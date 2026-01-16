"""
Slack service for admin orchestration.

Slack is NOT part of core application logic.
Slack exists only as a human-in-the-loop governance interface.

Allowed actions only:
1. Grant Index Inclusion (approve/reject)
2. Payment Issue Acknowledgement
3. Flag Review
"""

import hmac
import hashlib
import time
import json
from typing import Optional, Dict
from app.core.config import settings


def verify_slack_request(timestamp: str, signature: str, body: bytes) -> bool:
    """
    Verify Slack request signature using signing secret.
    
    Args:
        timestamp: Request timestamp header
        signature: Request signature header
        body: Raw request body bytes
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not settings.SLACK_SIGNING_SECRET:
        return False
    
    # Reject stale requests (>5 minutes old)
    try:
        request_time = int(timestamp)
        current_time = int(time.time())
        if abs(current_time - request_time) > 60 * 5:
            return False
    except ValueError:
        return False
    
    # Reconstruct signature
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    computed_signature = 'v0=' + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison
    return hmac.compare_digest(computed_signature, signature)


def verify_slack_workspace(team_id: str) -> bool:
    """
    Verify request is from allowed Slack workspace.
    
    Args:
        team_id: Slack team/workspace ID
        
    Returns:
        True if workspace is allowlisted, False otherwise
    """
    if not settings.SLACK_WORKSPACE_ID:
        # If not configured, log the ID for user to add and ALLOW temporarily
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"⚠️  SLACK_WORKSPACE_ID not set in .env. "
            f"Received workspace ID: {team_id} - ADD THIS TO YOUR .env FILE!"
        )
        print(f"\n{'='*60}")
        print(f"⚠️  YOUR SLACK WORKSPACE ID: {team_id}")
        print(f"Add this to backend/.env:")
        print(f"SLACK_WORKSPACE_ID={team_id}")
        print(f"{'='*60}\n")
        # Temporarily allow if not configured (for discovery)
        return True
    return team_id == settings.SLACK_WORKSPACE_ID


def verify_slack_admin(user_id: str) -> bool:
    """
    Verify user is in admin allowlist.
    
    Args:
        user_id: Slack user ID
        
    Returns:
        True if user is allowlisted admin, False otherwise
    """
    if not settings.SLACK_ADMIN_USER_IDS:
        return False
    
    allowed_users = [uid.strip() for uid in settings.SLACK_ADMIN_USER_IDS.split(',')]
    return user_id in allowed_users


def send_grant_approval_notification(
    grant_id: int, 
    grant_name: str, 
    grant_url: str,
    draft_normalization: Optional[Dict] = None
) -> None:
    """
    Send Slack notification for pending grant approval with draft normalization.
    
    This is a notification only. Action must come from Slack button click.
    
    Args:
        grant_id: Grant ID
        grant_name: Grant name
        grant_url: Grant source URL
        draft_normalization: Optional draft normalization dict with:
            - canonical_title: str
            - canonical_summary: str
            - timeline_status: 'active'|'closed'|'rolling'|'unknown'
            - confidence_level: 'high'|'medium'|'low'
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not settings.SLACK_WEBHOOK_URL:
        logger.warning(f"SLACK_WEBHOOK_URL not configured - cannot send notification for grant {grant_id}")
        print(f"\n⚠️  SLACK_WEBHOOK_URL not set in .env - Slack notifications disabled\n")
        return  # Slack not configured
    
    import httpx
    
    # Build message text with draft normalization
    message_text = f"*Grant Index Inclusion Request*\n\n"
    message_text += f"*Source Name:* {grant_name}\n"
    message_text += f"*URL:* {grant_url}\n"
    message_text += f"*Grant ID:* `{grant_id}`\n"
    
    # Add draft normalization fields if available
    if draft_normalization:
        message_text += f"\n*📝 Draft Normalization:*\n"
        
        if draft_normalization.get('canonical_title'):
            message_text += f"*Suggested Title:* {draft_normalization['canonical_title']}\n"
        else:
            message_text += f"*Suggested Title:* (use source name)\n"
        
        if draft_normalization.get('canonical_summary'):
            summary = draft_normalization['canonical_summary'][:200]  # Limit length
            if len(draft_normalization['canonical_summary']) > 200:
                summary += "..."
            message_text += f"*Suggested Summary:* {summary}\n"
        
        timeline_status = draft_normalization.get('timeline_status', 'unknown')
        confidence = draft_normalization.get('confidence_level', 'low')
        timeline_emoji = {
            'active': '🟢',
            'closed': '🔴',
            'rolling': '🔄',
            'unknown': '⚪'
        }.get(timeline_status, '⚪')
        message_text += f"*Timeline Status:* {timeline_emoji} {timeline_status.title()} (confidence: {confidence})\n"
    else:
        message_text += f"\n*Note:* Draft normalization not available (will use source data)\n"
    
    # Simple message with approve/reject buttons
    payload = {
        "text": f"New grant pending approval: {grant_name}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message_text
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Approve"
                        },
                        "style": "primary",
                        "value": f"grant_{grant_id}_approve",
                        "action_id": "grant_approve"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Reject"
                        },
                        "style": "danger",
                        "value": f"grant_{grant_id}_reject",
                        "action_id": "grant_reject"
                    }
                ]
            }
        ]
    }
    
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(settings.SLACK_WEBHOOK_URL, json=payload)
            response.raise_for_status()
            logger.info(f"Successfully sent Slack notification for grant {grant_id}")
            print(f"✓ Slack notification sent for grant {grant_id}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Slack API returned error {e.response.status_code}: {e.response.text}")
        print(f"❌ Slack API error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Failed to send Slack notification for grant {grant_id}: {str(e)}")
        print(f"❌ Failed to send Slack notification: {str(e)}")
        # Don't fail the request - Slack notifications are non-critical


def send_support_request_notification(
    request_id: int,
    issue_type: str,
    user_email: str,
    description: str,
    payment_id: Optional[int] = None,
    evaluation_id: Optional[int] = None
) -> None:
    """
    Send Slack notification for support request (Flag Review).
    
    This is a notification only - support requests require admin review via other channels.
    
    Args:
        request_id: Support request ID
        issue_type: Type of issue (duplicate_payment, technical_error, etc.)
        user_email: User's email
        description: Issue description
        payment_id: Optional payment ID
        evaluation_id: Optional evaluation ID
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not settings.SLACK_WEBHOOK_URL:
        logger.warning(f"SLACK_WEBHOOK_URL not configured - cannot send support request notification")
        return
    
    import httpx
    
    # Format issue type for display
    issue_display = issue_type.replace('_', ' ').title()
    
    # Build message
    message_text = f"*Support Request #{request_id}*\n\n"
    message_text += f"*Type:* {issue_display}\n"
    message_text += f"*User:* {user_email}\n"
    if payment_id:
        message_text += f"*Payment ID:* `{payment_id}`\n"
    if evaluation_id:
        message_text += f"*Evaluation ID:* `{evaluation_id}`\n"
    message_text += f"\n*Description:*\n{description[:200]}{'...' if len(description) > 200 else ''}"
    
    payload = {
        "text": f"New Support Request: {issue_display}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message_text
                }
            }
        ]
    }
    
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(settings.SLACK_WEBHOOK_URL, json=payload)
            response.raise_for_status()
            logger.info(f"Successfully sent Slack notification for support request {request_id}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Slack API returned error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        logger.error(f"Failed to send Slack notification for support request {request_id}: {str(e)}")
        # Non-critical - email notification still sent


def parse_button_value(value: str) -> Optional[Dict[str, str]]:
    """
    Parse Slack button value to extract entity and action.
    
    Format: "{entity_type}_{entity_id}_{action}"
    Example: "grant_123_approve"
    
    Args:
        value: Button value string
        
    Returns:
        Dict with entity_type, entity_id, action, or None if invalid
    """
    parts = value.split('_')
    if len(parts) != 3:
        return None
    
    entity_type, entity_id_str, action = parts
    
    # Validate entity types (strict allowlist)
    if entity_type not in ['grant']:
        return None
    
    # Validate actions (strict allowlist)
    if action not in ['approve', 'reject']:
        return None
    
    try:
        entity_id = int(entity_id_str)
    except ValueError:
        return None
    
    return {
        'entity_type': entity_type,
        'entity_id': entity_id,
        'action': action
    }

