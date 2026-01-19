"""
Slack webhook endpoints for admin orchestration.

Slack is NOT part of core application logic.
Only handles: Grant Index Inclusion, Payment Issues, Flag Review.
"""

import json
import logging
import urllib.parse
from fastapi import APIRouter, Request, HTTPException, status, Header, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional
from app.db.database import get_db
from app.db import models
from app.core.config import settings
from app.api.v1.auth import get_current_user
from app.services.slack_service import (
    verify_slack_request,
    verify_slack_workspace,
    verify_slack_admin,
    parse_button_value
)
from datetime import datetime, timezone

router = APIRouter()
logger = logging.getLogger(__name__)


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Require admin (superuser) access."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.post("/slack/interactive")
async def handle_slack_interaction(
    request: Request,
    x_slack_signature: Optional[str] = Header(None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: Optional[str] = Header(None, alias="X-Slack-Request-Timestamp"),
    db: Session = Depends(get_db)
):
    """
    Handle Slack button interactions (approve/reject only).
    
    Security:
    - Verifies Slack signing secret
    - Validates timestamp (rejects stale requests)
    - Checks workspace allowlist
    - Checks admin user allowlist
    
    Allowed actions only:
    - Grant Index Inclusion (approve/reject)
    """
    try:
        logger.info("=" * 60)
        logger.info("SLACK INTERACTIVE REQUEST RECEIVED")
        logger.info(f"Method: {request.method}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info("=" * 60)
        
        # Read raw body for signature verification
        # Note: We need to read body before accessing form, so we cache it
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        logger.info(f"Body length: {len(body_str)}")
        logger.info(f"Body preview: {body_str[:200]}")
        
            # Handle URL verification challenge (Slack sends this when you first set the URL)
        try:
            parsed_data = urllib.parse.parse_qs(body_str)
            challenge = parsed_data.get('challenge', [])
            if challenge:
                logger.info("Slack URL verification challenge received")
                return Response(
                    content=challenge[0],
                    media_type="text/plain"
                )
        except Exception:
            pass  # Not a challenge, continue with normal processing
        
            # Verify Slack signature
        if not x_slack_signature or not x_slack_request_timestamp:
            logger.warning("Slack request missing signature headers")
            return Response(
                status_code=200,
                content=json.dumps({"error": "Unauthorized"}),
                media_type="application/json"
            )
        
        if not verify_slack_request(x_slack_request_timestamp, x_slack_signature, body_bytes):
            logger.warning("Slack signature verification failed")
            return Response(
                status_code=200,
                content=json.dumps({"error": "Invalid signature"}),
                media_type="application/json"
            )
        
            # Parse payload (Slack sends form-data with "payload" field as JSON string)
        try:
            # Extract payload from form-data (format: payload=URL_ENCODED_JSON)
            parsed_data = urllib.parse.parse_qs(body_str)
            payload_list = parsed_data.get('payload', [])
            if not payload_list:
                logger.warning("Slack request missing payload field")
                return Response(
                    status_code=200,
                    content=json.dumps({"error": "Missing payload"}),
                    media_type="application/json"
                )
            
            payload_str = payload_list[0]
            payload = json.loads(urllib.parse.unquote(payload_str))
            logger.info(f"Slack payload received: {json.dumps(payload, indent=2)}")
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.warning(f"Failed to parse Slack payload: {e}", exc_info=True)
            return Response(
                status_code=200,
                content=json.dumps({"error": "Invalid payload format"}),
                media_type="application/json"
            )
        
            # Verify workspace
        team_id = payload.get("team", {}).get("id")
        
        # Log workspace ID for debugging (remove in production)
        if team_id:
            logger.info(f"Slack workspace ID received: {team_id}")
            logger.info(f"Expected workspace ID: {settings.SLACK_WORKSPACE_ID}")
        
        if not verify_slack_workspace(team_id):
            # Log the actual workspace ID so user can add it to config
            logger.warning(
                f"Rejected Slack request from unauthorized workspace: {team_id}. "
                f"Add this to SLACK_WORKSPACE_ID in .env if this is your workspace."
            )
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"Unauthorized workspace. Workspace ID: {team_id}"
                }),
                media_type="application/json"
            )
        
        # Verify admin user
        user_id = payload.get("user", {}).get("id")
        if not verify_slack_admin(user_id):
            logger.warning(f"Rejected Slack request from unauthorized user: {user_id}")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"Unauthorized user. User ID: {user_id}. Add to SLACK_ADMIN_USER_IDS in .env"
                }),
                media_type="application/json"
            )
        
        # Handle button action
        actions = payload.get("actions", [])
        if not actions or len(actions) != 1:
            logger.warning(f"Invalid actions array: {actions}")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": "Invalid action - expected exactly one action"
                }),
                media_type="application/json"
            )
        
        action = actions[0]
        action_id = action.get("action_id")
        value = action.get("value")
        
        logger.info(f"Processing Slack action: action_id={action_id}, value={value}")
        
        # Parse button value
        parsed = parse_button_value(value)
        if not parsed:
            logger.warning(f"Invalid button value: {value}")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"Invalid button value format: {value}"
                }),
                media_type="application/json"
            )
        
        entity_type = parsed["entity_type"]
        entity_id = parsed["entity_id"]
        action_type = parsed["action"]
        
        logger.info(f"Parsed button value - entity_type: {entity_type}, entity_id: {entity_id}, action: {action_type}")
        logger.info(f"Checking if action matches - entity_type=='grant': {entity_type == 'grant'}, action_id in allowlist: {action_id in ['grant_approve', 'grant_reject']}")
        
        # Execute action (strict allowlist)
        if entity_type == "grant" and action_id in ["grant_approve", "grant_reject"]:
            logger.info(f"Calling _handle_grant_approval with grant_id={entity_id}, action={action_type}")
            # Process the action and return response
            # Note: Must return within 3 seconds, so keep database operations fast
            return await _handle_grant_approval(
                grant_id=entity_id,
                action=action_type,
                slack_user_id=user_id,
                db=db
            )
        
        if entity_type == "grant" and action_id == "grant_delete":
            logger.info(f"Calling _handle_grant_deletion with grant_id={entity_id}")
            return await _handle_grant_deletion(
                grant_id=entity_id,
                slack_user_id=user_id,
                db=db
            )
        
        if entity_type == "contribution" and action_id in ["contribution_approve", "contribution_reject"]:
            logger.info(f"Calling _handle_contribution_review with contribution_id={entity_id}, action={action_type}")
            return await _handle_contribution_review(
                contribution_id=entity_id,
                action=action_type,
                slack_user_id=user_id,
                db=db
            )
        
        if entity_type == "support" and action_id in ["support_acknowledge", "support_resolve"]:
            logger.info(f"Calling _handle_support_action with request_id={entity_id}, action={action_type}")
            return await _handle_support_action(
                request_id=entity_id,
                action=action_type,
                slack_user_id=user_id,
                db=db
            )
        
        # Unknown action - return error message
        logger.warning(f"Unknown Slack action: action_id={action_id}, entity_type={entity_type}, entity_id={entity_id}, action={action_type}")
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"Unknown action: {action_id}. Entity: {entity_type}, ID: {entity_id}, Action: {action_type}"
            }),
            media_type="application/json"
        )
        
    except Exception as e:
        # Catch any unhandled exceptions
        logger.error(f"Unhandled exception in Slack interactive endpoint: {e}", exc_info=True)
        # Return empty 200 OK to prevent Slack from retrying
        return Response(
            status_code=200,
            content="",
            media_type="text/plain"
        )


async def _handle_grant_approval(
    grant_id: int,
    action: str,
    slack_user_id: str,
    db: Session
) -> Response:
    """
    Handle grant approval/rejection from Slack.
    
    This executes exactly one database operation and is idempotent.
    """
    logger.info("=" * 60)
    logger.info(f"_handle_grant_approval CALLED")
    logger.info(f"  grant_id: {grant_id}")
    logger.info(f"  action: {action}")
    logger.info(f"  slack_user_id: {slack_user_id}")
    logger.info("=" * 60)
    
    try:
        # Find grant
        grant = db.query(models.Grant).filter(models.Grant.id == grant_id).first()
        if not grant:
            logger.error(f"Grant {grant_id} not found in database")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Grant {grant_id} not found in database."
                }),
                media_type="application/json"
            )
        
        logger.info(f"Found grant {grant_id}: '{grant.name}', current status: {grant.approval_status}")
        
        # Check current status
        if grant.approval_status != "pending":
            # Already processed - idempotent, return success
            status_text = "already_approved" if grant.approval_status == "approved" else "already_rejected"
            logger.info(f"Grant {grant_id} already {status_text}")
            return Response(
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"Grant {grant_id} has already been {status_text}."
                }),
                media_type="application/json"
            )
        
        # Execute action
        if action == "approve":
            grant.approval_status = "approved"
            grant.approved_at = datetime.now(timezone.utc)
            logger.info(f"Setting grant {grant_id} status to 'approved'")
            # Note: approved_by requires User model lookup - simplified for now
            # In production, map slack_user_id to User ID or store slack_user_id
            
            # Generate and save normalization on approval
            # This creates the canonical presentation layer from raw grant data
            try:
                from app.services.normalization_service import NormalizationService
                normalization_service = NormalizationService()
                
                # Prepare grant dict for normalization service
                grant_dict = {
                    'name': grant.name,
                    'description': grant.description,
                    'mission': grant.mission,
                    'deadline': grant.deadline,
                    'decision_date': grant.decision_date,
                    'award_amount': grant.award_amount,
                }
                
                # Generate normalization
                normalization_data = normalization_service.generate_normalization(grant_dict)
                
                # Check if normalization already exists for this grant
                existing_norm = db.query(models.GrantNormalization).filter(
                    models.GrantNormalization.grant_id == grant_id
                ).first()
                
                if existing_norm:
                    # Update existing normalization
                    existing_norm.canonical_title = normalization_data.get('canonical_title')
                    existing_norm.canonical_summary = normalization_data.get('canonical_summary')
                    existing_norm.timeline_status = normalization_data.get('timeline_status')
                    existing_norm.confidence_level = normalization_data.get('confidence_level')
                    existing_norm.normalized_by = 'admin'
                    existing_norm.approved_at = datetime.now(timezone.utc)
                    existing_norm.revision_notes = f"Approved via Slack by {slack_user_id}"
                    existing_norm.updated_at = datetime.now(timezone.utc)
                    logger.info(f"Updated existing normalization for grant {grant_id}")
                else:
                    # Create new normalization
                    new_norm = models.GrantNormalization(
                        grant_id=grant_id,
                        canonical_title=normalization_data.get('canonical_title'),
                        canonical_summary=normalization_data.get('canonical_summary'),
                        timeline_status=normalization_data.get('timeline_status'),
                        confidence_level=normalization_data.get('confidence_level'),
                        normalized_by='admin',
                        approved_at=datetime.now(timezone.utc),
                        revision_notes=f"Approved via Slack by {slack_user_id}"
                    )
                    db.add(new_norm)
                    logger.info(f"Created new normalization for grant {grant_id}")
                
            except Exception as norm_error:
                # Log normalization error but don't fail approval
                # Grant approval succeeds even if normalization generation fails
                logger.warning(
                    f"Failed to generate/save normalization for grant {grant_id}: {norm_error}",
                    exc_info=True
                )
                # Continue with approval - normalization can be added later
            
        elif action == "reject":
            grant.approval_status = "rejected"
            grant.approved_at = datetime.now(timezone.utc)
            grant.rejection_reason = "Rejected via Slack admin interface"
            logger.info(f"Setting grant {grant_id} status to 'rejected'")
        else:
            logger.error(f"Invalid action: {action}")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Invalid action: {action}"
                }),
                media_type="application/json"
            )
        
        # Log action (audit trail)
        logger.info(
            f"Grant {grant_id} {action}d via Slack by user {slack_user_id} "
            f"at {datetime.now(timezone.utc)}"
        )
        
        # Commit
        try:
            db.commit()
            db.refresh(grant)
            
            # Verify the commit worked
            logger.info(f"Database commit successful. Refreshed grant status: {grant.approval_status}")
            
            # Log successful update with grant details
            logger.info(
                f"✅ Successfully {action}d grant {grant_id} '{grant.name}'. "
                f"Status: {grant.approval_status}, Approved at: {grant.approved_at}, "
                f"Source URL: {grant.source_url}"
            )
        except Exception as e:
            logger.error(f"Failed to commit grant {grant_id} update: {e}", exc_info=True)
            db.rollback()
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Error updating grant: {str(e)}"
                }),
                media_type="application/json"
            )
        
        # Return success response to Slack
        # For interactive components, return empty 200 OK to acknowledge
        # Slack requires immediate response within 3 seconds
        action_past = "approved" if action == "approve" else "rejected"
        logger.info(f"Grant '{grant.name}' (ID: {grant_id}) has been {action_past}. Status: {grant.approval_status}. Status updated in database.")
        
        # Return empty response - Slack just needs acknowledgment
        return Response(
            status_code=200,
            content="",
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Unexpected error in _handle_grant_approval: {e}", exc_info=True)
        db.rollback()
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"❌ Unexpected error: {str(e)}"
            }),
            media_type="application/json"
        )


async def _handle_contribution_review(
    contribution_id: int,
    action: str,
    slack_user_id: str,
    db: Session
) -> Response:
    """
    Handle contribution approval/rejection from Slack.
    
    This executes exactly one database operation and is idempotent.
    Sends email notification to the user who submitted the contribution.
    """
    logger.info("=" * 60)
    logger.info(f"_handle_contribution_review CALLED")
    logger.info(f"  contribution_id: {contribution_id}")
    logger.info(f"  action: {action}")
    logger.info(f"  slack_user_id: {slack_user_id}")
    logger.info("=" * 60)
    
    try:
        # Find contribution
        contribution = db.query(models.GrantDataContribution).filter(
            models.GrantDataContribution.id == contribution_id
        ).first()
        
        if not contribution:
            logger.error(f"Contribution {contribution_id} not found in database")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Contribution {contribution_id} not found in database."
                }),
                media_type="application/json"
            )
        
        logger.info(
            f"Found contribution {contribution_id}: field='{contribution.field_name}', "
            f"grant={contribution.grant_id or contribution.grant_name}, current status: {contribution.status}"
        )
        
        # Check current status
        if contribution.status != "pending":
            # Already processed - idempotent, return success
            status_text = "already_approved" if contribution.status == "approved" else "already_rejected"
            logger.info(f"Contribution {contribution_id} already {status_text}")
            return Response(
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"Contribution {contribution_id} has already been {status_text}."
                }),
                media_type="application/json"
            )
        
        # Get user who submitted the contribution
        user = db.query(models.User).filter(models.User.id == contribution.user_id).first()
        if not user:
            logger.error(f"User {contribution.user_id} not found for contribution {contribution_id}")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ User not found for contribution {contribution_id}"
                }),
                media_type="application/json"
            )
        
        # Execute action
        if action == "approve":
            contribution.status = "approved"
            contribution.reviewed_at = datetime.now(timezone.utc)
            contribution.admin_notes = f"Approved via Slack by {slack_user_id}"
            # Note: reviewed_by requires User model lookup - simplified for now
            # In production, map slack_user_id to User ID or store slack_user_id
            logger.info(f"Setting contribution {contribution_id} status to 'approved'")
            
            # Merge contribution data into grant record if grant exists
            if contribution.grant_id:
                grant = db.query(models.Grant).filter(
                    models.Grant.id == contribution.grant_id
                ).first()
                
                if grant:
                    try:
                        # Map contribution field_name to grant column
                        field_mapping = {
                            'award_amount': 'award_amount',
                            'deadline': 'deadline',
                            'decision_date': 'decision_date',
                            'eligibility': 'eligibility',
                            'preferred_applicants': 'preferred_applicants',
                            'application_requirements': 'application_requirements',
                            'award_structure': 'award_structure',
                            'mission': 'mission',
                            'description': 'description',
                        }
                        
                        # Handle special fields that go into JSONB
                        if contribution.field_name in ['past_recipients', 'acceptance_rate']:
                            # Update recipient_patterns JSONB field
                            recipient_patterns = grant.recipient_patterns or {}
                            
                            if contribution.field_name == 'past_recipients':
                                recipient_patterns['past_recipients'] = contribution.field_value
                                recipient_patterns['past_recipients_source'] = 'user_contribution'
                            elif contribution.field_name == 'acceptance_rate':
                                recipient_patterns['acceptance_rate'] = contribution.field_value
                                recipient_patterns['acceptance_rate_source'] = 'user_contribution'
                            
                            grant.recipient_patterns = recipient_patterns
                            logger.info(f"Updated recipient_patterns for grant {grant.id} with {contribution.field_name}")
                        elif contribution.field_name in field_mapping:
                            # Update direct grant field
                            grant_field = field_mapping[contribution.field_name]
                            
                            # Handle JSON fields (application_requirements)
                            if grant_field == 'application_requirements':
                                try:
                                    # Try to parse as JSON, otherwise store as string in list
                                    parsed_value = json.loads(contribution.field_value)
                                    if isinstance(parsed_value, list):
                                        grant.application_requirements = parsed_value
                                    else:
                                        grant.application_requirements = [contribution.field_value]
                                except (json.JSONDecodeError, ValueError):
                                    # If not valid JSON, store as single-item list
                                    grant.application_requirements = [contribution.field_value]
                            else:
                                # Direct field assignment
                                setattr(grant, grant_field, contribution.field_value)
                            
                            logger.info(f"Merged contribution {contribution_id} into grant {grant.id}, field: {grant_field}")
                        else:
                            logger.warning(f"Contribution field '{contribution.field_name}' not mapped to grant field - skipping merge")
                        
                        # Mark contribution as merged after successful merge
                        contribution.status = 'merged'
                        contribution.admin_notes = f"Approved and merged via Slack by {slack_user_id}"
                        
                        # Recompute decision readiness after merge (non-blocking)
                        try:
                            from app.services.decision_readiness_service import DecisionReadinessService
                            readiness_service = DecisionReadinessService()
                            
                            # Prepare grant dict for readiness computation
                            grant_dict = {
                                'name': grant.name,
                                'description': grant.description,
                                'mission': grant.mission,
                                'deadline': grant.deadline,
                                'decision_date': grant.deadline,
                                'award_amount': grant.award_amount,
                                'eligibility': grant.eligibility,
                                'preferred_applicants': grant.preferred_applicants,
                                'application_requirements': grant.application_requirements,
                                'award_structure': grant.award_structure,
                                'recipient_patterns': grant.recipient_patterns,
                            }
                            
                            # Recompute buckets
                            timeline_state, _ = readiness_service.assess_timeline_clarity(grant_dict)
                            winner_state, _ = readiness_service.assess_winner_signal(grant_dict)
                            mission_state, _ = readiness_service.assess_mission_specificity(grant_dict)
                            application_state, _ = readiness_service.assess_application_burden(grant_dict)
                            award_state, _ = readiness_service.assess_award_structure_clarity(grant_dict)
                            
                            grant.timeline_clarity = timeline_state
                            grant.winner_signal = winner_state
                            grant.mission_specificity = mission_state
                            grant.application_burden = application_state
                            grant.award_structure_clarity = award_state
                            
                            # Recompute decision readiness
                            grant.decision_readiness = readiness_service.compute_decision_readiness(grant_dict)
                            
                            logger.info(f"Recomputed decision readiness for grant {grant.id} after contribution merge")
                        except Exception as readiness_error:
                            # Log but don't fail - readiness computation is non-critical
                            logger.warning(f"Failed to recompute decision readiness after merge: {readiness_error}", exc_info=True)
                        
                    except Exception as merge_error:
                        # Log merge error but don't fail approval - contribution is still approved
                        logger.error(f"Failed to merge contribution {contribution_id} into grant {grant.id}: {merge_error}", exc_info=True)
                        # Keep status as 'approved' (not 'merged') if merge failed
                        contribution.admin_notes = f"Approved via Slack by {slack_user_id} (merge failed: {str(merge_error)})"
                else:
                    logger.warning(f"Grant {contribution.grant_id} not found - cannot merge contribution {contribution_id}")
            else:
                logger.info(f"Contribution {contribution_id} has no grant_id - skipping merge (in-memory grant)")
            
        elif action == "reject":
            contribution.status = "rejected"
            contribution.reviewed_at = datetime.now(timezone.utc)
            contribution.admin_notes = f"Rejected via Slack by {slack_user_id}"
            logger.info(f"Setting contribution {contribution_id} status to 'rejected'")
        else:
            logger.error(f"Invalid action: {action}")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Invalid action: {action}"
                }),
                media_type="application/json"
            )
        
        # Log action (audit trail)
        logger.info(
            f"Contribution {contribution_id} {action}d via Slack by user {slack_user_id} "
            f"at {datetime.now(timezone.utc)}"
        )
        
        # Commit
        try:
            db.commit()
            db.refresh(contribution)
            
            # Verify the commit worked
            logger.info(f"Database commit successful. Refreshed contribution status: {contribution.status}")
            
            # Send email notification to user
            try:
                from app.services.email_service import EmailService
                email_service = EmailService()
                
                # Format field name for display
                field_labels = {
                    'award_amount': 'Award Amount',
                    'deadline': 'Application Deadline',
                    'decision_date': 'Decision Date',
                    'acceptance_rate': 'Acceptance Rate',
                    'past_recipients': 'Past Recipients',
                    'eligibility': 'Eligibility Criteria',
                    'preferred_applicants': 'Preferred Applicants',
                    'application_requirements': 'Application Requirements',
                    'award_structure': 'Award Structure',
                    'other': 'Other Information'
                }
                field_display = field_labels.get(contribution.field_name, contribution.field_name.replace('_', ' ').title())
                
                grant_name = contribution.grant_name or (contribution.grant.name if contribution.grant else "Unknown Grant")
                
                if action == "approve":
                    subject = f"Your Grant Data Contribution Has Been Approved"
                    html_content = f"""
                    <html>
                    <body>
                        <h2>Contribution Approved</h2>
                        <p>Your contribution for <strong>{field_display}</strong> on <strong>{grant_name}</strong> has been approved by our team.</p>
                        <p>Thank you for helping improve GrantPool's data quality!</p>
                        <p><strong>Contribution ID:</strong> {contribution_id}</p>
                        <p><strong>Field:</strong> {field_display}</p>
                        <p><strong>Grant:</strong> {grant_name}</p>
                    </body>
                    </html>
                    """
                else:  # reject
                    subject = f"Your Grant Data Contribution Has Been Reviewed"
                    html_content = f"""
                    <html>
                    <body>
                        <h2>Contribution Reviewed</h2>
                        <p>Your contribution for <strong>{field_display}</strong> on <strong>{grant_name}</strong> has been reviewed.</p>
                        <p>Unfortunately, we were unable to use this contribution at this time.</p>
                        <p><strong>Contribution ID:</strong> {contribution_id}</p>
                        <p><strong>Field:</strong> {field_display}</p>
                        <p><strong>Grant:</strong> {grant_name}</p>
                    </body>
                    </html>
                    """
                
                text_content = html_content.replace('<html>', '').replace('</html>', '').replace('<body>', '').replace('</body>', '').replace('<h2>', '').replace('</h2>', '').replace('<p>', '').replace('</p>', '\n').replace('<strong>', '').replace('</strong>', '')
                
                email_sent = email_service.send_email(user.email, subject, html_content, text_content)
                if email_sent:
                    logger.info(f"Email notification sent to {user.email} for contribution {contribution_id}")
                else:
                    logger.warning(f"Failed to send email notification to {user.email} for contribution {contribution_id}")
            except Exception as email_error:
                # Log email error but don't fail the request
                logger.warning(f"Failed to send email notification for contribution {contribution_id}: {email_error}", exc_info=True)
            
            # Log successful update
            logger.info(
                f"✅ Successfully {action}d contribution {contribution_id} for field '{contribution.field_name}' "
                f"on grant {contribution.grant_id or contribution.grant_name}. "
                f"Status: {contribution.status}, Reviewed at: {contribution.reviewed_at}"
            )
        except Exception as e:
            logger.error(f"Failed to commit contribution {contribution_id} update: {e}", exc_info=True)
            db.rollback()
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Error updating contribution: {str(e)}"
                }),
                media_type="application/json"
            )
        
        # Return success response to Slack
        # For interactive components, return empty 200 OK to acknowledge
        # Slack requires immediate response within 3 seconds
        action_past = "approved" if action == "approve" else "rejected"
        logger.info(
            f"Contribution {contribution_id} (field: {contribution.field_name}) has been {action_past}. "
            f"Status: {contribution.status}. Status updated in database."
        )
        
        # Return empty response - Slack just needs acknowledgment
        return Response(
            status_code=200,
            content="",
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Unexpected error in _handle_contribution_review: {e}", exc_info=True)
        db.rollback()
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"❌ Unexpected error: {str(e)}"
            }),
            media_type="application/json"
        )


async def _handle_support_action(
    request_id: int,
    action: str,
    slack_user_id: str,
    db: Session
) -> Response:
    """
    Handle support request actions from Slack (acknowledge/resolve).
    """
    logger.info("=" * 60)
    logger.info(f"_handle_support_action CALLED")
    logger.info(f"  request_id: {request_id}")
    logger.info(f"  action: {action}")
    logger.info(f"  slack_user_id: {slack_user_id}")
    logger.info("=" * 60)
    
    try:
        # Find support request
        support_request = db.query(models.SupportRequest).filter(
            models.SupportRequest.id == request_id
        ).first()
        
        if not support_request:
            logger.error(f"Support request {request_id} not found in database")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Support request {request_id} not found in database."
                }),
                media_type="application/json"
            )
        
        # Get user who submitted the request
        user = db.query(models.User).filter(models.User.id == support_request.user_id).first()
        if not user:
            logger.error(f"User {support_request.user_id} not found for support request {request_id}")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ User not found for support request {request_id}"
                }),
                media_type="application/json"
            )
        
        # Execute action
        if action == "acknowledge":
            support_request.status = "acknowledged"
            support_request.admin_notes = f"Acknowledged via Slack by {slack_user_id}"
            logger.info(f"Setting support request {request_id} status to 'acknowledged'")
        elif action == "resolve":
            support_request.status = "resolved"
            support_request.admin_notes = f"Resolved via Slack by {slack_user_id}"
            logger.info(f"Setting support request {request_id} status to 'resolved'")
        else:
            logger.error(f"Invalid action: {action}")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Invalid action: {action}"
                }),
                media_type="application/json"
            )
        
        support_request.updated_at = datetime.now(timezone.utc)
        
        # Commit
        try:
            db.commit()
            db.refresh(support_request)
            logger.info(f"Database commit successful. Refreshed support request status: {support_request.status}")
            
            # Send email notification to user
            try:
                from app.services.email_service import EmailService
                email_service = EmailService()
                
                if action == "acknowledge":
                    subject = f"Your Support Request Has Been Acknowledged"
                    html_content = f"""
                    <html>
                    <body>
                        <h2>Support Request Acknowledged</h2>
                        <p>Your support request #{request_id} has been acknowledged by our team.</p>
                        <p>We're looking into your issue and will update you soon.</p>
                        <p><strong>Request ID:</strong> {request_id}</p>
                        <p><strong>Issue Type:</strong> {support_request.issue_type.replace('_', ' ').title()}</p>
                    </body>
                    </html>
                    """
                else:  # resolve
                    subject = f"Your Support Request Has Been Resolved"
                    html_content = f"""
                    <html>
                    <body>
                        <h2>Support Request Resolved</h2>
                        <p>Your support request #{request_id} has been resolved by our team.</p>
                        <p>If you have any further questions, please don't hesitate to reach out.</p>
                        <p><strong>Request ID:</strong> {request_id}</p>
                        <p><strong>Issue Type:</strong> {support_request.issue_type.replace('_', ' ').title()}</p>
                    </body>
                    </html>
                    """
                
                text_content = html_content.replace('<html>', '').replace('</html>', '').replace('<body>', '').replace('</body>', '').replace('<h2>', '').replace('</h2>', '').replace('<p>', '').replace('</p>', '\n').replace('<strong>', '').replace('</strong>', '')
                
                email_sent = email_service.send_email(user.email, subject, html_content, text_content)
                if email_sent:
                    logger.info(f"Email notification sent to {user.email} for support request {request_id}")
                else:
                    logger.warning(f"Failed to send email notification to {user.email} for support request {request_id}")
            except Exception as email_error:
                logger.warning(f"Failed to send email notification for support request {request_id}: {email_error}", exc_info=True)
            
            logger.info(f"✅ Successfully {action}d support request {request_id}. Status: {support_request.status}")
        except Exception as e:
            logger.error(f"Failed to commit support request {request_id} update: {e}", exc_info=True)
            db.rollback()
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Error updating support request: {str(e)}"
                }),
                media_type="application/json"
            )
        
        # Return success response
        action_past = "acknowledged" if action == "acknowledge" else "resolved"
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"✅ Support request #{request_id} has been {action_past}."
            }),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Unexpected error in _handle_support_action: {e}", exc_info=True)
        db.rollback()
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"❌ Unexpected error: {str(e)}"
            }),
            media_type="application/json"
        )


async def _handle_grant_deletion(
    grant_id: int,
    slack_user_id: str,
    db: Session
) -> Response:
    """
    Handle grant deletion from Slack.
    
    This deletes the grant, unlinks evaluations, and deletes normalization.
    """
    logger.info("=" * 60)
    logger.info(f"_handle_grant_deletion CALLED")
    logger.info(f"  grant_id: {grant_id}")
    logger.info(f"  slack_user_id: {slack_user_id}")
    logger.info("=" * 60)
    
    try:
        # Find grant
        grant = db.query(models.Grant).filter(models.Grant.id == grant_id).first()
        if not grant:
            logger.error(f"Grant {grant_id} not found in database")
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"❌ Grant {grant_id} not found in database."
                }),
                media_type="application/json"
            )
        
        grant_name = grant.name
        
        # Set grant_id to NULL for evaluations linked to this grant (preserve evaluations)
        from sqlalchemy import update
        evaluations_count = db.query(models.Evaluation).filter(
            models.Evaluation.grant_id == grant_id
        ).count()
        if evaluations_count > 0:
            db.execute(
                update(models.Evaluation)
                .where(models.Evaluation.grant_id == grant_id)
                .values(grant_id=None)
            )
            logger.info(f"Unlinked {evaluations_count} evaluation(s) from grant {grant_id}")
        
        # Delete associated normalization if exists
        if grant.normalization:
            db.delete(grant.normalization)
            logger.info(f"Deleted normalization for grant {grant_id}")
        
        # Delete the grant
        db.delete(grant)
        db.commit()
        
        logger.info(f"Grant {grant_id} '{grant_name}' deleted via Slack by user {slack_user_id}")
        
        # Return success response
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"✅ Grant '{grant_name}' (ID: {grant_id}) has been deleted. {evaluations_count} evaluation(s) unlinked."
            }),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Unexpected error in _handle_grant_deletion: {e}", exc_info=True)
        db.rollback()
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"❌ Unexpected error deleting grant: {str(e)}"
            }),
            media_type="application/json"
        )


@router.post("/slack/commands")
async def handle_slack_command(
    request: Request,
    x_slack_signature: Optional[str] = Header(None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: Optional[str] = Header(None, alias="X-Slack-Request-Timestamp"),
    db: Session = Depends(get_db)
):
    """
    Handle Slack slash commands for admin actions.
    
    Supported commands:
    - /grantpool pending - List all pending grants
    """
    try:
        # Read raw body for signature verification
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        
        # Verify Slack signature
        if not x_slack_signature or not x_slack_request_timestamp:
            logger.warning("Slack command missing signature headers")
            return Response(
                status_code=200,
                content="Unauthorized",
                media_type="text/plain"
            )
        
        if not verify_slack_request(x_slack_request_timestamp, x_slack_signature, body_bytes):
            logger.warning("Slack command signature verification failed")
            return Response(
                status_code=200,
                content="Invalid signature",
                media_type="text/plain"
            )
        
        # Parse form data
        parsed_data = urllib.parse.parse_qs(body_str)
        command = parsed_data.get('command', [None])[0]
        text = parsed_data.get('text', [''])[0].strip()
        team_id = parsed_data.get('team_id', [None])[0]
        user_id = parsed_data.get('user_id', [None])[0]
        
        # Verify workspace
        if not verify_slack_workspace(team_id):
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"Unauthorized workspace. Workspace ID: {team_id}"
                }),
                media_type="application/json"
            )
        
        # Verify admin user
        if not verify_slack_admin(user_id):
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": f"Unauthorized user. User ID: {user_id}. Add to SLACK_ADMIN_USER_IDS in .env"
                }),
                media_type="application/json"
            )
        
        # Handle commands
        if command == "/grantpool":
            if text == "pending":
                return await _list_pending_grants_command(db)
            else:
                return Response(
                    status_code=200,
                    content=json.dumps({
                        "response_type": "ephemeral",
                        "text": "Unknown command. Available commands:\n- `/grantpool pending` - List pending grants"
                    }),
                    media_type="application/json"
                )
        
        return Response(
            status_code=200,
            content="Unknown command",
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Error handling Slack command: {e}", exc_info=True)
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"Error processing command: {str(e)}"
            }),
            media_type="application/json"
        )


async def _list_pending_grants_command(db: Session) -> Response:
    """List pending grants as Slack message blocks."""
    try:
        pending_grants = db.query(models.Grant).filter(
            models.Grant.approval_status == 'pending'
        ).order_by(models.Grant.created_at.desc()).limit(20).all()
        
        if not pending_grants:
            return Response(
                status_code=200,
                content=json.dumps({
                    "response_type": "ephemeral",
                    "text": "✅ No pending grants"
                }),
                media_type="application/json"
            )
        
        # Build blocks for Slack message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Pending Grants ({len(pending_grants)})"
                }
            }
        ]
        
        for grant in pending_grants:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{grant.name}*\nID: `{grant.id}`\nURL: {grant.source_url or 'N/A'}"
                }
            })
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "value": f"grant_{grant.id}_approve",
                        "action_id": "grant_approve"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "style": "danger",
                        "value": f"grant_{grant.id}_reject",
                        "action_id": "grant_reject"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Delete"},
                        "style": "danger",
                        "value": f"grant_{grant.id}_delete",
                        "action_id": "grant_delete"
                    }
                ]
            })
            blocks.append({"type": "divider"})
        
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "blocks": blocks
            }),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Error listing pending grants: {e}", exc_info=True)
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"Error listing pending grants: {str(e)}"
            }),
            media_type="application/json"
        )


@router.post("/slack/test-notification")
async def test_slack_notification(
    admin_user: models.User = Depends(require_admin),
):
    """
    Test endpoint to send a sample Slack notification.
    Admin only - for testing Slack integration.
    """
    from app.services.slack_service import send_grant_approval_notification
    
    # Send test notification
    send_grant_approval_notification(
        grant_id=999,
        grant_name="Test Grant - Slack Integration",
        grant_url="https://example.com/test-grant"
    )
    
    return {
        "message": "Test notification sent to Slack. Check your #grantpool-admin channel.",
        "note": "This is a test - grant ID 999 does not exist in database."
    }


@router.post("/slack/debug")
async def debug_slack_interaction(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to log Slack interaction details.
    This helps diagnose why buttons aren't working.
    """
    try:
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        
        # Try to parse as form data
        parsed_data = urllib.parse.parse_qs(body_str)
        
        # Log everything
        logger.info("=" * 60)
        logger.info("SLACK DEBUG REQUEST")
        logger.info("=" * 60)
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Body (raw): {body_str[:500]}")
        logger.info(f"Parsed form data: {parsed_data}")
        
        # Try to extract payload
        if 'payload' in parsed_data:
            payload_str = parsed_data['payload'][0]
            try:
                payload = json.loads(urllib.parse.unquote(payload_str))
                logger.info(f"Parsed payload: {json.dumps(payload, indent=2)}")
            except Exception as e:
                logger.error(f"Failed to parse payload: {e}")
        
        logger.info("=" * 60)
        
        return {
            "status": "logged",
            "message": "Check server logs for detailed information",
            "body_length": len(body_str),
            "has_payload": 'payload' in parsed_data
        }
    except Exception as e:
        logger.error(f"Debug endpoint error: {e}", exc_info=True)
        return {"error": str(e)}

