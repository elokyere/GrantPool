"""
Payment endpoints for Paystack integration.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.database import get_db
from app.db import models
from app.api.v1.auth import get_current_user
from app.services.payment_service import PaymentService
from app.services.credit_service import CreditService
from app.services.payment_analytics import PaymentAnalytics
from app.services.fx_service import ghs_to_usd_display
from app.core.middleware import get_rate_limiter
from app.core.config import settings
from datetime import datetime, timedelta

router = APIRouter()
limiter = get_rate_limiter()


class PaymentInitializeRequest(BaseModel):
    country_code: Optional[str] = None  # ISO 3166-1 alpha-2
    payment_type: str = "standard"  # "refinement", "standard", or "bundle"


class PaymentInitializeResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str
    amount: int
    currency: str
    payment_type: str
    assessment_count: int  # 1 for standard/refinement, 3 for bundle


class CreditStatusResponse(BaseModel):
    free_available: bool
    total_assessments: int
    paid_assessments: int
    free_assessments: int
    bundle_credits: int = 0  # Number of unused assessments from bundle purchases


class PriceDisplay(BaseModel):
    payment_type: str
    ghs_amount_pesewas: int
    ghs_amount: float
    usd_equivalent: Optional[float] = None  # None if FX rate unavailable


class PricingResponse(BaseModel):
    refinement: PriceDisplay
    standard: PriceDisplay
    bundle: PriceDisplay


@router.post("/initialize", response_model=PaymentInitializeResponse)
@limiter.limit("5/minute")
async def initialize_payment(
    request: Request,
    payment_request: PaymentInitializeRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initialize a Paystack transaction for an assessment.
    
    Returns authorization_url that user should be redirected to for payment.
    User must not have free assessment available to initialize payment.
    """
    # Check if user has free assessment available
    if CreditService.has_free_assessment_available(current_user.id, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free assessment available. Use free assessment instead."
        )
    
    # Validate payment_type
    if payment_request.payment_type not in ["refinement", "standard", "bundle"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payment_type must be 'refinement', 'standard', or 'bundle'"
        )
    
    try:
        result = PaymentService.initialize_transaction(
            user_id=current_user.id,
            country_code=payment_request.country_code or current_user.country_code,
            db=db,
            payment_type=payment_request.payment_type
        )
        return PaymentInitializeResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment intent: {str(e)}"
        )


@router.get("/status", response_model=CreditStatusResponse)
async def get_credit_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's assessment credit status."""
    try:
        status_data = CreditService.get_user_assessment_status(current_user.id, db)
        return CreditStatusResponse(**status_data)
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting credit status for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get credit status: {str(e)}"
        )


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing():
    """
    Get pricing information for display.
    
    Returns locked GHS prices with USD equivalents (for display only).
    All payments are charged in GHS. USD equivalent is approximate and informational.
    """
    # Get locked GHS prices
    refinement_ghs = PaymentService.get_ghs_price("refinement")
    standard_ghs = PaymentService.get_ghs_price("standard")
    bundle_ghs = PaymentService.get_ghs_price("bundle")
    
    # Get USD equivalents (for display only)
    refinement_usd = ghs_to_usd_display(refinement_ghs)
    standard_usd = ghs_to_usd_display(standard_ghs)
    bundle_usd = ghs_to_usd_display(bundle_ghs)
    
    return PricingResponse(
        refinement=PriceDisplay(
            payment_type="refinement",
            ghs_amount_pesewas=refinement_ghs,
            ghs_amount=refinement_ghs / 100.0,
            usd_equivalent=refinement_usd
        ),
        standard=PriceDisplay(
            payment_type="standard",
            ghs_amount_pesewas=standard_ghs,
            ghs_amount=standard_ghs / 100.0,
            usd_equivalent=standard_usd
        ),
        bundle=PriceDisplay(
            payment_type="bundle",
            ghs_amount_pesewas=bundle_ghs,
            ghs_amount=bundle_ghs / 100.0,
            usd_equivalent=bundle_usd
        )
    )


@router.get("/history")
async def get_payment_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's payment history with linked assessment counts."""
    payments = db.query(models.Payment).filter(
        models.Payment.user_id == current_user.id
    ).order_by(models.Payment.created_at.desc()).all()
    
    result = []
    for p in payments:
        # Count linked assessments
        linked_count = db.query(models.AssessmentPurchase).filter(
            models.AssessmentPurchase.payment_id == p.id
        ).count()
        
        result.append({
            "id": p.id,
            "amount": p.amount,
            "currency": p.currency,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
            "assessment_count": p.assessment_count,
            "linked_assessments": linked_count,
            "missing_assessments": max(0, p.assessment_count - linked_count) if p.status == "succeeded" else 0,
            "paystack_reference": p.paystack_reference,
            "payment_type": p.payment_type
        })
    
    return result


@router.get("/analytics")
async def get_payment_analytics(
    days: int = 30,
    payment_type: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get payment analytics (admin or user-specific).
    
    Returns payment success rates and average completion times.
    """
    # For now, return user-specific analytics
    # In production, add admin check for system-wide analytics
    metrics = PaymentAnalytics.get_payment_metrics(
        days=days,
        payment_type=payment_type,
        db=db
    )
    
    return metrics

