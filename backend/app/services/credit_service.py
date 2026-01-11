"""
Service for managing user assessment credits and free assessments.
"""

from sqlalchemy.orm import Session
from app.db import models
from typing import Optional


class CreditService:
    """Service for managing assessment credits."""
    
    @staticmethod
    def has_free_assessment_available(user_id: int, db: Session) -> bool:
        """
        Check if user has a free assessment available.
        
        Returns True if user hasn't used their free assessment yet.
        """
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return False
        
        return not user.free_assessment_used
    
    @staticmethod
    def use_free_assessment(user_id: int, evaluation_id: int, db: Session) -> bool:
        """
        Mark free assessment as used and create purchase record.
        
        Returns True if successful, False if free assessment already used.
        """
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return False
        
        if user.free_assessment_used:
            return False
        
        # Mark free assessment as used
        user.free_assessment_used = True
        
        # Create purchase record
        purchase = models.AssessmentPurchase(
            user_id=user_id,
            evaluation_id=evaluation_id,
            payment_id=None,
            purchase_type="free",
            currency=None,
            amount_paid=None,
        )
        db.add(purchase)
        db.commit()
        
        return True
    
    @staticmethod
    def can_access_evaluation(user_id: int, evaluation_id: int, db: Session) -> bool:
        """
        Check if user can access an evaluation.
        
        Users can only access assessments they have purchased (free or paid).
        Each assessment requires either:
        - Free assessment (first one only)
        - Payment (all subsequent assessments)
        
        Access is per-assessment: users can view each assessment they paid for,
        but must pay for each new assessment.
        """
        # Check if user owns the evaluation
        evaluation = db.query(models.Evaluation).filter(
            models.Evaluation.id == evaluation_id,
            models.Evaluation.user_id == user_id
        ).first()
        
        if not evaluation:
            return False
        
        # Check if there's a purchase record (free or paid)
        purchase = db.query(models.AssessmentPurchase).filter(
            models.AssessmentPurchase.evaluation_id == evaluation_id,
            models.AssessmentPurchase.user_id == user_id
        ).first()
        
        return purchase is not None
    
    @staticmethod
    def has_bundle_credits_available(user_id: int, db: Session) -> Optional[models.Payment]:
        """
        Check if user has unused bundle credits available.
        
        Returns the Payment object if bundle credits are available, None otherwise.
        """
        # Find bundle payments that haven't been fully used
        bundle_payments = db.query(models.Payment).filter(
            models.Payment.user_id == user_id,
            models.Payment.payment_type == "bundle",
            models.Payment.status == "succeeded"
        ).all()
        
        for bundle_payment in bundle_payments:
            # Count how many assessments have been used from this bundle
            used_count = db.query(models.AssessmentPurchase).filter(
                models.AssessmentPurchase.payment_id == bundle_payment.id,
                models.AssessmentPurchase.user_id == user_id
            ).count()
            
            # Check if there are unused credits
            # Default to 1 if assessment_count is None (for backward compatibility)
            assessment_count = bundle_payment.assessment_count if bundle_payment.assessment_count is not None else 1
            if used_count < assessment_count:
                return bundle_payment
        
        return None
    
    @staticmethod
    def get_user_assessment_status(user_id: int, db: Session) -> dict:
        """
        Get user's assessment credit status.
        
        Returns:
        {
            "free_available": bool,
            "total_assessments": int,
            "paid_assessments": int,
            "free_assessments": int
        }
        """
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return {
                "free_available": False,
                "total_assessments": 0,
                "paid_assessments": 0,
                "free_assessments": 0
            }
        
        # Count assessments
        total = db.query(models.Evaluation).filter(
            models.Evaluation.user_id == user_id
        ).count()
        
        purchases = db.query(models.AssessmentPurchase).filter(
            models.AssessmentPurchase.user_id == user_id
        ).all()
        
        paid_count = sum(1 for p in purchases if p.purchase_type == "paid")
        free_count = sum(1 for p in purchases if p.purchase_type == "free")
        
        # Check for bundle credits
        bundle_payment = CreditService.has_bundle_credits_available(user_id, db)
        bundle_credits = 0
        if bundle_payment and bundle_payment.assessment_count is not None:
            used_count = db.query(models.AssessmentPurchase).filter(
                models.AssessmentPurchase.payment_id == bundle_payment.id,
                models.AssessmentPurchase.user_id == user_id
            ).count()
            bundle_credits = max(0, bundle_payment.assessment_count - used_count)
        
        return {
            "free_available": not user.free_assessment_used,
            "total_assessments": total,
            "paid_assessments": paid_count,
            "free_assessments": free_count,
            "bundle_credits": bundle_credits
        }

