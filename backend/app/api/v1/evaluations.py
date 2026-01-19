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
from app.services.scoring_service import ScoringService
from app.core.sanitization import sanitize_url
from datetime import date
import sys
import os

# Add parent directory to path to import evaluators
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from evaluator import GrantInfo, UserContext, EvaluationResult, Recommendation
from llm_evaluator import LLMGrantEvaluator


def format_field_name(field_name: str) -> str:
    """Convert snake_case field names to human-readable format.
    
    Examples:
        organization_country -> organization country
        funding_need_amount -> funding need amount
        organization_type -> organization type
    """
    # Map of field names to their human-readable labels
    field_labels = {
        "organization_country": "organization country",
        "funding_need_amount": "funding need amount",
        "organization_type": "organization type",
        "funding_need_currency": "funding need currency",
        "has_prior_grants": "prior grant history",
        "description": "project description",
        "stage": "project stage",
    }
    
    # Return mapped label if available, otherwise replace underscores with spaces
    return field_labels.get(field_name, field_name.replace("_", " "))


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
    winner_pattern_match: Optional[int]  # NULL for free tier (no project data)
    mission_alignment: Optional[int]  # NULL for free tier (no project data)
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
    assessment_type: str  # 'free' or 'paid' - New two-tier framework
    is_legacy: bool
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
    
    # Determine assessment type (free vs paid)
    if has_free and not used_bundle_credit:
        assessment_type = "free"
    else:
        assessment_type = "paid"
    
    # Get or create project
    # For free tier: Can use minimal/default project (grant quality doesn't need project data)
    # For paid tier: Require project with minimum data (soft validation)
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
        # Auto-create default project if needed
        default_project = db.query(models.Project).filter(
            models.Project.user_id == current_user.id,
            models.Project.name == "Default Project"
        ).first()
        
        if default_project:
            project = default_project
        else:
            # Create default project
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
    
    # Prepare grant data dict for scoring service (include recipient_patterns if available)
    grant_dict = {
        "name": grant_info.name,
        "description": grant_info.description or "",
        "mission": grant_info.mission or "",
        "deadline": grant_info.deadline,
        "decision_date": grant_info.decision_date,
        "award_amount": grant_info.award_amount,
        "award_structure": grant_info.award_structure or "",
        "eligibility": grant_info.eligibility or "",
        "preferred_applicants": grant_info.preferred_applicants or "",
        "application_requirements": grant_info.application_requirements or [],
        "reporting_requirements": grant_info.reporting_requirements or "",
        "restrictions": grant_info.restrictions or [],
    }
    
    # Add recipient_patterns if grant is from DB
    if grant_id:
        grant_db = db.query(models.Grant).filter(models.Grant.id == grant_id).first()
        if grant_db and grant_db.recipient_patterns:
            grant_dict["recipient_patterns"] = grant_db.recipient_patterns
    elif grant_snapshot and "recipient_patterns" in grant_snapshot:
        grant_dict["recipient_patterns"] = grant_snapshot.get("recipient_patterns")
    
    # Prepare project data dict for scoring service (paid tier only)
    project_dict = None
    user_context = None
    
    if assessment_type == "paid":
        # Backfill funding_need_amount/currency if missing but funding_need string exists
        funding_need_amount = project.funding_need_amount
        funding_need_currency = project.funding_need_currency
        
        if not funding_need_amount and project.funding_need and project.funding_need.strip() != "Not specified":
            from app.api.v1.projects import parse_funding_need
            parsed_amount, parsed_currency = parse_funding_need(project.funding_need)
            if parsed_amount and parsed_currency:
                # Update the project in database for future use
                project.funding_need_amount = parsed_amount
                project.funding_need_currency = parsed_currency
                db.commit()
                db.refresh(project)
                funding_need_amount = parsed_amount
                funding_need_currency = parsed_currency
        
        # Paid tier: Need project data for fit assessment
        # CRITICAL: Log project details to ensure correct project is used
        import logging
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info(f"EVALUATION PROJECT VALIDATION")
        logger.info(f"  Project ID: {project.id}")
        logger.info(f"  Project Name: {project.name}")
        logger.info(f"  Project Description (first 100 chars): {project.description[:100] if project.description else 'None'}...")
        logger.info(f"  User ID: {current_user.id}")
        logger.info(f"  Grant ID: {grant_id}")
        logger.info(f"  Grant Name: {grant_name}")
        logger.info("=" * 60)
        
        # Validate project belongs to user (double-check)
        if project.user_id != current_user.id:
            logger.error(f"SECURITY: Project {project.id} does not belong to user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project access denied"
            )
        
        project_dict = {
            "name": project.name or "",  # Include name for better context
            "description": project.description or "",
            "stage": project.stage or "",
            "funding_need": project.funding_need or "",
            "organization_country": project.organization_country,
            "organization_type": project.organization_type,
            "funding_need_amount": funding_need_amount,
            "funding_need_currency": funding_need_currency,
            "has_prior_grants": project.has_prior_grants,
            "profile_metadata": project.profile_metadata or {},
        }
        
        # Create user context for LLM
        user_context = UserContext(
            project_stage=project.stage,
            funding_need=project.funding_need,
            urgency=project.urgency,
            project_description=project.description,
            founder_type=project.founder_type,
            timeline_constraints=project.timeline_constraints,
        )
        
        # Log project data being sent to evaluator
        logger.info(f"Project data being sent to evaluator: name='{project.name}', description_length={len(project.description) if project.description else 0}")
    else:
        # Free tier: No project data needed
        user_context = None
    
    # Run evaluation with new framework
    if evaluation_request.use_llm:
        try:
            evaluator = LLMGrantEvaluator(api_key=settings.ANTHROPIC_API_KEY)
            # Pass assessment_type instead of evaluation_tier
            result = evaluator.evaluate(grant_info, user_context, assessment_type=assessment_type)
            evaluator_type = "llm"
        except Exception as e:
            # Log full error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"LLM evaluation failed for user {current_user.id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM evaluation failed: {str(e)}"
            )
    else:
        from evaluator import GrantEvaluator
        evaluator = GrantEvaluator()
        result = evaluator.evaluate(grant_info, user_context if user_context else UserContext(
            project_stage="Not specified",
            funding_need="Not specified",
            urgency="flexible",
            project_description="Not specified"
        ))
        evaluator_type = "rule_based"
    
    # Use scoring service to get deterministic scores
    scoring_service = ScoringService()
    
    # Calculate grant readiness score (for both free and paid assessments)
    readiness_result = scoring_service.calculate_grant_readiness_score(grant_dict)
    
    if assessment_type == "free":
        # Free tier: Grant quality assessment only
        clarity_result = scoring_service.calculate_clarity_score(grant_dict)
        access_barrier_result = scoring_service.assess_access_barrier(grant_dict)
        timeline_result = scoring_service.assess_timeline(grant_dict, current_date=date.today())
        award_result = scoring_service.assess_award_structure(grant_dict)
        competition_result = scoring_service.assess_competition(grant_dict)
        
        # Convert access barrier level to score for composite calculation
        access_barrier_score = 2 if access_barrier_result.level == "HIGH" else (6 if access_barrier_result.level == "MEDIUM" else 10)
        
        # Calculate free tier composite
        free_composite = scoring_service.calculate_free_composite(
            clarity_result.score,
            timeline_result.score,
            award_result.score,
            access_barrier_score
        )
        
        # Store grant quality data in reasoning
        reasoning_with_quality = result.reasoning.copy()
        reasoning_with_quality["_grant_quality"] = {
            "clarity_score": clarity_result.score,
            "clarity_rating": clarity_result.rating,
            "clarity_breakdown": clarity_result.breakdown,
            "access_barrier": access_barrier_result.level,
            "access_barrier_hours": access_barrier_result.estimated_hours,
            "timeline_status": timeline_result.status,
            "timeline_weeks": timeline_result.weeks_remaining,
            "award_structure_score": award_result.score,
            "award_structure_transparency": award_result.transparency,
            "competition_level": competition_result.level,
            "competition_acceptance_rate": competition_result.acceptance_rate,
            "competition_source": competition_result.source,
            "competition_confidence": competition_result.confidence,
        }
        
        # Store readiness score in reasoning for frontend access
        reasoning_with_quality["_readiness"] = {
            "score": readiness_result.score,
            "tier": readiness_result.tier,
            "missing_data": readiness_result.missing_data,
            "completeness_percentage": readiness_result.completeness_percentage,
        }
        
        # Update scores with scoring service results
        result.scores.timeline_viability = timeline_result.score
        # Invert access barrier for application_burden (low barrier = high score)
        result.scores.application_burden = 10 - access_barrier_score
        result.scores.award_structure = award_result.score
        result.scores.winner_pattern_match = None  # NULL for free tier (no project data)
        result.scores.mission_alignment = None  # NULL for free tier (no project data)
        result.composite_score = free_composite
        
        # Ensure recommendation is not APPLY
        if result.recommendation.value == "APPLY":
            result.recommendation = Recommendation.CONDITIONAL
        
    else:
        # Paid tier: Personalized fit assessment
        if not project_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project data required for paid assessments"
            )
        
        # Soft validation: Check profile completeness (warn but don't block)
        from app.api.v1.projects import check_profile_completeness
        completeness = check_profile_completeness(project)
        
        # If profile is incomplete, add warning to confidence notes
        if not completeness["is_complete"]:
            # Format field names for human-readable display
            formatted_fields = [format_field_name(field) for field in completeness['missing_required']]
            missing_fields_text = ', '.join(formatted_fields)
            warning = f"Profile incomplete: Missing {missing_fields_text}. Assessment confidence may be reduced."
            if result.confidence_notes:
                result.confidence_notes = f"{warning} {result.confidence_notes}"
            else:
                result.confidence_notes = warning
        
        # Use scoring service for fit assessments
        mission_result = scoring_service.calculate_mission_alignment(grant_dict, project_dict)
        profile_result = scoring_service.calculate_profile_match(grant_dict, project_dict)
        funding_result = scoring_service.assess_funding_fit(grant_dict, project_dict)
        effort_reward_result = scoring_service.assess_effort_reward(
            grant_dict, project_dict, 
            mission_result.score, 
            profile_result.score if profile_result.score is not None else None
        )
        competition_result = scoring_service.assess_competition(grant_dict)
        success_prob_result = scoring_service.estimate_success_probability(
            grant_dict,
            mission_result.score,
            profile_result.score if profile_result.score is not None else None,
            competition_result
        )
        
        # Calculate paid tier composite
        paid_composite = scoring_service.calculate_paid_composite(
            mission_result.score,
            profile_result.score,
            funding_result.fit,
            effort_reward_result.assessment
        )
        
        # Update scores with scoring service results
        result.scores.mission_alignment = mission_result.score
        result.scores.winner_pattern_match = profile_result.score if profile_result.score is not None else 0
        result.composite_score = paid_composite
        
        # Store paid-tier details in reasoning
        reasoning_with_quality = result.reasoning.copy()
        
        # Store readiness score in reasoning for frontend access
        reasoning_with_quality["_readiness"] = {
            "score": readiness_result.score,
            "tier": readiness_result.tier,
            "missing_data": readiness_result.missing_data,
            "completeness_percentage": readiness_result.completeness_percentage,
        }
        
        reasoning_with_quality["_paid_tier"] = {
            "mission_alignment_details": {
                "strong_matches": mission_result.strong_matches,
                "gaps": mission_result.gaps,
                "confidence": mission_result.confidence,
            },
            "profile_match_details": {
                "score": profile_result.score,
                "reason": profile_result.reason,
                "similarities": profile_result.similarities,
                "differences": profile_result.differences,
                "confidence": profile_result.confidence,
                "recipient_count": profile_result.recipient_count,
                "recipient_details": profile_result.recipient_details or [],
            },
            "funding_fit": {
                "fit": funding_result.fit,
                "severity": funding_result.severity,
                "reasoning": funding_result.message,
                "recommendation": funding_result.recommendation,
            },
            "effort_reward": {
                "assessment": effort_reward_result.assessment,
                "estimated_hours": effort_reward_result.estimated_hours,
                "potential_value": effort_reward_result.potential_value,
                "value_per_hour": effort_reward_result.value_per_hour,
                "reasoning": effort_reward_result.reasoning,
                "opportunity_cost": effort_reward_result.opportunity_cost,
                "confidence": effort_reward_result.confidence,
            },
            "success_probability": {
                "range": success_prob_result.range,
                "base_rate": success_prob_result.base_rate,
                "explanation": success_prob_result.explanation,
                "confidence": success_prob_result.confidence,
                "source": success_prob_result.source,
            },
        }
        
        # Update LLM result with scoring service data
        if not result.success_probability_range:
            result.success_probability_range = success_prob_result.range or "UNKNOWN"
        if not result.decision_gates:
            result.decision_gates = []  # Will be populated by LLM
        if not result.confidence_index:
            # Calculate confidence index from data completeness
            confidence = 0.7  # Base
            if profile_result.score is None:
                confidence -= 0.2
            if competition_result.level == "UNKNOWN":
                confidence -= 0.1
            if not grant_dict.get("award_amount"):
                confidence -= 0.1
            result.confidence_index = max(0.0, min(1.0, confidence))
        
        # CRITICAL: Validate recommendation based on composite score and mission alignment
        # This ensures recommendations align with score ranges and prevents trust-breaking recommendations
        mission_score = mission_result.score
        composite = result.composite_score
        
        # Score range: 0-10 (composite score is integer 0-10)
        # Standard recommendation thresholds:
        # - APPLY: composite >= 8.0 (strong fit across all dimensions)
        # - CONDITIONAL: composite >= 6.5 and < 8.0 (potential fit with conditions)
        # - PASS: composite < 6.5 (not worth pursuing)
        
        # Enforce recommendation based on composite score
        if composite < 6.5:
            # Composite < 6.5 should always be PASS (not CONDITIONAL or APPLY)
            if result.recommendation.value != "PASS":
                result.recommendation = Recommendation.PASS
                if result.confidence_notes:
                    result.confidence_notes = f"Recommendation adjusted: Composite score is {composite}/10 (below 6.5 threshold for CONDITIONAL). {result.confidence_notes}"
                else:
                    result.confidence_notes = f"Recommendation adjusted: Composite score is {composite}/10 (below 6.5 threshold for CONDITIONAL)."
        elif result.recommendation.value == "APPLY":
            # Never recommend APPLY if mission alignment is 0/10
            if mission_score == 0:
                result.recommendation = Recommendation.PASS
                if result.confidence_notes:
                    result.confidence_notes = f"Recommendation downgraded: Mission alignment is 0/10 (no alignment found). {result.confidence_notes}"
                else:
                    result.confidence_notes = "Recommendation downgraded: Mission alignment is 0/10 (no alignment found)."
            # Don't recommend APPLY if composite score is very low (< 5) or mission alignment is very low (< 3)
            elif composite < 5 or mission_score < 3:
                result.recommendation = Recommendation.CONDITIONAL
                if result.confidence_notes:
                    result.confidence_notes = f"Recommendation adjusted: Low fit scores (mission: {mission_score}/10, composite: {composite}/10). {result.confidence_notes}"
                else:
                    result.confidence_notes = f"Recommendation adjusted: Low fit scores (mission: {mission_score}/10, composite: {composite}/10)."
    
    # Save evaluation to database
    db_evaluation = models.Evaluation(
        user_id=current_user.id,
        project_id=project.id,
        grant_id=grant_id,
        grant_url=grant_url,
        grant_name=grant_name,
        grant_snapshot_json=grant_snapshot,
        timeline_viability=int(result.scores.timeline_viability),
        winner_pattern_match=int(result.scores.winner_pattern_match) if result.scores.winner_pattern_match is not None and result.scores.winner_pattern_match > 0 else None,  # NULL for free tier
        mission_alignment=int(result.scores.mission_alignment) if result.scores.mission_alignment is not None and result.scores.mission_alignment > 0 else None,  # NULL for free tier
        application_burden=int(result.scores.application_burden),
        award_structure=int(result.scores.award_structure),
        composite_score=int(result.composite_score),
        recommendation=result.recommendation.value,
        reasoning=reasoning_with_quality,
        key_insights=result.key_insights,
        red_flags=result.red_flags,
        confidence_notes=result.confidence_notes,
        evaluator_type=evaluator_type,
        evaluation_tier="free" if assessment_type == "free" else "standard",  # Keep for backward compatibility
        assessment_type=assessment_type,  # New field
        is_legacy=False,  # New assessments are not legacy
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


@router.post("/refine", status_code=status.HTTP_410_GONE)
async def refine_evaluation(
    request: Request,
    refinement_request: RefinementRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DEPRECATED: Refinement endpoint has been removed.
    
    Refinement payments have been converted to bundle credits.
    Use your bundle credits to create paid assessments instead.
    
    If you had a refinement payment, it has been automatically converted to a $3 credit
    toward a full paid assessment. Check your bundle credits in the dashboard.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "message": "The refinement endpoint has been deprecated.",
            "reason": "Refinement payments have been converted to bundle credits.",
            "action": "Use your bundle credits to create paid assessments. Check your dashboard for available credits.",
            "help": "If you had a $3 refinement payment, it has been automatically converted to 1 bundle credit."
        }
    )
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

