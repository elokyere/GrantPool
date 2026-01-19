"""
Project management endpoints.
"""

import re
from typing import List, Tuple, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import update
from pydantic import BaseModel, field_serializer, field_validator
from app.db.database import get_db
from app.db import models
from app.api.v1.auth import get_current_user
from app.services.credit_service import CreditService
from app.core.sanitization import sanitize_html, sanitize_text

router = APIRouter()


def parse_funding_need(funding_need: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Parse funding_need string to extract amount (in cents) and currency.
    
    Examples:
    - "10,000 cedis" -> (1000000, "GHS")
    - "5000 GHS" -> (500000, "GHS")
    - "$5,000" -> (500000, "USD")
    - "10000" -> (1000000, "GHS")  # Default to GHS if no currency specified
    
    Returns:
        Tuple of (amount_in_cents, currency_code) or (None, None) if parsing fails
    """
    if not funding_need or not funding_need.strip():
        return None, None
    
    funding_need_lower = funding_need.lower().strip()
    
    # Currency detection
    currency = None
    if 'ghs' in funding_need_lower or 'cedi' in funding_need_lower or 'cedis' in funding_need_lower:
        currency = 'GHS'
    elif 'usd' in funding_need_lower or '$' in funding_need:
        currency = 'USD'
    elif 'eur' in funding_need_lower or '€' in funding_need:
        currency = 'EUR'
    elif 'gbp' in funding_need_lower or '£' in funding_need:
        currency = 'GBP'
    else:
        # Default to GHS if no currency specified (common for Ghana-based users)
        currency = 'GHS'
    
    # Extract numbers (handle commas, spaces, etc.)
    # Remove currency symbols and commas, then extract numbers
    cleaned_str = funding_need.replace(',', '').replace('$', '').replace('€', '').replace('£', '').strip()
    numbers = re.findall(r'\d+', cleaned_str)
    
    if not numbers:
        return None, None
    
    try:
        # Get the first/largest number (usually the amount)
        amount_base = int(numbers[0])
        # Convert to cents
        amount_cents = amount_base * 100
        return amount_cents, currency
    except (ValueError, IndexError):
        return None, None


class ProjectCreate(BaseModel):
    name: str
    description: str
    stage: str
    funding_need: str
    urgency: str
    founder_type: str | None = None
    timeline_constraints: str | None = None
    # New profile fields (optional - progressive enhancement)
    organization_country: str | None = None  # ISO 2-letter country code
    organization_type: str | None = None  # e.g., "NGO", "Research Institution", "Government Agency"
    funding_need_amount: int | None = None  # Amount in cents
    funding_need_currency: str | None = None  # ISO 3-letter currency code (USD, GHS, etc.)
    has_prior_grants: bool | None = None
    profile_metadata: dict | None = None  # JSONB for flexible additional data

    @field_validator('description')
    @classmethod
    def validate_description_word_limit(cls, v: str) -> str:
        """Validate description is within 100 word limit."""
        if not v or not v.strip():
            return v
        words = v.strip().split()
        if len(words) > 100:
            # Truncate to 100 words
            truncated = ' '.join(words[:100])
            return truncated
        return v


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    stage: str | None = None
    funding_need: str | None = None
    urgency: str | None = None
    founder_type: str | None = None
    timeline_constraints: str | None = None
    organization_country: str | None = None
    organization_type: str | None = None
    funding_need_amount: int | None = None
    funding_need_currency: str | None = None
    has_prior_grants: bool | None = None
    profile_metadata: dict | None = None

    @field_validator('description')
    @classmethod
    def validate_description_word_limit(cls, v: str | None) -> str | None:
        """Validate description is within 100 word limit."""
        if not v or not v.strip():
            return v
        
        words = v.strip().split()
        if len(words) > 100:
            # Truncate to 100 words
            truncated = ' '.join(words[:100])
            return truncated
        return v


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    stage: str
    funding_need: str
    urgency: str
    founder_type: str | None
    timeline_constraints: str | None
    # New profile fields
    organization_country: str | None
    organization_type: str | None
    
    @field_validator('description')
    @classmethod
    def validate_description_word_limit(cls, v: str | None) -> str | None:
        """Validate description is within 100 word limit."""
        if not v or not v.strip():
            return v
        
        words = v.strip().split()
        if len(words) > 100:
            # Truncate to 100 words
            truncated = ' '.join(words[:100])
            return truncated
        return v
    funding_need_amount: int | None
    funding_need_currency: str | None
    has_prior_grants: bool | None
    profile_metadata: dict | None
    created_at: datetime
    updated_at: datetime | None
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime | None, _info):
        """Serialize datetime to ISO format string."""
        return value.isoformat() if value else None
    
    class Config:
        from_attributes = True


def has_paid_assessment(user_id: int, db: Session) -> bool:
    """Check if user has at least one paid assessment."""
    paid_purchase = db.query(models.AssessmentPurchase).join(
        models.Evaluation, models.AssessmentPurchase.evaluation_id == models.Evaluation.id
    ).filter(
        models.Evaluation.user_id == user_id,
        models.AssessmentPurchase.purchase_type == "paid"
    ).first()
    return paid_purchase is not None


def check_profile_completeness(project: models.Project) -> dict:
    """
    Check project profile completeness for paid assessments.
    
    Returns dict with:
    - is_complete: bool (has minimum required fields)
    - confidence: str (high/medium/low)
    - missing_fields: list of missing field names
    - completeness_score: float (0.0-1.0)
    """
    # Minimum required fields for paid assessment (soft validation)
    required_fields = {
        "description": project.description and len(project.description.strip()) > 0,
        "stage": project.stage and project.stage.strip() != "Not specified",
        "organization_country": project.organization_country is not None,
        "funding_need_amount": project.funding_need_amount is not None,
    }
    
    # Optional but improves confidence
    optional_fields = {
        "organization_type": project.organization_type is not None,
        "funding_need_currency": project.funding_need_currency is not None,
        "has_prior_grants": project.has_prior_grants is not None,
    }
    
    missing_required = [field for field, present in required_fields.items() if not present]
    missing_optional = [field for field, present in optional_fields.items() if not present]
    
    # Calculate completeness score
    required_count = sum(required_fields.values())
    optional_count = sum(optional_fields.values())
    completeness_score = (required_count / len(required_fields)) * 0.7 + (optional_count / len(optional_fields)) * 0.3
    
    # Determine confidence
    if len(missing_required) == 0 and len(missing_optional) <= 1:
        confidence = "high"
    elif len(missing_required) == 0:
        confidence = "medium"
    else:
        confidence = "low"
    
    return {
        "is_complete": len(missing_required) == 0,
        "confidence": confidence,
        "missing_fields": missing_required + missing_optional,
        "completeness_score": round(completeness_score, 2),
        "missing_required": missing_required,
        "missing_optional": missing_optional,
    }


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new project.
    
    Uses progressive enhancement approach:
    - Minimum fields: name, description, stage, funding_need, urgency
    - Additional fields improve confidence for paid assessments
    - No hard gating - users can create projects anytime
    """
    # Sanitize user inputs to prevent XSS
    project_dict = project_data.model_dump()
    project_dict['name'] = sanitize_text(project_dict.get('name', ''))
    project_dict['description'] = sanitize_html(project_dict.get('description', '')) if project_dict.get('description') else ''
    project_dict['timeline_constraints'] = sanitize_html(project_dict.get('timeline_constraints', '')) if project_dict.get('timeline_constraints') else None
    
    # Auto-parse funding_need if amount/currency not provided
    if not project_dict.get('funding_need_amount') and project_dict.get('funding_need'):
        parsed_amount, parsed_currency = parse_funding_need(project_dict['funding_need'])
        if parsed_amount and parsed_currency:
            project_dict['funding_need_amount'] = parsed_amount
            if not project_dict.get('funding_need_currency'):
                project_dict['funding_need_currency'] = parsed_currency
    
    db_project = models.Project(
        user_id=current_user.id,
        **project_dict
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all projects for the current user."""
    projects = db.query(models.Project).filter(
        models.Project.user_id == current_user.id
    ).all()
    
    # Backfill funding_need_amount/currency for projects that have funding_need string but missing parsed values
    for project in projects:
        if project.funding_need and project.funding_need.strip() != "Not specified" and not project.funding_need_amount:
            parsed_amount, parsed_currency = parse_funding_need(project.funding_need)
            if parsed_amount and parsed_currency:
                project.funding_need_amount = parsed_amount
                project.funding_need_currency = parsed_currency
                db.commit()
    
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific project."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


@router.get("/{project_id}/completeness")
async def get_project_completeness(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check project profile completeness for paid assessments.
    
    Returns completeness status, confidence level, and missing fields.
    Used to guide users on what information to add for better assessment quality.
    """
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return check_profile_completeness(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a project.
    
    Uses progressive enhancement - no hard gating.
    Additional fields improve confidence for paid assessments.
    """
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get update data
    update_data = project_data.model_dump(exclude_unset=True)
    
    # Sanitize user inputs
    if 'name' in update_data:
        update_data['name'] = sanitize_text(update_data['name'])
    if 'description' in update_data:
        update_data['description'] = sanitize_html(update_data['description']) if update_data.get('description') else ''
    if 'timeline_constraints' in update_data:
        update_data['timeline_constraints'] = sanitize_html(update_data['timeline_constraints']) if update_data.get('timeline_constraints') else None
    
    # Auto-parse funding_need if amount/currency not provided but funding_need is being updated
    if 'funding_need' in update_data and not update_data.get('funding_need_amount'):
        parsed_amount, parsed_currency = parse_funding_need(update_data['funding_need'])
        if parsed_amount and parsed_currency:
            update_data['funding_need_amount'] = parsed_amount
            if 'funding_need_currency' not in update_data:
                update_data['funding_need_currency'] = parsed_currency
    
    # Apply updates
    for field, value in update_data.items():
        setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    return project
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    update_data = project_data.model_dump(exclude_unset=True)
    # Sanitize user inputs
    if 'name' in update_data:
        update_data['name'] = sanitize_text(update_data['name'])
    if 'description' in update_data:
        update_data['description'] = sanitize_html(update_data['description']) if update_data['description'] else ''
    if 'timeline_constraints' in update_data:
        update_data['timeline_constraints'] = sanitize_html(update_data['timeline_constraints']) if update_data.get('timeline_constraints') else None
    
    # Auto-parse funding_need if amount/currency not provided but funding_need is being updated
    if 'funding_need' in update_data and not update_data.get('funding_need_amount'):
        parsed_amount, parsed_currency = parse_funding_need(update_data['funding_need'])
        if parsed_amount and parsed_currency:
            update_data['funding_need_amount'] = parsed_amount
            if 'funding_need_currency' not in update_data:
                update_data['funding_need_currency'] = parsed_currency
    
    for field, value in update_data.items():
        setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a project.
    
    If the project has evaluations linked to it, they will be automatically
    moved to the user's "Default Project" (created if it doesn't exist).
    This ensures no data loss while allowing project deletion.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        project = db.query(models.Project).filter(
            models.Project.id == project_id,
            models.Project.user_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Check if project has evaluations
        linked_evaluations = db.query(models.Evaluation).filter(
            models.Evaluation.project_id == project_id
        ).all()
        evaluation_count = len(linked_evaluations)
        
        # If project has evaluations, unlink them by moving to default project
        # But skip if we're deleting the Default Project itself
        if evaluation_count > 0 and project.name != "Default Project":
            # Get or create default project for this user
            default_project = db.query(models.Project).filter(
                models.Project.user_id == current_user.id,
                models.Project.name == "Default Project"
            ).first()
            
            if not default_project:
                # Create default project if it doesn't exist
                # Use a savepoint to ensure we can rollback if needed
                savepoint = db.begin_nested()
                try:
                    default_project = models.Project(
                        user_id=current_user.id,
                        name="Default Project",
                        description="Not specified",
                        stage="Not specified",
                        funding_need="Not specified",
                        urgency="Not specified",
                        founder_type=None,
                        timeline_constraints=None
                    )
                    db.add(default_project)
                    db.flush()  # Flush to get the ID
                    
                    # Force the ID to be generated by accessing it
                    _ = default_project.id
                    
                    # Commit the savepoint to make the default project available
                    savepoint.commit()
                    
                    # Refresh to ensure we have the latest state
                    db.refresh(default_project)
                except Exception as e:
                    savepoint.rollback()
                    db.rollback()
                    logger.error(f"Failed to create default project: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create default project for evaluation migration: {str(e)}"
                    )
            
            # Verify default_project has an ID before using it
            if not default_project or not default_project.id:
                db.rollback()
                logger.error(f"Default project has no ID - default_project: {default_project}, id: {default_project.id if default_project else 'None'}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve valid default project ID for evaluation migration"
                )
            
            # Store the ID to ensure we use a valid value
            default_project_id = default_project.id
            
            # Verify ID is not None
            if default_project_id is None:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Default project ID is None - cannot migrate evaluations"
                )
            
            # Unlink evaluations from deleted project and move to default project
            # Use direct SQL update to ensure it works
            try:
                stmt = update(models.Evaluation).where(
                    models.Evaluation.id.in_([e.id for e in linked_evaluations])
                ).values(project_id=default_project_id)
                db.execute(stmt)
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to update evaluations: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to migrate evaluations to default project: {str(e)}"
                )
            
            logger.info(f"Unlinked {evaluation_count} evaluation(s) from project {project_id} and moved to default project {default_project_id}")
        elif evaluation_count > 0 and project.name == "Default Project":
            # If deleting Default Project, we need to create a new one first
            # Get another project to move evaluations to, or create a new default
            other_project = db.query(models.Project).filter(
                models.Project.user_id == current_user.id,
                models.Project.id != project_id
            ).first()
            
            if other_project:
                # Move evaluations to another project using direct SQL update
                try:
                    stmt = update(models.Evaluation).where(
                        models.Evaluation.id.in_([e.id for e in linked_evaluations])
                    ).values(project_id=other_project.id)
                    db.execute(stmt)
                    logger.info(f"Unlinked {evaluation_count} evaluation(s) from Default Project {project_id} and moved to project {other_project.id}")
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to update evaluations to other project: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to migrate evaluations to other project: {str(e)}"
                    )
            else:
                # No other projects exist - create a new default project first
                savepoint = db.begin_nested()
                try:
                    new_default_project = models.Project(
                        user_id=current_user.id,
                        name="Default Project",
                        description="Not specified",
                        stage="Not specified",
                        funding_need="Not specified",
                        urgency="Not specified",
                        founder_type=None,
                        timeline_constraints=None
                    )
                    db.add(new_default_project)
                    db.flush()
                    
                    # Force the ID to be generated by accessing it
                    _ = new_default_project.id
                    
                    # Commit the savepoint
                    savepoint.commit()
                    db.refresh(new_default_project)
                except Exception as e:
                    savepoint.rollback()
                    db.rollback()
                    logger.error(f"Failed to create replacement default project: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create replacement default project: {str(e)}"
                    )
                
                if not new_default_project or not new_default_project.id:
                    db.rollback()
                    logger.error(f"New default project has no ID - new_default_project: {new_default_project}, id: {new_default_project.id if new_default_project else 'None'}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to retrieve valid replacement default project ID"
                    )
                
                # Store the ID to ensure we use a valid value
                new_default_project_id = new_default_project.id
                
                if new_default_project_id is None:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Replacement default project ID is None - cannot migrate evaluations"
                    )
                
                # Move evaluations to new default project using direct SQL update
                try:
                    stmt = update(models.Evaluation).where(
                        models.Evaluation.id.in_([e.id for e in linked_evaluations])
                    ).values(project_id=new_default_project_id)
                    db.execute(stmt)
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to update evaluations to new default project: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to migrate evaluations to replacement default project: {str(e)}"
                    )
                
                logger.info(f"Unlinked {evaluation_count} evaluation(s) from Default Project {project_id} and moved to new Default Project {new_default_project_id}")
        
        # Delete the project
        db.delete(project)
        db.commit()
        
        # Return 204 No Content (FastAPI handles this automatically)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error deleting project {project_id} for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}"
        )

