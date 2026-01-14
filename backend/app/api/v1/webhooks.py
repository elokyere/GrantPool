"""
Webhook endpoints for external services (Paystack, etc.).
"""

import json
import hmac
import hashlib
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status, Header
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import Optional

from app.db.database import SessionLocal
from app.db import models
from app.core.config import settings
from app.services.payment_service import PaymentService

router = APIRouter()


def verify_paystack_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Paystack webhook signature using HMAC SHA512.
    
    Paystack signs webhooks with HMAC SHA512 using the Secret Key (same as API key).
    Note: Paystack does NOT use a separate webhook secret - it uses PAYSTACK_SECRET_KEY.
    """
    if not settings.PAYSTACK_SECRET_KEY:
        return False
    
    # Paystack uses HMAC SHA512 with the Secret Key (not a separate webhook secret)
    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()
    
    return hmac.compare_digest(computed_signature, signature)


@router.post("/paystack")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: Optional[str] = Header(None, alias="x-paystack-signature")
):
    """
    Handle Paystack webhook events.
    
    Verifies webhook signature and processes payment events.
    Paystack webhooks use HMAC SHA512 signature verification.
    """
    if not x_paystack_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing x-paystack-signature header"
        )
    
    if not settings.PAYSTACK_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paystack secret key not configured"
        )
    
    body = await request.body()
    
    # Verify webhook signature
    if not verify_paystack_signature(body, x_paystack_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    # Parse webhook event
    try:
        event = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {str(e)}"
        )
    
    # Handle the event
    db = SessionLocal()
    try:
        event_type = event.get("event")
        data = event.get("data", {})
        
        if event_type == "charge.success":
            # Payment successful
            reference = data.get("reference")
            if reference:
                PaymentService.handle_payment_success(reference, db)
                
        elif event_type == "charge.failed":
            # Payment failed
            reference = data.get("reference")
            if reference:
                PaymentService.handle_payment_failure(reference, db)
                
        elif event_type == "refund.processed":
            # Handle refunds processed by Paystack
            # Only process refunds that were approved via support requests
            reference = data.get("reference")
            refund_amount = data.get("amount", 0)
            
            if reference:
                payment = db.query(models.Payment).filter(
                    models.Payment.paystack_reference == reference
                ).first()
                
                if payment:
                    # Update payment refund status
                    payment.refund_status = "processed"
                    payment.refund_amount = refund_amount
                    payment.refunded_at = datetime.utcnow()
                    
                    # Update refund metadata
                    payment.refund_metadata = payment.refund_metadata or {}
                    payment.refund_metadata["paystack_refund_data"] = data
                    payment.refund_metadata["refund_processed_at"] = datetime.utcnow().isoformat()
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(payment, "refund_metadata")
                    
                    # Find and update associated support request
                    support_request = db.query(models.SupportRequest).filter(
                        models.SupportRequest.payment_id == payment.id,
                        models.SupportRequest.status == "resolved"
                    ).order_by(models.SupportRequest.created_at.desc()).first()
                    
                    if support_request:
                        support_request.resolution_type = "refund"
                        support_request.resolution_amount = refund_amount
                        support_request.status = "resolved"
                    
                    db.commit()
        
        return {"status": "success"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing error: {str(e)}"
        )
    finally:
        db.close()


@router.get("/paystack/callback")
async def paystack_callback(
    reference: str = None,
    trxref: str = None,
    ref: str = None,
    request: Request = None
):
    """
    Paystack payment callback endpoint.
    
    This is called after user completes payment on Paystack.
    Verifies the transaction and redirects to frontend dashboard.
    Note: Paystack may use 'reference' or 'trxref' parameter.
    We also support 'ref' query parameter for our custom callback URL.
    """
    # Use reference, trxref, or ref (our custom parameter)
    payment_ref = reference or trxref or ref
    if not payment_ref:
        # Redirect to dashboard with error
        frontend_url = settings.FRONTEND_URL or settings.APP_URL.replace('/api/v1', '')
        return RedirectResponse(
            url=f"{frontend_url}/dashboard?payment=error&message=Missing+reference+parameter",
            status_code=302
        )
    
    db = SessionLocal()
    try:
        # Verify transaction
        payment = PaymentService.verify_transaction(payment_ref, db)
        
        # Get frontend URL (fallback to APP_URL without /api/v1)
        frontend_url = settings.FRONTEND_URL or settings.APP_URL.replace('/api/v1', '').replace('/api', '')
        
        if payment and payment.status == "succeeded":
            # Payment successful - redirect to dashboard with reference
            return RedirectResponse(
                url=f"{frontend_url}/dashboard?payment=success&reference={payment_ref}",
                status_code=302
            )
        else:
            # Payment failed - redirect to dashboard with error
            return RedirectResponse(
                url=f"{frontend_url}/dashboard?payment=failed&reference={payment_ref}",
                status_code=302
            )
    except Exception as e:
        # Error occurred - redirect to dashboard with error
        frontend_url = settings.FRONTEND_URL or settings.APP_URL.replace('/api/v1', '').replace('/api', '')
        return RedirectResponse(
            url=f"{frontend_url}/dashboard?payment=error&message={str(e).replace(' ', '+')}",
            status_code=302
        )
    finally:
        db.close()
