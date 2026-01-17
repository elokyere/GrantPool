"""
User management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import update
import logging
from app.db.database import get_db
from app.db import models
from app.api.v1.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/me")
async def get_user_profile(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "created_at": current_user.created_at,
    }


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_account(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete the current user's account and all associated data.
    
    This will:
    - Delete all user's projects
    - Delete all user's evaluations
    - Delete all user's assessment purchases
    - Delete all user's support requests
    - Delete all user's payment records (only metadata, no card data stored)
    - Anonymize audit logs (set user_id to NULL for security compliance - backend only)
    - Remove user from grant approvals (set approved_by to NULL)
    - Finally delete the user account
    
    Note: GrantPool does not store payment card details. All payments are processed
    through Paystack. We only store payment transaction metadata.
    
    This action is irreversible.
    """
    try:
        user_id = current_user.id
        user_email = current_user.email
        
        logger.info(f"Starting account deletion for user {user_id} ({user_email})")
        
        # 1. Delete user's support requests FIRST (they reference evaluations and payments)
        support_requests_count = db.query(models.SupportRequest).filter(
            models.SupportRequest.user_id == user_id
        ).count()
        if support_requests_count > 0:
            db.query(models.SupportRequest).filter(
                models.SupportRequest.user_id == user_id
            ).delete(synchronize_session=False)
            db.flush()
        logger.info(f"Deleted {support_requests_count} support requests for user {user_id}")
        
        # 2. Delete user's assessment purchases (they reference evaluations)
        assessment_purchases_count = db.query(models.AssessmentPurchase).filter(
            models.AssessmentPurchase.user_id == user_id
        ).count()
        if assessment_purchases_count > 0:
            db.query(models.AssessmentPurchase).filter(
                models.AssessmentPurchase.user_id == user_id
            ).delete(synchronize_session=False)
            db.flush()
        logger.info(f"Deleted {assessment_purchases_count} assessment purchases for user {user_id}")
        
        # 3. Delete user's evaluations (after support requests and assessment purchases are deleted)
        evaluations_count = db.query(models.Evaluation).filter(
            models.Evaluation.user_id == user_id
        ).count()
        if evaluations_count > 0:
            db.query(models.Evaluation).filter(
                models.Evaluation.user_id == user_id
            ).delete(synchronize_session=False)
            db.flush()
        logger.info(f"Deleted {evaluations_count} evaluations for user {user_id}")
        
        # 4. Delete user's projects (after evaluations are deleted)
        projects_count = db.query(models.Project).filter(
            models.Project.user_id == user_id
        ).count()
        if projects_count > 0:
            db.query(models.Project).filter(
                models.Project.user_id == user_id
            ).delete(synchronize_session=False)
            db.flush()
        logger.info(f"Deleted {projects_count} projects for user {user_id}")
        
        # 5. Delete user's payment records (only metadata, no card data stored)
        payments_count = db.query(models.Payment).filter(
            models.Payment.user_id == user_id
        ).count()
        if payments_count > 0:
            db.query(models.Payment).filter(
                models.Payment.user_id == user_id
            ).delete(synchronize_session=False)
            db.flush()
        logger.info(f"Deleted {payments_count} payment records for user {user_id}")
        
        # 6. Anonymize audit logs (keep for security compliance, but remove user association - backend only)
        audit_logs_count = db.query(models.AuditLog).filter(
            models.AuditLog.user_id == user_id
        ).count()
        if audit_logs_count > 0:
            db.execute(
                update(models.AuditLog)
                .where(models.AuditLog.user_id == user_id)
                .values(user_id=None)
            )
            db.flush()
        logger.info(f"Anonymized {audit_logs_count} audit logs for user {user_id}")
        
        # 7. Remove user from grant approvals (set approved_by to NULL)
        grants_approved_count = db.query(models.Grant).filter(
            models.Grant.approved_by == user_id
        ).count()
        if grants_approved_count > 0:
            db.execute(
                update(models.Grant)
                .where(models.Grant.approved_by == user_id)
                .values(approved_by=None)
            )
            db.flush()
        logger.info(f"Removed user {user_id} from {grants_approved_count} grant approvals")
        
        # 8. Remove user from grant normalization approvals
        normalizations_approved_count = db.query(models.GrantNormalization).filter(
            models.GrantNormalization.approved_by_user_id == user_id
        ).count()
        if normalizations_approved_count > 0:
            db.execute(
                update(models.GrantNormalization)
                .where(models.GrantNormalization.approved_by_user_id == user_id)
                .values(approved_by_user_id=None)
            )
            db.flush()
        logger.info(f"Removed user {user_id} from {normalizations_approved_count} grant normalization approvals")
        
        # 9. Finally, delete the user account
        # Get fresh user object from database to ensure it's in the session
        user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
        if not user_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        db.delete(user_to_delete)
        db.commit()
        
        logger.info(f"Successfully deleted account for user {user_id} ({user_email})")
        
        return {
            "message": "Account deleted successfully",
            "deleted": {
                "projects": projects_count,
                "evaluations": evaluations_count,
                "assessment_purchases": assessment_purchases_count,
                "support_requests": support_requests_count,
                "payments": payments_count,
                "audit_logs_anonymized": audit_logs_count,  # Backend only, not shown to user
                "grants_approvals_removed": grants_approved_count,
                "normalizations_approvals_removed": normalizations_approved_count,
            }
        }
        
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        logger.error(f"Error deleting account for user {current_user.id}: {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {error_msg}. Please contact support if this persists."
        )

