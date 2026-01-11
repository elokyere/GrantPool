"""
Refund service - GrantPool Refund & Support Policy

Implements refund policy:
- No cash refunds for delivered assessments
- Eligible refunds/credits for: duplicate payments, technical errors, payment processing issues
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db import models
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)


class RefundService:
    """
    Refund service implementing GrantPool Refund & Support Policy.
    
    Policy:
    - Digital assessments are delivered instantly upon payment
    - No cash refunds for successfully delivered assessments
    - Eligible refunds/credits for:
      1. Duplicate payments
      2. Technical errors preventing assessment generation
      3. Payment processing issues
    """
    
    REFUND_POLICY = {
        "refunds_allowed": True,
        "eligibility": [
            "duplicate_payment",
            "technical_error",
            "payment_processing_issue"
        ],
        "no_cash_refunds": "Once an assessment is generated, cash refunds are not available",
        "product_type": "digital_assessment",
        "delivery": "immediate_upon_payment"
    }
    
    @staticmethod
    def check_duplicate_payment(payment_id: int, user_id: int, db: Session) -> bool:
        """
        Check if a payment is a duplicate.
        
        A duplicate payment is:
        - Same amount
        - Same currency
        - Same payment type
        - Within 5 minutes of another payment
        - Same user
        """
        payment = db.query(models.Payment).filter(
            models.Payment.id == payment_id,
            models.Payment.user_id == user_id
        ).first()
        
        if not payment:
            return False
        
        # Check for duplicate payments within 5 minutes
        time_window = payment.created_at - timedelta(minutes=5)
        
        duplicate = db.query(models.Payment).filter(
            and_(
                models.Payment.user_id == user_id,
                models.Payment.id != payment_id,
                models.Payment.amount == payment.amount,
                models.Payment.currency == payment.currency,
                models.Payment.payment_type == payment.payment_type,
                models.Payment.status == "succeeded",
                models.Payment.created_at >= time_window,
                models.Payment.created_at <= payment.created_at + timedelta(minutes=5)
            )
        ).first()
        
        return duplicate is not None
    
    @staticmethod
    def check_technical_error(payment_id: int, evaluation_id: Optional[int], db: Session) -> bool:
        """
        Check if there was a technical error preventing assessment generation.
        
        A technical error is indicated by:
        - Payment succeeded
        - But no evaluation was created within 10 minutes
        - OR evaluation creation failed (error in logs)
        """
        payment = db.query(models.Payment).filter(
            models.Payment.id == payment_id
        ).first()
        
        if not payment or payment.status != "succeeded":
            return False
        
        # Check if payment has associated evaluation
        if evaluation_id:
            evaluation = db.query(models.Evaluation).filter(
                models.Evaluation.id == evaluation_id
            ).first()
            if not evaluation:
                return True  # Payment succeeded but no evaluation
        else:
            # Check if payment has any associated assessments
            purchase = db.query(models.AssessmentPurchase).filter(
                models.AssessmentPurchase.payment_id == payment_id
            ).first()
            if not purchase:
                # Check if payment was made more than 10 minutes ago and no assessment exists
                if payment.created_at < datetime.utcnow() - timedelta(minutes=10):
                    return True
        
        return False
    
    @staticmethod
    def check_payment_processing_issue(payment_id: int, db: Session) -> bool:
        """
        Check if there was a payment processing issue.
        
        A payment processing issue is:
        - Payment status is 'failed' but user was charged
        - Payment metadata indicates processing error
        - Duplicate charge on same transaction
        """
        payment = db.query(models.Payment).filter(
            models.Payment.id == payment_id
        ).first()
        
        if not payment:
            return False
        
        # Check metadata for processing errors
        metadata = payment.payment_metadata or {}
        if metadata.get("processing_error"):
            return True
        
        # Check if payment failed but user was charged (status mismatch)
        if payment.status == "failed":
            # Check Paystack to verify actual status
            # For now, if status is failed, consider it a processing issue if metadata indicates charge
            if metadata.get("charged_but_failed"):
                return True
        
        return False
    
    @staticmethod
    def verify_refund_eligibility(
        payment_id: int,
        user_id: int,
        issue_type: str,
        evaluation_id: Optional[int] = None,
        db: Session = None
    ) -> Dict:
        """
        Verify if a refund request is eligible.
        
        Returns:
        {
            "eligible": bool,
            "reason": str,
            "auto_verified": bool
        }
        """
        payment = db.query(models.Payment).filter(
            models.Payment.id == payment_id,
            models.Payment.user_id == user_id
        ).first()
        
        if not payment:
            return {
                "eligible": False,
                "reason": "Payment not found",
                "auto_verified": False
            }
        
        # Check if assessment was already delivered (no refunds for delivered assessments)
        purchase = db.query(models.AssessmentPurchase).filter(
            models.AssessmentPurchase.payment_id == payment_id
        ).first()
        
        if purchase:
            evaluation = db.query(models.Evaluation).filter(
                models.Evaluation.id == purchase.evaluation_id
            ).first()
            if evaluation and issue_type != "technical_error":
                return {
                    "eligible": False,
                    "reason": "Assessment was successfully delivered. Refunds are not available for delivered assessments.",
                    "auto_verified": True
                }
        
        # Verify based on issue type
        if issue_type == "duplicate_payment":
            is_duplicate = RefundService.check_duplicate_payment(payment_id, user_id, db)
            return {
                "eligible": is_duplicate,
                "reason": "Duplicate payment detected" if is_duplicate else "No duplicate payment found",
                "auto_verified": True
            }
        
        elif issue_type == "technical_error":
            has_error = RefundService.check_technical_error(payment_id, evaluation_id, db)
            return {
                "eligible": has_error,
                "reason": "Technical error preventing assessment generation" if has_error else "Assessment was generated successfully",
                "auto_verified": has_error  # Only auto-verify if error is confirmed
            }
        
        elif issue_type == "payment_issue":
            has_issue = RefundService.check_payment_processing_issue(payment_id, db)
            return {
                "eligible": has_issue,
                "reason": "Payment processing issue detected" if has_issue else "Payment processed successfully",
                "auto_verified": has_issue
            }
        
        else:
            return {
                "eligible": False,
                "reason": "Invalid issue type. Must be: duplicate_payment, technical_error, or payment_issue",
                "auto_verified": False
            }
    
    @staticmethod
    def create_support_request(
        user_id: int,
        issue_type: str,
        description: str,
        payment_id: Optional[int] = None,
        evaluation_id: Optional[int] = None,
        db: Session = None
    ) -> models.SupportRequest:
        """
        Create a support request and verify eligibility.
        """
        # Verify payment belongs to user
        if payment_id:
            payment = db.query(models.Payment).filter(
                models.Payment.id == payment_id,
                models.Payment.user_id == user_id
            ).first()
            if not payment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found or access denied"
                )
        
        # Verify evaluation belongs to user if provided
        if evaluation_id:
            evaluation = db.query(models.Evaluation).filter(
                models.Evaluation.id == evaluation_id,
                models.Evaluation.user_id == user_id
            ).first()
            if not evaluation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Evaluation not found or access denied"
                )
        
        # Verify refund eligibility
        if payment_id and issue_type in ["duplicate_payment", "technical_error", "payment_issue"]:
            eligibility = RefundService.verify_refund_eligibility(
                payment_id, user_id, issue_type, evaluation_id, db
            )
            
            # Create support request
            support_request = models.SupportRequest(
                user_id=user_id,
                payment_id=payment_id,
                evaluation_id=evaluation_id,
                issue_type=issue_type,
                description=description,
                status="resolved" if eligibility["eligible"] and eligibility["auto_verified"] else "pending",
                auto_verified=eligibility["auto_verified"]
            )
        else:
            # General support request (not refund-related)
            support_request = models.SupportRequest(
                user_id=user_id,
                payment_id=payment_id,
                evaluation_id=evaluation_id,
                issue_type=issue_type,
                description=description,
                status="pending",
                auto_verified=False
            )
        
        db.add(support_request)
        
        # If auto-verified and eligible, automatically process credit
        if support_request.status == "resolved" and payment_id:
            payment = db.query(models.Payment).get(payment_id)
            if payment:
                # Issue credit (refund will be processed manually or via admin)
                support_request.resolution_type = "credit"
                support_request.resolution_amount = payment.amount
                support_request.resolution_currency = payment.currency
                
                # Update payment refund status
                payment.refund_status = "approved"
                payment.refund_reason = eligibility["reason"]
        
        db.commit()
        db.refresh(support_request)
        
        return support_request
    
    @staticmethod
    def get_refund_policy() -> dict:
        """Get the refund policy information."""
        return RefundService.REFUND_POLICY.copy()
    
    @staticmethod
    def process_refund(
        support_request_id: int,
        resolution_type: str,  # 'credit' or 'refund'
        admin_notes: Optional[str] = None,
        db: Session = None
    ) -> models.SupportRequest:
        """
        Process a refund or credit for an approved support request.
        This should typically be called by an admin.
        """
        support_request = db.query(models.SupportRequest).filter(
            models.SupportRequest.id == support_request_id
        ).first()
        
        if not support_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Support request not found"
            )
        
        if support_request.status != "resolved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Support request must be resolved before processing refund"
            )
        
        if not support_request.payment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No payment associated with this support request"
            )
        
        payment = db.query(models.Payment).get(support_request.payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Update support request
        support_request.resolution_type = resolution_type
        support_request.resolution_amount = payment.amount
        support_request.resolution_currency = payment.currency
        support_request.admin_notes = admin_notes
        
        # Update payment
        payment.refund_status = "processed"
        payment.refund_amount = payment.amount
        payment.refund_reason = f"Refund for: {support_request.issue_type}"
        payment.refunded_at = datetime.utcnow()
        
        # If credit, update user's credit balance (implement credit service method)
        if resolution_type == "credit":
            # TODO: Implement credit service method to add credits
            # For now, we'll just mark it as processed
            payment.refund_metadata = {
                "resolution_type": "credit",
                "support_request_id": support_request_id
            }
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(payment, "refund_metadata")
        
        db.commit()
        db.refresh(support_request)
        
        return support_request
