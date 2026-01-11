"""
Grant evaluation endpoints.
"""

from typing import List, Optional, Dict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.middleware import get_rate_limiter

router = APIRouter()
limiter = get_rate_limiter()
from sqlalchemy.orm import Session
from pydantic import BaseModel, model_validator, field_serializer
from app.db.database import get_db
from app.db import models
from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.services.credit_service import CreditService
from app.services.payment_service import PaymentService
from app.services.grant_extraction_service import GrantExtractionService
from app.core.sanitization import sanitize_url
import sys
import os

# Add parent directory to path to import evaluators
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from evaluator import GrantInfo, UserContext, EvaluationResult
from llm_evaluator import LLMGrantEvaluator


class EvaluationRequest(BaseModel):
    """Request to evaluate a grant.
    
    Option A (in-memory grants): Provide grant_url, grant_id must be None
    Option B (indexed grants): Provide grant_id, grant_url must be None
    
    For Option A, users can optionally provide additional grant context to supplement
    or override extracted data (useful when AI couldn't extract key information).
    """
    grant_id: Optional[int] = None  # For indexed grants (existing grants in DB)
    grant_url: Optional[str] = None  # For in-memory grants (Option A - no DB grant)
    project_id: Optional[int] = None  # Optional - will auto-create default project if not provided
    use_llm: bool = True
    payment_reference: Optional[str] = None  # Required if no free assessment available (Paystack reference)
    
    # Optional grant context fields (for supplementing/extending extracted data)
    grant_name: Optional[str] = None
    grant_description: Optional[str] = None
    grant_deadline: Optional[str] = None
    grant_decision_date: Optional[str] = None
    grant_award_amount: Optional[str] = None
    grant_award_structure: Optional[str] = None
    grant_eligibility: Optional[str] = None
    grant_preferred_applicants: Optional[str] = None
    grant_application_requirements: Optional[List[str]] = None
    grant_reporting_requirements: Optional[str] = None
    grant_restrictions: Optional[List[str]] = None
    grant_mission: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_grant_input(self):
        """Validate that exactly one of grant_id or grant_url is provided."""
        if (self.grant_id is None) == (self.grant_url is None):
            raise ValueError("Exactly one of 'grant_id' or 'grant_url' must be provided")
        return self


class RefinementRequest(BaseModel):
    evaluation_id: int
    project_id: Optional[int] = None  # Optional - will use existing project from original evaluation
    payment_reference: str  # Required Paystack reference for refinement payment


class EvaluationResponse(BaseModel):
    id: int
    grant_id: Optional[int]  # None for Option A (in-memory grants)
    grant_url: Optional[str]  # Set for Option A, None for Option B
    grant_name: Optional[str]  # Grant name at time of evaluation
    grant_snapshot_json: Optional[Dict]  # Full grant snapshot for Option A
    project_id: int
    timeline_viability: int
    winner_pattern_match: int
    mission_alignment: int
    application_burden: int
    award_structure: int
    composite_score: int
    recommendation: str
    reasoning: dict
    key_insights: Optional[List[str]]
    red_flags: Optional[List[str]]
    confidence_notes: Optional[str]
    evaluator_type: str
    evaluation_tier: str
    parent_evaluation_id: Optional[int]
    is_refinement: bool
    created_at: datetime
    # Paid-tier fields (extracted from reasoning["_paid_tier"] if present)
    success_probability_range: Optional[str] = None
    decision_gates: Optional[List[str]] = None
    pattern_knowledge: Optional[str] = None
    opportunity_cost: Optional[str] = None
    confidence_index: Optional[float] = None
    
    @model_validator(mode='before')
    @classmethod
    def extract_paid_tier_fields(cls, data):
        """Extract paid-tier fields from reasoning JSON before validation."""
        if isinstance(data, dict):
            reasoning = data.get('reasoning') or {}
            if isinstance(reasoning, dict) and '_paid_tier' in reasoning:
                paid_tier = reasoning['_paid_tier']
                data['success_probability_range'] = paid_tier.get('success_probability_range')
                data['decision_gates'] = paid_tier.get('decision_gates')
                data['pattern_knowledge'] = paid_tier.get('pattern_knowledge')
                data['opportunity_cost'] = paid_tier.get('opportunity_cost')
                data['confidence_index'] = paid_tier.get('confidence_index')
        elif hasattr(data, 'reasoning'):
            # SQLAlchemy model
            reasoning = data.reasoning or {}
            if isinstance(reasoning, dict) and '_paid_tier' in reasoning:
                paid_tier = reasoning['_paid_tier']
                data.success_probability_range = paid_tier.get('success_probability_range')
                data.decision_gates = paid_tier.get('decision_gates')
                data.pattern_knowledge = paid_tier.get('pattern_knowledge')
                data.opportunity_cost = paid_tier.get('opportunity_cost')
                data.confidence_index = paid_tier.get('confidence_index')
        return data
    
    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime, _info):
        """Serialize datetime to ISO format string."""
        return value.isoformat() if value else None
    
    class Config:
        from_attributes = True


@router.post("/", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def evaluate_grant(
    request: Request,
    evaluation_request: EvaluationRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evaluate a grant for a project.
    
    Requires either:
    - Free assessment available, OR
    - Valid payment_intent_id with succeeded payment
    """
    # Check payment/credit status
    has_free = CreditService.has_free_assessment_available(current_user.id, db)
    payment_id = None
    used_bundle_credit = False
    
    if not has_free:
        # Check for bundle credits first
        bundle_payment = CreditService.has_bundle_credits_available(current_user.id, db)
        
        if bundle_payment:
            # User has bundle credits available - use them
            payment_id = bundle_payment.id
            used_bundle_credit = True
        elif evaluation_request.payment_reference:
            # User provided payment reference - verify payment
            payment = db.query(models.Payment).filter(
                models.Payment.paystack_reference == evaluation_request.payment_reference,
                models.Payment.user_id == current_user.id,
                models.Payment.status == "succeeded"
            ).first()
            
            if not payment:
                # Try to verify transaction with Paystack
                payment = PaymentService.verify_transaction(evaluation_request.payment_reference, db)
                if not payment or payment.user_id != current_user.id or payment.status != "succeeded":
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail="Payment not found or not completed. Please complete payment first."
                    )
            
            payment_id = payment.id
        else:
            # No free assessment, no bundle credits, and no payment reference
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Payment required. Free assessment not available. Please initialize payment first or use bundle credits if available."
            )
    
    # Get grant info - either from DB (grant_id) or extract from URL (grant_url)
    grant_info = None
    grant_snapshot = None
    grant_name = None
    grant_url = None
    grant_id = None
    
    if evaluation_request.grant_url:
        # Option A: In-memory grant (extract from URL, don't create DB grant)
        try:
            validated_url = sanitize_url(evaluation_request.grant_url)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or dangerous URL: {str(e)}"
            )
        
        # Extract grant information
        extraction_service = GrantExtractionService()
        try:
            extracted_data = extraction_service.extract_grant_from_url(validated_url)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to extract grant information from URL: {str(e)}"
            )
        
        # Store snapshot for evaluation (before user overrides)
        grant_snapshot = extracted_data.copy()
        grant_url = validated_url
        
        # Merge user-provided context with extracted data (user data takes precedence)
        # This allows users to supplement or override extracted information
        final_grant_data = {
            'name': evaluation_request.grant_name or extracted_data.get('name') or "Grant from URL",
            'description': evaluation_request.grant_description or extracted_data.get('description') or "",
            'deadline': evaluation_request.grant_deadline or extracted_data.get('deadline'),
            'decision_date': evaluation_request.grant_decision_date or extracted_data.get('decision_date'),
            'award_amount': evaluation_request.grant_award_amount or extracted_data.get('award_amount'),
            'award_structure': evaluation_request.grant_award_structure or extracted_data.get('award_structure'),
            'eligibility': evaluation_request.grant_eligibility or extracted_data.get('eligibility'),
            'application_requirements': evaluation_request.grant_application_requirements or extracted_data.get('application_requirements') or [],
            'reporting_requirements': evaluation_request.grant_reporting_requirements or extracted_data.get('reporting_requirements'),
            'restrictions': evaluation_request.grant_restrictions or extracted_data.get('restrictions') or [],
            'preferred_applicants': evaluation_request.grant_preferred_applicants or extracted_data.get('preferred_applicants'),
            'mission': evaluation_request.grant_mission or extracted_data.get('mission'),
        }
        
        # Update snapshot with final merged data
        grant_snapshot.update(final_grant_data)
        grant_name = final_grant_data['name']
        
        # Convert to GrantInfo format
        grant_info = GrantInfo(
            name=final_grant_data['name'],
            description=final_grant_data['description'],
            deadline=final_grant_data['deadline'],
            decision_date=final_grant_data['decision_date'],
            award_amount=final_grant_data['award_amount'],
            award_structure=final_grant_data['award_structure'],
            eligibility=final_grant_data['eligibility'],
            application_requirements=final_grant_data['application_requirements'],
            reporting_requirements=final_grant_data['reporting_requirements'],
            restrictions=final_grant_data['restrictions'],
            preferred_applicants=final_grant_data['preferred_applicants'],
            mission=final_grant_data['mission'],
        )
    else:
        # Option B: Indexed grant (use existing grant from DB)
        grant = db.query(models.Grant).filter(models.Grant.id == evaluation_request.grant_id).first()
        if not grant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grant not found"
            )
        
        grant_id = grant.id
        grant_name = grant.name
        
        # Convert to evaluator format
        grant_info = GrantInfo(
            name=grant.name,
            description=grant.description or "",
            deadline=grant.deadline,
            decision_date=grant.decision_date,
            award_amount=grant.award_amount,
            award_structure=grant.award_structure,
            eligibility=grant.eligibility,
            application_requirements=grant.application_requirements or [],
            reporting_requirements=grant.reporting_requirements,
            restrictions=grant.restrictions or [],
            preferred_applicants=grant.preferred_applicants,
            mission=grant.mission,
        )
    
    # Get or create project
    if evaluation_request.project_id:
        # Use provided project (must belong to current user)
        project = db.query(models.Project).filter(
            models.Project.id == evaluation_request.project_id,
            models.Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied"
            )
    else:
        # Auto-create default project for minimal context (first assessment)
        # Check if user already has a default project
        default_project = db.query(models.Project).filter(
            models.Project.user_id == current_user.id,
            models.Project.name == "Default Project"
        ).first()
        
        if default_project:
            project = default_project
        else:
            # Create default project with "Not specified" values
            project = models.Project(
                user_id=current_user.id,
                name="Default Project",
                description="Not specified",
                stage="Not specified",
                funding_need="Not specified",
                urgency="Not specified",
                founder_type=None,
                timeline_constraints=None
            )
            db.add(project)
            db.commit()
            db.refresh(project)
    
    # grant_info is already created above (either from URL extraction or DB grant)
    user_context = UserContext(
        project_stage=project.stage,
        funding_need=project.funding_need,
        urgency=project.urgency,
        project_description=project.description,
        founder_type=project.founder_type,
        timeline_constraints=project.timeline_constraints,
    )
    
    # Determine evaluation tier
    # Free assessments are "free" tier (conservative defaults)
    # Paid assessments (including bundle credits) are "standard" tier
    # Only use "free" if it's actually a free assessment, not bundle credits
    if has_free and not used_bundle_credit:
        evaluation_tier = "free"
    else:
        evaluation_tier = "standard"
    
    # Run evaluation with tier information
    if evaluation_request.use_llm:
        try:
            evaluator = LLMGrantEvaluator(api_key=settings.ANTHROPIC_API_KEY)
            result = evaluator.evaluate(grant_info, user_context, evaluation_tier=evaluation_tier)
            evaluator_type = "llm"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM evaluation failed: {str(e)}"
            )
    else:
        from evaluator import GrantEvaluator
        evaluator = GrantEvaluator()
        result = evaluator.evaluate(grant_info, user_context)
        evaluator_type = "rule_based"
    
    # For free tier, use minimal project context (conservative defaults)
    # This is already handled by the default project creation above
    
    # Store paid-tier fields in reasoning JSON for now (can be moved to separate column later)
    reasoning_with_paid_tier = result.reasoning.copy()
    if result.success_probability_range or result.decision_gates or result.pattern_knowledge or result.opportunity_cost or result.confidence_index is not None:
        reasoning_with_paid_tier["_paid_tier"] = {
            "success_probability_range": result.success_probability_range,
            "decision_gates": result.decision_gates,
            "pattern_knowledge": result.pattern_knowledge,
            "opportunity_cost": result.opportunity_cost,
            "confidence_index": result.confidence_index,
        }
    
    # Save evaluation to database
    db_evaluation = models.Evaluation(
        user_id=current_user.id,
        project_id=project.id,
        grant_id=grant_id,  # None for Option A (in-memory grants), set for Option B (indexed grants)
        grant_url=grant_url,  # Set for Option A, None for Option B
        grant_name=grant_name,  # Grant name at time of evaluation
        grant_snapshot_json=grant_snapshot,  # Full grant data snapshot (immutable) for Option A
        timeline_viability=int(result.scores.timeline_viability),
        winner_pattern_match=int(result.scores.winner_pattern_match),
        mission_alignment=int(result.scores.mission_alignment),
        application_burden=int(result.scores.application_burden),
        award_structure=int(result.scores.award_structure),
        composite_score=int(result.composite_score),
        recommendation=result.recommendation.value,
        reasoning=reasoning_with_paid_tier,
        key_insights=result.key_insights,
        red_flags=result.red_flags,
        confidence_notes=result.confidence_notes,
        evaluator_type=evaluator_type,
        evaluation_tier=evaluation_tier,
        is_refinement=False,
        parent_evaluation_id=None,
    )
    db.add(db_evaluation)
    db.commit()
    db.refresh(db_evaluation)
    
    # Link to payment or use free assessment
    if has_free:
        CreditService.use_free_assessment(current_user.id, db_evaluation.id, db)
    else:
        PaymentService.link_payment_to_assessment(
            payment_id=payment_id,
            user_id=current_user.id,
            evaluation_id=db_evaluation.id,
            db=db
        )
    
    return db_evaluation


@router.get("/", response_model=List[EvaluationResponse])
async def list_evaluations(
    project_id: Optional[int] = None,
    grant_id: Optional[int] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List evaluations the user can access.
    
    Only returns assessments the user has purchased (free or paid).
    Each assessment requires payment (except the first free one).
    Users can view assessments they've paid for, but must pay for each new assessment.
    """
    try:
        # Get all evaluations user owns
        query = db.query(models.Evaluation).filter(models.Evaluation.user_id == current_user.id)
        
        if project_id:
            query = query.filter(models.Evaluation.project_id == project_id)
        if grant_id:
            query = query.filter(models.Evaluation.grant_id == grant_id)
        
        all_evaluations = query.order_by(models.Evaluation.created_at.desc()).all()
        
        # Filter to only include assessments user has purchased (free or paid)
        accessible_evaluations = []
        for evaluation in all_evaluations:
            try:
                if CreditService.can_access_evaluation(current_user.id, evaluation.id, db):
                    accessible_evaluations.append(evaluation)
            except Exception as e:
                # Log error but continue processing other evaluations
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error checking access for evaluation {evaluation.id}: {str(e)}", exc_info=True)
                # Skip this evaluation if access check fails
                continue
        
        return accessible_evaluations
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error listing evaluations for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list evaluations: {str(e)}"
        )


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific evaluation.
    
    Users can only access assessments they have purchased (free or paid).
    Each assessment requires payment (except the first free one).
    Users can view assessments they've paid for, but must pay for each new assessment.
    """
    try:
        evaluation = db.query(models.Evaluation).filter(
            models.Evaluation.id == evaluation_id
        ).first()
        
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evaluation not found"
            )
        
        # Check access - user must own it and have purchase record
        try:
            has_access = CreditService.can_access_evaluation(current_user.id, evaluation_id, db)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error checking access for evaluation {evaluation_id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error checking access: {str(e)}"
            )
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You do not have permission to view this evaluation."
            )
        
        return evaluation
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting evaluation {evaluation_id} for user {current_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get evaluation: {str(e)}"
        )


@router.post("/refine", response_model=EvaluationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def refine_evaluation(
    request: Request,
    refinement_request: RefinementRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refine a free tier evaluation with full project context.
    
    Requires:
    - Original evaluation must be free tier
    - Valid payment reference for $3 refinement payment
    - Payment must be type "refinement" and succeeded
    """
    # Get original evaluation
    original_eval = db.query(models.Evaluation).filter(
        models.Evaluation.id == refinement_request.evaluation_id,
        models.Evaluation.user_id == current_user.id
    ).first()
    
    if not original_eval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original evaluation not found or access denied"
        )
    
    # Check if original is free tier
    if original_eval.evaluation_tier != "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only free tier evaluations can be refined"
        )
    
    # Check if already refined
    existing_refinement = db.query(models.Evaluation).filter(
        models.Evaluation.parent_evaluation_id == original_eval.id,
        models.Evaluation.user_id == current_user.id
    ).first()
    
    if existing_refinement:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This evaluation has already been refined"
        )
    
    # Verify payment
    payment = db.query(models.Payment).filter(
        models.Payment.paystack_reference == refinement_request.payment_reference,
        models.Payment.user_id == current_user.id,
        models.Payment.status == "succeeded",
        models.Payment.payment_type == "refinement"
    ).first()
    
    if not payment:
        # Try to verify transaction with Paystack
        payment = PaymentService.verify_transaction(refinement_request.payment_reference, db)
        if not payment or payment.user_id != current_user.id or payment.status != "succeeded" or payment.payment_type != "refinement":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Valid refinement payment required. Please complete payment first."
            )
    
    # Get grant
    grant = db.query(models.Grant).filter(models.Grant.id == original_eval.grant_id).first()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grant not found"
        )
    
    # Get project (use provided or original evaluation's project)
    if refinement_request.project_id:
        project = db.query(models.Project).filter(
            models.Project.id == refinement_request.project_id,
            models.Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied"
            )
    else:
        # Use original evaluation's project
        project = db.query(models.Project).filter(
            models.Project.id == original_eval.project_id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
    
    # Convert to evaluator format
    grant_info = GrantInfo(
        name=grant.name,
        description=grant.description or "",
        deadline=grant.deadline,
        decision_date=grant.decision_date,
        award_amount=grant.award_amount,
        award_structure=grant.award_structure,
        eligibility=grant.eligibility,
        application_requirements=grant.application_requirements or [],
        reporting_requirements=grant.reporting_requirements,
        restrictions=grant.restrictions or [],
        preferred_applicants=grant.preferred_applicants,
        mission=grant.mission,
    )
    
    # Use full project context for refinement
    user_context = UserContext(
        project_stage=project.stage,
        funding_need=project.funding_need,
        urgency=project.urgency,
        project_description=project.description,
        founder_type=project.founder_type,
        timeline_constraints=project.timeline_constraints,
    )
    
    # Run evaluation with full context
    try:
        evaluator = LLMGrantEvaluator(api_key=settings.ANTHROPIC_API_KEY)
        result = evaluator.evaluate(grant_info, user_context)
        evaluator_type = "llm"
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM evaluation failed: {str(e)}"
        )
    
    # Save refined evaluation
    refined_eval = models.Evaluation(
        user_id=current_user.id,
        project_id=project.id,
        grant_id=grant.id,
        timeline_viability=int(result.scores.timeline_viability),
        winner_pattern_match=int(result.scores.winner_pattern_match),
        mission_alignment=int(result.scores.mission_alignment),
        application_burden=int(result.scores.application_burden),
        award_structure=int(result.scores.award_structure),
        composite_score=int(result.composite_score),
        recommendation=result.recommendation.value,
        reasoning=result.reasoning,
        key_insights=result.key_insights,
        red_flags=result.red_flags,
        confidence_notes=result.confidence_notes,
        evaluator_type=evaluator_type,
        evaluation_tier="refined",
        is_refinement=True,
        parent_evaluation_id=original_eval.id,
    )
    db.add(refined_eval)
    db.commit()
    db.refresh(refined_eval)
    
    # Link payment to refined evaluation
    PaymentService.link_payment_to_assessment(
        payment_id=payment.id,
        user_id=current_user.id,
        evaluation_id=refined_eval.id,
        db=db
    )
    
    return refined_eval

