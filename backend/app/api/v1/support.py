"""
Support and refund request endpoints.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.middleware import get_rate_limiter
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = get_rate_limiter()

from app.db.database import get_db
from app.db import models
from app.api.v1.auth import get_current_user
from app.services.refund_service import RefundService
from app.services.email_service import EmailService
from app.services.slack_service import send_support_request_notification


class SupportRequestCreate(BaseModel):
    issue_type: str  # 'duplicate_payment', 'technical_error', 'payment_issue', 'other'
    description: str
    payment_id: Optional[int] = None
    evaluation_id: Optional[int] = None


class SupportRequestResponse(BaseModel):
    id: int
    user_id: int
    payment_id: Optional[int]
    evaluation_id: Optional[int]
    issue_type: str
    status: str
    description: str
    resolution_type: Optional[str]
    resolution_amount: Optional[int]
    resolution_currency: Optional[str]
    admin_notes: Optional[str]
    auto_verified: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class RefundPolicyResponse(BaseModel):
    refunds_allowed: bool
    eligibility: List[str]
    no_cash_refunds: str
    product_type: str
    delivery: str


@router.post("/support/request", response_model=SupportRequestResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def create_support_request(
    request: Request,
    support_data: SupportRequestCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a support request for refund or technical issues.
    
    Issue types:
    - duplicate_payment: Report duplicate charges
    - technical_error: Report technical issues preventing assessment generation
    - payment_issue: Report payment processing problems
    - other: General support requests
    """
    # Validate issue type
    valid_issue_types = ["duplicate_payment", "technical_error", "payment_issue", "other"]
    if support_data.issue_type not in valid_issue_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid issue_type. Must be one of: {', '.join(valid_issue_types)}"
        )
    
    # Create support request
    try:
        support_request = RefundService.create_support_request(
            user_id=current_user.id,
            issue_type=support_data.issue_type,
            description=support_data.description,
            payment_id=support_data.payment_id,
            evaluation_id=support_data.evaluation_id,
            db=db
        )
        
        # Send confirmation email
        email_service = EmailService()
        from app.core.config import settings
        
        subject = "Support Request Received - GrantPool"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .status {{ padding: 10px; border-radius: 6px; margin: 20px 0; }}
                .resolved {{ background-color: #d1fae5; color: #065f46; }}
                .pending {{ background-color: #fef3c7; color: #92400e; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Support Request Received</h2>
                <p>Thank you for contacting GrantPool support.</p>
                <p><strong>Request ID:</strong> #{support_request.id}</p>
                <p><strong>Issue Type:</strong> {support_request.issue_type.replace('_', ' ').title()}</p>
                <div class="status {support_request.status}">
                    <strong>Status:</strong> {support_request.status.replace('_', ' ').title()}
                </div>
                {f'<p><strong>Resolution:</strong> Your request has been automatically verified and approved. You will receive a credit for future assessments.</p>' if support_request.status == 'resolved' and support_request.auto_verified else '<p>Our team will review your request within 48 hours.</p>'}
                <p>If you have any questions, please reply to this email.</p>
                <div style="margin-top: 30px; font-size: 12px; color: #666;">
                    <p>GrantPool - Decisive grant triage system</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Support Request Received
        
        Thank you for contacting GrantPool support.
        
        Request ID: #{support_request.id}
        Issue Type: {support_request.issue_type.replace('_', ' ').title()}
        Status: {support_request.status.replace('_', ' ').title()}
        
        {f'Your request has been automatically verified and approved. You will receive a credit for future assessments.' if support_request.status == 'resolved' and support_request.auto_verified else 'Our team will review your request within 48 hours.'}
        
        If you have any questions, please reply to this email.
        
        GrantPool - Decisive grant triage system
        """
        
        email_service.send_email(current_user.email, subject, html_content, text_content)
        
        # Send notification email to support team
        support_email = "hello@grantpool.org"
        support_subject = f"New Support Request #{support_request.id} - {support_request.issue_type.replace('_', ' ').title()}"
        
        # Get related information
        payment_info = ""
        if support_request.payment_id:
            payment = db.query(models.Payment).filter(models.Payment.id == support_request.payment_id).first()
            if payment:
                payment_info = f"""
                <p><strong>Payment Details:</strong></p>
                <ul>
                    <li>Payment ID: {payment.id}</li>
                    <li>Amount: ${payment.amount / 100:.2f} {payment.currency}</li>
                    <li>Status: {payment.status}</li>
                    <li>Reference: {payment.paystack_reference or 'N/A'}</li>
                    <li>Date: {payment.created_at.strftime('%Y-%m-%d %H:%M:%S') if payment.created_at else 'N/A'}</li>
                </ul>
                """
        
        evaluation_info = ""
        if support_request.evaluation_id:
            evaluation = db.query(models.Evaluation).filter(models.Evaluation.id == support_request.evaluation_id).first()
            if evaluation:
                evaluation_info = f"""
                <p><strong>Evaluation Details:</strong></p>
                <ul>
                    <li>Evaluation ID: {evaluation.id}</li>
                    <li>Grant ID: {evaluation.grant_id}</li>
                    <li>Project ID: {evaluation.project_id}</li>
                    <li>Tier: {evaluation.evaluation_tier}</li>
                    <li>Recommendation: {evaluation.recommendation}</li>
                </ul>
                """
        
        support_html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .info-box {{ background-color: #f8f9fa; padding: 15px; border-radius: 6px; margin: 15px 0; }}
                .status {{ padding: 10px; border-radius: 6px; margin: 15px 0; }}
                .resolved {{ background-color: #d1fae5; color: #065f46; }}
                .pending {{ background-color: #fef3c7; color: #92400e; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>New Support Request</h2>
                <div class="info-box">
                    <p><strong>Request ID:</strong> #{support_request.id}</p>
                    <p><strong>User:</strong> {current_user.email} (ID: {current_user.id})</p>
                    <p><strong>Issue Type:</strong> {support_request.issue_type.replace('_', ' ').title()}</p>
                    <div class="status {support_request.status}">
                        <strong>Status:</strong> {support_request.status.replace('_', ' ').title()}
                        {' (Auto-verified)' if support_request.auto_verified else ''}
                    </div>
                </div>
                
                <div class="info-box">
                    <p><strong>Description:</strong></p>
                    <p>{support_request.description}</p>
                </div>
                
                {payment_info}
                {evaluation_info}
                
                <p><strong>View in admin panel:</strong> Support Request #{support_request.id}</p>
                
                <div style="margin-top: 30px; font-size: 12px; color: #666; border-top: 1px solid #ddd; padding-top: 15px;">
                    <p>GrantPool Support System</p>
                    <p>Submitted: {support_request.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        support_text_content = f"""
        New Support Request
        
        Request ID: #{support_request.id}
        User: {current_user.email} (ID: {current_user.id})
        Issue Type: {support_request.issue_type.replace('_', ' ').title()}
        Status: {support_request.status.replace('_', ' ').title()}{' (Auto-verified)' if support_request.auto_verified else ''}
        
        Description:
        {support_request.description}
        
        {f'Payment ID: {support_request.payment_id}' if support_request.payment_id else ''}
        {f'Evaluation ID: {support_request.evaluation_id}' if support_request.evaluation_id else ''}
        
        Submitted: {support_request.created_at.strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # Send email to support team
        email_service.send_email(support_email, support_subject, support_html_content, support_text_content)
        
        # Send Slack notification (Flag Review - support request notification)
        try:
            send_support_request_notification(
                request_id=support_request.id,
                issue_type=support_request.issue_type,
                user_email=current_user.email,
                description=support_request.description,
                payment_id=support_request.payment_id,
                evaluation_id=support_request.evaluation_id
            )
        except Exception as e:
            logger.warning(f"Failed to send Slack notification for support request {support_request.id}: {e}")
            # Non-critical - email notification still sent
        
        return support_request
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating support request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create support request. Please try again later."
        )


@router.get("/support/requests", response_model=List[SupportRequestResponse])
async def list_support_requests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all support requests for the current user."""
    requests = db.query(models.SupportRequest).filter(
        models.SupportRequest.user_id == current_user.id
    ).order_by(models.SupportRequest.created_at.desc()).all()
    
    return requests


@router.get("/support/requests/{request_id}", response_model=SupportRequestResponse)
async def get_support_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific support request."""
    support_request = db.query(models.SupportRequest).filter(
        models.SupportRequest.id == request_id,
        models.SupportRequest.user_id == current_user.id
    ).first()
    
    if not support_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Support request not found"
        )
    
    return support_request


@router.get("/support/policy", response_model=RefundPolicyResponse)
async def get_refund_policy():
    """Get the refund and support policy."""
    policy = RefundService.get_refund_policy()
    return RefundPolicyResponse(**policy)

