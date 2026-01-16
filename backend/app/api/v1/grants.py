"""
Grant management endpoints.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel, field_serializer
from app.db.database import get_db
from app.db import models
from app.api.v1.auth import get_current_user
from app.services.grant_extraction_service import GrantExtractionService
from app.core.config import settings
from app.core.sanitization import sanitize_html, sanitize_text, sanitize_url
from app.services.slack_service import send_grant_approval_notification
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class GrantCreate(BaseModel):
    name: str
    description: Optional[str] = None
    mission: Optional[str] = None
    deadline: Optional[str] = None
    decision_date: Optional[str] = None
    award_amount: Optional[str] = None
    award_structure: Optional[str] = None
    eligibility: Optional[str] = None
    preferred_applicants: Optional[str] = None
    application_requirements: Optional[List[str]] = None
    reporting_requirements: Optional[str] = None
    restrictions: Optional[List[str]] = None
    source_url: Optional[str] = None


class GrantCreateFromURL(BaseModel):
    """Create grant from URL - minimal info, prompts for name."""
    source_url: str
    name: Optional[str] = None  # If not provided, will use URL as name


class GrantExtractionResponse(BaseModel):
    """Response for grant extraction (no DB creation)."""
    name: Optional[str] = None
    description: Optional[str] = None
    mission: Optional[str] = None
    deadline: Optional[str] = None
    decision_date: Optional[str] = None
    award_amount: Optional[str] = None
    award_structure: Optional[str] = None
    eligibility: Optional[str] = None
    preferred_applicants: Optional[str] = None
    application_requirements: Optional[List[str]] = None
    reporting_requirements: Optional[str] = None
    restrictions: Optional[List[str]] = None
    source_url: str


class GrantNormalizationResponse(BaseModel):
    """Normalization fields for grant presentation."""
    canonical_title: Optional[str] = None
    canonical_summary: Optional[str] = None
    timeline_status: Optional[str] = None  # 'active', 'closed', 'rolling', 'unknown'
    confidence_level: Optional[str] = None  # 'high', 'medium', 'low'
    
    class Config:
        from_attributes = True


class GrantResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    mission: Optional[str]
    deadline: Optional[str]
    decision_date: Optional[str]
    award_amount: Optional[str]
    award_structure: Optional[str]
    eligibility: Optional[str]
    preferred_applicants: Optional[str]
    application_requirements: Optional[List[str]]
    reporting_requirements: Optional[str]
    restrictions: Optional[List[str]]
    source_url: Optional[str]
    approval_status: str
    created_at: datetime
    # Normalization fields (optional - only if normalization exists and is approved)
    normalization: Optional[GrantNormalizationResponse] = None
    
    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime, _info):
        """Serialize datetime to ISO format string."""
        return value.isoformat() if value else None
    
    class Config:
        from_attributes = True


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require admin (superuser) access."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.post("/", response_model=GrantResponse, status_code=status.HTTP_201_CREATED)
async def create_grant(
    grant_data: GrantCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new grant."""
    # Sanitize user inputs to prevent XSS
    grant_dict = grant_data.model_dump()
    grant_dict['name'] = sanitize_text(grant_dict.get('name', ''))
    grant_dict['description'] = sanitize_html(grant_dict.get('description', '')) if grant_dict.get('description') else None
    grant_dict['mission'] = sanitize_html(grant_dict.get('mission', '')) if grant_dict.get('mission') else None
    
    # Validate and sanitize URL if provided
    if grant_dict.get('source_url'):
        try:
            grant_dict['source_url'] = sanitize_url(grant_dict.get('source_url', ''))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or dangerous URL: {str(e)}"
            )
    else:
        grant_dict['source_url'] = None
    
    # All new grants require admin approval
    grant_dict['approval_status'] = 'pending'
    
    # Store raw data (immutable source of record)
    # For manual creation, use provided name/description as raw data
    if not grant_dict.get('raw_title'):
        grant_dict['raw_title'] = grant_dict.get('name') or ''
    if not grant_dict.get('raw_content'):
        grant_dict['raw_content'] = grant_dict.get('description') or grant_dict.get('mission') or ''
    if not grant_dict.get('fetched_at'):
        grant_dict['fetched_at'] = datetime.now(timezone.utc)
    
    db_grant = models.Grant(**grant_dict)
    db.add(db_grant)
    db.commit()
    db.refresh(db_grant)
    
    # Generate draft normalization (non-blocking, for Slack notification)
    draft_normalization = None
    try:
        from app.services.normalization_service import NormalizationService
        normalization_service = NormalizationService()
        
        # Prepare grant dict for normalization service
        grant_data_dict = {
            'name': db_grant.name,
            'description': db_grant.description,
            'mission': db_grant.mission,
            'deadline': db_grant.deadline,
            'decision_date': db_grant.decision_date,
            'award_amount': db_grant.award_amount,
        }
        
        # Generate draft normalization
        draft_normalization = normalization_service.generate_normalization(grant_data_dict)
    except Exception as e:
        logger.warning(f"Failed to generate draft normalization for grant {db_grant.id}: {e}", exc_info=True)
        # Non-critical - continue without normalization
    
    # Send Slack notification for admin approval (non-blocking)
    # This happens for both successful extraction and fallback creation
    try:
        send_grant_approval_notification(
            grant_id=db_grant.id,
            grant_name=db_grant.name,
            grant_url=db_grant.source_url or "",
            draft_normalization=draft_normalization
        )
    except Exception as e:
        logger.error(f"Exception sending Slack notification for grant {db_grant.id}: {e}", exc_info=True)
        # Non-critical, continue - grant is still created
    
    return db_grant


@router.post("/from-url", response_model=GrantResponse, status_code=status.HTTP_201_CREATED)
async def create_grant_from_url(
    grant_data: GrantCreateFromURL,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Auto-create grant from URL using web scraping and Claude API extraction.
    
    This endpoint:
    1. Validates URL security (SSRF protection)
    2. Scrapes the grant page content
    3. Uses Claude API to extract structured grant information
    4. Creates a grant record with extracted details
    
    If extraction fails, falls back to creating a basic grant with URL.
    """
    # Validate and sanitize URL first (security check)
    try:
        validated_url = sanitize_url(grant_data.source_url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or dangerous URL: {str(e)}"
        )
    
    # Helper function to handle list or string values for Text fields
    def sanitize_text_field(value):
        """Convert list to string if needed, then sanitize."""
        if not value:
            return None
        if isinstance(value, list):
            # Join list items with newlines for readability
            value = '\n'.join(str(item) for item in value if item)
        if not value:
            return None
        return sanitize_html(str(value))
    
    # Helper function for plain text fields (non-HTML)
    def sanitize_plain_text_field(value):
        """Convert list to string if needed, then sanitize as plain text."""
        if not value:
            return None
        if isinstance(value, list):
            # Join list items with newlines
            value = '\n'.join(str(item) for item in value if item)
        if not value:
            return None
        return sanitize_text(str(value))
    
    db_grant = None
    try:
        # Initialize extraction service
        extraction_service = GrantExtractionService()
        
        # Extract grant information from validated URL
        extracted_data = extraction_service.extract_grant_from_url(validated_url)
        
        # Use provided name if given, otherwise use extracted name
        name = grant_data.name or extracted_data.get('name') or "Grant from URL"
        
        # Validate extracted source_url if present
        extracted_url = extracted_data.get('source_url') or validated_url
        try:
            extracted_url = sanitize_url(extracted_url)
        except ValueError:
            # If extracted URL is invalid, use the validated input URL
            extracted_url = validated_url
        
        # Create grant with extracted data
        db_grant = models.Grant(
            name=sanitize_text(name),
            description=sanitize_text_field(extracted_data.get('description')),
            mission=sanitize_text_field(extracted_data.get('mission')),
            deadline=sanitize_plain_text_field(extracted_data.get('deadline')),
            decision_date=sanitize_plain_text_field(extracted_data.get('decision_date')),
            award_amount=sanitize_plain_text_field(extracted_data.get('award_amount')),
            award_structure=sanitize_text_field(extracted_data.get('award_structure')),
            eligibility=sanitize_text_field(extracted_data.get('eligibility')),
            preferred_applicants=sanitize_text_field(extracted_data.get('preferred_applicants')),
            application_requirements=[sanitize_text(req) for req in (extracted_data.get('application_requirements') or [])],
            reporting_requirements=sanitize_text_field(extracted_data.get('reporting_requirements')),
            restrictions=[sanitize_text(res) for res in (extracted_data.get('restrictions') or [])],
            source_url=extracted_url,
            approval_status='pending',  # All new grants require admin approval
        )
        
    except Exception as e:
        # If extraction fails, create basic grant with validated URL
        # This allows the user to manually fill in details
        name = grant_data.name
        if not name:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(validated_url)
                name = f"{parsed.netloc}{parsed.path}".replace('/', ' ').strip()[:100]
                if not name:
                    name = "Grant from URL"
            except:
                name = "Grant from URL"
        
        # For fallback case, still store raw data (even if minimal)
        raw_title = name
        raw_content = ''  # No content scraped in fallback case
        fetched_at = datetime.now(timezone.utc)
        
        db_grant = models.Grant(
            name=sanitize_text(name),
            source_url=validated_url,  # Use validated URL, not original
            description=None,  # User can fill in later
            # Raw data fields (immutable source of record)
            raw_title=raw_title,
            raw_content=raw_content,
            fetched_at=fetched_at,
            approval_status='pending',  # All new grants require admin approval
        )
        
        # Log the error but don't fail - allow manual entry
        # In production, you might want to log this to a monitoring service
        logger.error(f"Grant extraction failed for {validated_url}: {str(e)}", exc_info=True)
    
    db.add(db_grant)
    db.commit()
    db.refresh(db_grant)
    
    # Generate draft normalization (non-blocking, for Slack notification)
    draft_normalization = None
    try:
        from app.services.normalization_service import NormalizationService
        normalization_service = NormalizationService()
        
        # Prepare grant dict for normalization service
        grant_dict = {
            'name': db_grant.name,
            'description': db_grant.description,
            'mission': db_grant.mission,
            'deadline': db_grant.deadline,
            'decision_date': db_grant.decision_date,
            'award_amount': db_grant.award_amount,
        }
        
        # Generate draft normalization
        draft_normalization = normalization_service.generate_normalization(grant_dict)
    except Exception as e:
        logger.warning(f"Failed to generate draft normalization for grant {db_grant.id}: {e}", exc_info=True)
        # Non-critical - continue without normalization
    
    # Send Slack notification for admin approval (non-blocking)
    try:
        send_grant_approval_notification(
            grant_id=db_grant.id,
            grant_name=db_grant.name,
            grant_url=db_grant.source_url or "",
            draft_normalization=draft_normalization
        )
    except Exception as e:
        logger.error(f"Exception sending Slack notification for grant {db_grant.id}: {e}", exc_info=True)
        # Non-critical, continue - grant is still created
    
    return db_grant


@router.post("/extract", response_model=GrantExtractionResponse)
async def extract_grant_data(
    grant_data: GrantCreateFromURL,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Extract grant information from URL WITHOUT creating a grant record.
    
    This is for evaluation flow (Option A) - users can review/edit extracted data
    before evaluation. No grant is created in the database.
    
    Admin review/validation only applies to grants added to the index via /from-url.
    """
    # Validate and sanitize URL first (security check)
    try:
        validated_url = sanitize_url(grant_data.source_url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or dangerous URL: {str(e)}"
        )
    
    # Extract grant information (no DB creation)
    try:
        # Initialize extraction service (may raise ValueError if API key missing)
        try:
            extraction_service = GrantExtractionService()
        except ValueError as ve:
            # API key missing or invalid
            logger.error(f"GrantExtractionService initialization failed: {str(ve)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(ve)
            )
        except Exception as init_error:
            # Other initialization errors
            logger.error(f"GrantExtractionService initialization error: {str(init_error)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize extraction service: {str(init_error)}"
            )
        
        # Extract grant data
        try:
            extracted_data = extraction_service.extract_grant_from_url(validated_url)
        except ValueError as ve:
            # ValueError from extraction (URL validation, scraping, etc.)
            logger.error(f"Grant extraction ValueError: {str(ve)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )
        
        # Return extracted data only (no grant record created)
        return GrantExtractionResponse(
            name=extracted_data.get('name'),
            description=extracted_data.get('description'),
            mission=extracted_data.get('mission'),
            deadline=extracted_data.get('deadline'),
            decision_date=extracted_data.get('decision_date'),
            award_amount=extracted_data.get('award_amount'),
            award_structure=extracted_data.get('award_structure'),
            eligibility=extracted_data.get('eligibility'),
            preferred_applicants=extracted_data.get('preferred_applicants'),
            application_requirements=extracted_data.get('application_requirements'),
            reporting_requirements=extracted_data.get('reporting_requirements'),
            restrictions=extracted_data.get('restrictions'),
            source_url=validated_url,
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging (logger is already defined at module level)
        logger.error(f"Error extracting grant from URL {validated_url}: {str(e)}", exc_info=True)
        
        # Provide a more helpful error message
        error_detail = str(e)
        error_message = f"Failed to extract grant information from URL: {error_detail}"
        
        if "ANTHROPIC_API_KEY" in error_detail or "api key" in error_detail.lower():
            error_message = "Anthropic API key not configured. Please set ANTHROPIC_API_KEY in environment variables."
        elif "timeout" in error_detail.lower() or "connection" in error_detail.lower():
            error_message = f"Failed to fetch grant page: {error_detail}. Please check the URL and try again."
        elif "404" in error_detail or "not found" in error_detail.lower():
            error_message = "Grant page not found. Please check the URL and try again."
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )


@router.get("/", response_model=List[GrantResponse])
async def list_grants(
    skip: int = 0,
    limit: int = 100,
    include_pending: bool = False,
    current_user: Optional[models.User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List grants.
    
    Regular users: Only see approved grants.
    Admins: Can see all grants including pending if include_pending=true.
    """
    query = db.query(models.Grant).options(selectinload(models.Grant.normalization))
    
    # Regular users only see approved grants
    if not current_user or not current_user.is_superuser:
        query = query.filter(models.Grant.approval_status == 'approved')
    elif not include_pending:
        # Admins can filter by default
        query = query.filter(models.Grant.approval_status == 'approved')
    
    grants = query.order_by(models.Grant.created_at.desc()).offset(skip).limit(limit).all()
    return grants


@router.get("/pending", response_model=List[GrantResponse])
async def list_pending_grants(
    admin_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List pending grants (admin only)."""
    grants = db.query(models.Grant).filter(
        models.Grant.approval_status == 'pending'
    ).order_by(models.Grant.created_at.desc()).all()
    return grants


class GrantApprovalRequest(BaseModel):
    approval_status: str  # 'approved' or 'rejected'
    rejection_reason: Optional[str] = None


@router.post("/{grant_id}/approve", response_model=GrantResponse)
async def approve_or_reject_grant(
    grant_id: int,
    approval_request: GrantApprovalRequest,
    admin_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Approve or reject a grant (admin only)."""
    grant = db.query(models.Grant).filter(models.Grant.id == grant_id).first()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grant not found"
        )
    
    if approval_request.approval_status not in ['approved', 'rejected']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="approval_status must be 'approved' or 'rejected'"
        )
    
    grant.approval_status = approval_request.approval_status
    grant.approved_by = admin_user.id
    grant.approved_at = datetime.now()
    
    if approval_request.approval_status == 'rejected':
        grant.rejection_reason = approval_request.rejection_reason
    
    db.commit()
    db.refresh(grant)
    return grant


@router.get("/{grant_id}", response_model=GrantResponse)
async def get_grant(
    grant_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific grant."""
    grant = db.query(models.Grant).options(selectinload(models.Grant.normalization)).filter(
        models.Grant.id == grant_id
    ).first()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grant not found"
        )
    return grant

