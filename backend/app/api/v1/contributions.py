"""
Grant data contribution endpoints.
Allows users to submit missing grant information they discover.
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl, field_validator, model_validator
from app.db.database import get_db
from app.db import models
from app.api.v1.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models
class ContributionCreate(BaseModel):
    """Request to submit grant data contribution."""
    grant_id: Optional[int] = None  # If grant is indexed
    evaluation_id: Optional[int] = None  # If evaluation exists
    grant_name: Optional[str] = None  # For in-memory grants
    grant_url: Optional[str] = None  # For in-memory grants
    field_name: str  # 'award_amount', 'deadline', 'acceptance_rate', 'past_recipients', etc.
    field_value: str  # The value provided
    source_url: Optional[str] = None  # URL where user found the data
    source_description: Optional[str] = None  # Additional context
    
    @field_validator('field_name')
    @classmethod
    def validate_field_name(cls, v):
        allowed_fields = [
            'award_amount', 'deadline', 'decision_date', 'acceptance_rate',
            'past_recipients', 'eligibility', 'preferred_applicants',
            'application_requirements', 'award_structure', 'other'
        ]
        if v not in allowed_fields:
            raise ValueError(f"field_name must be one of: {', '.join(allowed_fields)}")
        return v
    
    @field_validator('field_value')
    @classmethod
    def validate_field_value(cls, v):
        if not v or not v.strip():
            raise ValueError("field_value cannot be empty")
        if len(v) > 5000:
            raise ValueError("field_value must be less than 5000 characters")
        return v.strip()
    
    @model_validator(mode='after')
    def validate_structured_fields(self):
        """Validate JSON structure for fields that require structured data."""
        if self.field_name == 'past_recipients':
            try:
                import json
                parsed = json.loads(self.field_value)
                if not isinstance(parsed, list):
                    raise ValueError("past_recipients must be a JSON array of recipient objects")
                if len(parsed) == 0:
                    raise ValueError("past_recipients array cannot be empty")
                # Validate each recipient object structure
                for i, recipient in enumerate(parsed):
                    if not isinstance(recipient, dict):
                        raise ValueError(f"Recipient at index {i} must be an object")
                    # At least one of these fields should be present
                    required_fields = ['organization_name', 'organization_type', 'project_title']
                    if not any(recipient.get(field) for field in required_fields):
                        raise ValueError(
                            f"Recipient at index {i} must have at least one of: "
                            f"organization_name, organization_type, or project_title"
                        )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON format for past_recipients: {str(e)}")
        elif self.field_name in ['preferred_applicants', 'application_requirements']:
            try:
                import json
                parsed = json.loads(self.field_value)
                if not isinstance(parsed, list):
                    raise ValueError(f"{self.field_name} must be a JSON array of strings")
                if len(parsed) == 0:
                    raise ValueError(f"{self.field_name} array cannot be empty")
                # Validate each item is a string
                for i, item in enumerate(parsed):
                    if not isinstance(item, str) or not item.strip():
                        raise ValueError(f"Item at index {i} must be a non-empty string")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON format for {self.field_name}: {str(e)}")
        return self


class ContributionResponse(BaseModel):
    """Response for contribution submission."""
    id: int
    grant_id: Optional[int]
    evaluation_id: Optional[int]
    grant_name: Optional[str]
    field_name: str
    field_value: str
    source_url: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/submit", response_model=ContributionResponse, status_code=status.HTTP_201_CREATED)
async def submit_contribution(
    contribution: ContributionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit a grant data contribution.
    
    Users can contribute missing grant information they discover.
    Contributions are reviewed by admins before being merged into grant data.
    """
    # Validate that at least one identifier is provided
    if not contribution.grant_id and not contribution.evaluation_id and not contribution.grant_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either grant_id, evaluation_id, or grant_name"
        )
    
    # If grant_id provided, verify grant exists
    if contribution.grant_id:
        grant = db.query(models.Grant).filter(models.Grant.id == contribution.grant_id).first()
        if not grant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grant not found"
            )
    
    # If evaluation_id provided, verify evaluation exists and belongs to user
    if contribution.evaluation_id:
        evaluation = db.query(models.Evaluation).filter(
            models.Evaluation.id == contribution.evaluation_id,
            models.Evaluation.user_id == current_user.id
        ).first()
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evaluation not found or does not belong to you"
            )
        # Auto-populate grant info from evaluation if not provided
        if not contribution.grant_id and evaluation.grant_id:
            contribution.grant_id = evaluation.grant_id
        if not contribution.grant_name and evaluation.grant_name:
            contribution.grant_name = evaluation.grant_name
        if not contribution.grant_url and evaluation.grant_url:
            contribution.grant_url = evaluation.grant_url
    
    # Create contribution record
    db_contribution = models.GrantDataContribution(
        user_id=current_user.id,
        grant_id=contribution.grant_id,
        evaluation_id=contribution.evaluation_id,
        grant_name=contribution.grant_name,
        grant_url=contribution.grant_url,
        field_name=contribution.field_name,
        field_value=contribution.field_value,
        source_url=contribution.source_url,
        source_description=contribution.source_description,
        status="pending"
    )
    
    db.add(db_contribution)
    db.commit()
    db.refresh(db_contribution)
    
    logger.info(
        f"User {current_user.id} submitted contribution {db_contribution.id} "
        f"for field '{contribution.field_name}' on grant {contribution.grant_id or contribution.grant_name}"
    )
    
    # Send Slack notification for admin review
    try:
        from app.services.slack_service import send_contribution_review_notification
        send_contribution_review_notification(
            contribution_id=db_contribution.id,
            grant_name=contribution.grant_name or (grant.name if grant else "Unknown Grant"),
            field_name=contribution.field_name,
            field_value=contribution.field_value,
            user_email=current_user.email,
            source_url=contribution.source_url
        )
    except Exception as e:
        logger.warning(f"Failed to send Slack notification for contribution {db_contribution.id}: {e}")
        # Don't fail the request - Slack notifications are non-critical
    
    return db_contribution


@router.get("/my-contributions", response_model=List[ContributionResponse])
async def get_my_contributions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: Optional[str] = None
):
    """Get current user's contributions."""
    query = db.query(models.GrantDataContribution).filter(
        models.GrantDataContribution.user_id == current_user.id
    )
    
    if status_filter:
        query = query.filter(models.GrantDataContribution.status == status_filter)
    
    contributions = query.order_by(models.GrantDataContribution.created_at.desc()).all()
    return contributions
