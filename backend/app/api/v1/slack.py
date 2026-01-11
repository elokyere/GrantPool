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
from datetime import datetime

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
        
        # Execute action (strict allowlist)
        if entity_type == "grant" and action_id in ["grant_approve", "grant_reject"]:
            # Process the action and return response
            # Note: Must return within 3 seconds, so keep database operations fast
            return await _handle_grant_approval(
                grant_id=entity_id,
                action=action_type,
                slack_user_id=user_id,
                db=db
            )
        
        # Unknown action - return error message
        logger.warning(f"Unknown Slack action: {action_id}")
        return Response(
            status_code=200,
            content=json.dumps({
                "response_type": "ephemeral",
                "text": f"Unknown action: {action_id}"
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
            grant.approved_at = datetime.now()
            logger.info(f"Setting grant {grant_id} status to 'approved'")
            # Note: approved_by requires User model lookup - simplified for now
            # In production, map slack_user_id to User ID or store slack_user_id
            
        elif action == "reject":
            grant.approval_status = "rejected"
            grant.approved_at = datetime.now()
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
            f"at {datetime.now()}"
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

