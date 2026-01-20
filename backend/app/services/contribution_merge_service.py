"""
Contribution Merge Service

Handles merging approved user contributions into Grant records with proper:
- Field mapping (contribution field_name → Grant column)
- Data validation and sanitization
- Provenance tracking in recipient_patterns JSONB
- Automatic bucket recomputation after merge
- Conflict resolution (when grant already has data)
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db import models
from app.core.sanitization import sanitize_text, sanitize_html
from app.services.decision_readiness_service import DecisionReadinessService

logger = logging.getLogger(__name__)


# ============================================================================
# FIELD MAPPING TABLE
# ============================================================================

# Direct scalar field mappings (contribution.field_name → Grant column)
SCALAR_FIELD_MAPPING = {
    'award_amount': 'award_amount',  # String field
    'deadline': 'deadline',  # String field
    'decision_date': 'decision_date',  # String field
    'eligibility': 'eligibility',  # Text field
    'preferred_applicants': 'preferred_applicants',  # Text field
    'award_structure': 'award_structure',  # Text field
    'mission': 'mission',  # Text field
    'description': 'description',  # Text field
    'application_requirements': 'application_requirements',  # JSON field (list of strings)
}

# Fields that go into recipient_patterns JSONB (structured data)
RECIPIENT_PATTERNS_FIELDS = {
    'acceptance_rate': {
        'path': ['competition_stats', 'acceptance_rate'],
        'source_key': 'acceptance_rate_source',
        'type': 'string',  # e.g., "12%" or "~15%"
    },
    'past_recipients': {
        'path': ['recipients'],  # Array of recipient objects
        'source_key': 'recipients_source',
        'type': 'array',  # List of dicts with organization_type, country, career_stage, etc.
    },
    'applications_received': {
        'path': ['competition_stats', 'applications_received'],
        'source_key': 'competition_stats_source',
        'type': 'integer',
    },
    'awards_made': {
        'path': ['competition_stats', 'awards_made'],
        'source_key': 'competition_stats_source',
        'type': 'integer',
    },
}

# Fields that require special handling (not in mapping above)
SPECIAL_FIELDS = {
    'other': None,  # Admin must manually review and decide where to place
}


class ContributionMergeService:
    """Service for merging approved contributions into Grant records."""
    
    @staticmethod
    def get_field_mapping() -> Dict[str, Any]:
        """
        Return the complete field mapping table for reference.
        
        Returns:
            Dict with:
            - scalar_fields: Direct Grant column mappings
            - recipient_patterns_fields: Fields that go into JSONB
            - special_fields: Fields requiring manual review
        """
        return {
            'scalar_fields': SCALAR_FIELD_MAPPING,
            'recipient_patterns_fields': RECIPIENT_PATTERNS_FIELDS,
            'special_fields': SPECIAL_FIELDS,
        }
    
    @staticmethod
    def validate_contribution_data(
        field_name: str,
        field_value: str,
        grant: Optional[models.Grant] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate contribution data before merging.
        
        Args:
            field_name: The contribution field name
            field_value: The raw value from contribution
            grant: Optional grant to check for conflicts
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if field is mappable
        if field_name not in SCALAR_FIELD_MAPPING and field_name not in RECIPIENT_PATTERNS_FIELDS:
            if field_name == 'other':
                return True, None  # 'other' requires manual review, but is valid
            return False, f"Unknown field_name: {field_name}. Must be one of: {', '.join(list(SCALAR_FIELD_MAPPING.keys()) + list(RECIPIENT_PATTERNS_FIELDS.keys()) + ['other'])}"
        
        # Validate field_value is not empty
        if not field_value or not field_value.strip():
            return False, "field_value cannot be empty"
        
        # Validate length
        if len(field_value) > 10000:  # Reasonable limit
            return False, f"field_value too long (max 10000 characters, got {len(field_value)})"
        
        # Type-specific validation for recipient_patterns fields
        if field_name in RECIPIENT_PATTERNS_FIELDS:
            field_config = RECIPIENT_PATTERNS_FIELDS[field_name]
            
            if field_config['type'] == 'array':
                # Try to parse as JSON array
                try:
                    parsed = json.loads(field_value)
                    if not isinstance(parsed, list):
                        return False, f"past_recipients must be a JSON array, got {type(parsed).__name__}"
                    # Validate array items are objects
                    for item in parsed:
                        if not isinstance(item, dict):
                            return False, "past_recipients array items must be objects"
                except json.JSONDecodeError:
                    # If not JSON, treat as plain text (will be stored as text, not structured)
                    pass
            
            elif field_config['type'] == 'integer':
                try:
                    int(field_value)
                except ValueError:
                    return False, f"{field_name} must be a valid integer"
        
        # Check for conflicts (if grant already has this data)
        if grant:
            if field_name in SCALAR_FIELD_MAPPING:
                grant_field = SCALAR_FIELD_MAPPING[field_name]
                existing_value = getattr(grant, grant_field, None)
                if existing_value and existing_value.strip():
                    # Conflict exists - but we'll still allow merge (admin approved it)
                    logger.info(f"Conflict detected: grant {grant.id} already has {grant_field}={existing_value[:50]}...")
        
        return True, None
    
    @staticmethod
    def merge_contribution_into_grant(
        contribution: models.GrantDataContribution,
        grant: models.Grant,
        admin_user_id: Optional[int] = None,
        admin_notes: Optional[str] = None,
        db: Session = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Merge an approved contribution into a grant record.
        
        This is the main merge function that:
        1. Validates the contribution data
        2. Maps field_name to Grant column or recipient_patterns path
        3. Sanitizes and stores the data
        4. Tracks provenance (source, admin, timestamp)
        5. Recomputes all bucket states and derived fields
        6. Updates contribution status to 'merged'
        
        Args:
            contribution: The approved contribution to merge
            grant: The grant record to merge into
            admin_user_id: ID of admin performing the merge
            admin_notes: Optional notes about the merge
            db: Database session (required for commit)
            
        Returns:
            Tuple of (success, error_message)
        """
        if not db:
            return False, "Database session required for merge"
        
        try:
            # 1. Validate contribution data
            is_valid, error_msg = ContributionMergeService.validate_contribution_data(
                contribution.field_name,
                contribution.field_value,
                grant
            )
            if not is_valid:
                return False, error_msg
            
            # 2. Determine merge target
            field_name = contribution.field_name
            
            # Handle recipient_patterns fields (JSONB)
            if field_name in RECIPIENT_PATTERNS_FIELDS:
                success, error = ContributionMergeService._merge_into_recipient_patterns(
                    contribution, grant, admin_user_id
                )
                if not success:
                    return False, error
            
            # Handle scalar fields (direct Grant columns)
            elif field_name in SCALAR_FIELD_MAPPING:
                success, error = ContributionMergeService._merge_into_scalar_field(
                    contribution, grant, admin_user_id
                )
                if not success:
                    return False, error
            
            # Handle 'other' field (requires manual placement - just mark as approved, don't merge)
            elif field_name == 'other':
                logger.info(f"Contribution {contribution.id} is 'other' field - requires manual review, marking as approved only")
                contribution.status = 'approved'
                contribution.admin_notes = admin_notes or f"Approved but requires manual placement (field: 'other')"
                contribution.reviewed_by = admin_user_id
                contribution.reviewed_at = datetime.now(timezone.utc)
                db.commit()
                return True, None
            
            else:
                return False, f"Unknown field_name: {field_name}"
            
            # 3. Update contribution status
            contribution.status = 'merged'
            contribution.reviewed_by = admin_user_id
            contribution.reviewed_at = datetime.now(timezone.utc)
            contribution.admin_notes = admin_notes or f"Merged via admin interface"
            
            # 4. Recompute all bucket states and derived fields
            try:
                ContributionMergeService._recompute_grant_buckets(grant, db)
                logger.info(f"Successfully recomputed buckets for grant {grant.id} after merging contribution {contribution.id}")
            except Exception as bucket_error:
                # Log but don't fail - bucket recomputation is important but merge should succeed
                logger.error(f"Failed to recompute buckets after merge: {bucket_error}", exc_info=True)
                # Continue - buckets can be recomputed later
            
            # 5. Commit all changes
            db.commit()
            db.refresh(grant)
            db.refresh(contribution)
            
            logger.info(
                f"✅ Successfully merged contribution {contribution.id} (field: {field_name}) "
                f"into grant {grant.id}. Status: {contribution.status}"
            )
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error merging contribution {contribution.id} into grant {grant.id}: {e}", exc_info=True)
            db.rollback()
            return False, f"Merge failed: {str(e)}"
    
    @staticmethod
    def _merge_into_scalar_field(
        contribution: models.GrantDataContribution,
        grant: models.Grant,
        admin_user_id: Optional[int]
    ) -> Tuple[bool, Optional[str]]:
        """Merge contribution into a scalar Grant field."""
        field_name = contribution.field_name
        grant_field = SCALAR_FIELD_MAPPING[field_name]
        raw_value = contribution.field_value
        
        try:
            # Sanitize based on field type
            if grant_field in ['eligibility', 'preferred_applicants', 'award_structure', 'mission', 'description']:
                # HTML/text fields - sanitize HTML
                sanitized_value = sanitize_html(raw_value)
            else:
                # Plain text fields (deadline, decision_date, award_amount)
                sanitized_value = sanitize_text(raw_value)
            
            # Handle JSON fields (application_requirements)
            if grant_field == 'application_requirements':
                try:
                    # Try to parse as JSON array
                    parsed = json.loads(sanitized_value)
                    if isinstance(parsed, list):
                        # Validate all items are strings
                        sanitized_value = [sanitize_text(str(item)) for item in parsed]
                    else:
                        # Single value - wrap in list
                        sanitized_value = [sanitize_text(sanitized_value)]
                except (json.JSONDecodeError, ValueError):
                    # Not JSON - treat as single string, wrap in list
                    sanitized_value = [sanitize_text(sanitized_value)]
            
            # Set the field
            setattr(grant, grant_field, sanitized_value)
            
            logger.info(f"Merged {field_name} into grant {grant.id}, field: {grant_field}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error merging scalar field {field_name}: {e}", exc_info=True)
            return False, f"Failed to merge scalar field: {str(e)}"
    
    @staticmethod
    def _merge_into_recipient_patterns(
        contribution: models.GrantDataContribution,
        grant: models.Grant,
        admin_user_id: Optional[int]
    ) -> Tuple[bool, Optional[str]]:
        """Merge contribution into recipient_patterns JSONB field with provenance tracking."""
        field_name = contribution.field_name
        field_config = RECIPIENT_PATTERNS_FIELDS[field_name]
        raw_value = contribution.field_value
        
        try:
            # Get or initialize recipient_patterns
            recipient_patterns = grant.recipient_patterns or {}
            
            # Parse value based on type
            if field_config['type'] == 'array':
                # Try to parse as JSON array of recipient objects
                try:
                    parsed = json.loads(raw_value)
                    if isinstance(parsed, list):
                        # Validate and sanitize recipient objects
                        sanitized_recipients = []
                        for recipient in parsed:
                            if isinstance(recipient, dict):
                                # Sanitize string fields in recipient object
                                sanitized = {}
                                for key, value in recipient.items():
                                    if isinstance(value, str):
                                        sanitized[key] = sanitize_text(value)
                                    elif isinstance(value, list) and key == "project_theme":
                                        # Sanitize project_theme array items
                                        sanitized[key] = [sanitize_text(str(item)) for item in value if item]
                                    else:
                                        sanitized[key] = value
                                sanitized_recipients.append(sanitized)
                            else:
                                return False, "Recipient array items must be objects"
                        
                        # Merge with existing recipients (avoid duplicates by name/year if present)
                        existing_recipients = recipient_patterns.get('recipients', [])
                        if not isinstance(existing_recipients, list):
                            existing_recipients = []
                        
                        # Simple merge: append new recipients (admin can dedupe later if needed)
                        merged_recipients = existing_recipients + sanitized_recipients
                        recipient_patterns['recipients'] = merged_recipients
                    else:
                        return False, "past_recipients must be a JSON array"
                except json.JSONDecodeError:
                    # Not JSON - store as plain text (legacy format)
                    recipient_patterns['past_recipients'] = sanitize_text(raw_value)
            
            elif field_config['type'] == 'integer':
                try:
                    parsed_value = int(raw_value)
                    # Navigate to path and set value
                    _set_nested_value(recipient_patterns, field_config['path'], parsed_value)
                except ValueError:
                    return False, f"{field_name} must be a valid integer"
            
            elif field_config['type'] == 'string':
                # String value (e.g., acceptance_rate: "12%")
                sanitized_value = sanitize_text(raw_value)
                _set_nested_value(recipient_patterns, field_config['path'], sanitized_value)
            
            # Track provenance
            source_key = field_config.get('source_key')
            if source_key:
                # Store source metadata
                provenance = {
                    'source': 'user_contribution',
                    'contribution_id': contribution.id,
                    'user_id': contribution.user_id,
                    'admin_id': admin_user_id,
                    'merged_at': datetime.now(timezone.utc).isoformat(),
                    'source_url': contribution.source_url,
                }
                recipient_patterns[source_key] = provenance
            
            # Update grant
            grant.recipient_patterns = recipient_patterns
            
            logger.info(f"Merged {field_name} into recipient_patterns for grant {grant.id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error merging into recipient_patterns: {e}", exc_info=True)
            return False, f"Failed to merge into recipient_patterns: {str(e)}"
    
    @staticmethod
    def _recompute_grant_buckets(grant: models.Grant, db: Session) -> None:
        """
        Recompute all bucket states and derived fields for a grant.
        
        This is called after any data merge to ensure buckets stay accurate.
        """
        # Convert grant to dict for service
        grant_dict = {
            'deadline': grant.deadline,
            'decision_date': grant.decision_date,
            'award_amount': grant.award_amount,
            'award_structure': grant.award_structure,
            'mission': grant.mission,
            'preferred_applicants': grant.preferred_applicants,
            'eligibility': grant.eligibility,
            'application_requirements': grant.application_requirements,
            'recipient_patterns': grant.recipient_patterns or {},
            'description': grant.description,
        }
        
        # Compute all bucket states and derived fields
        results = DecisionReadinessService.compute_all_buckets(grant_dict)
        
        # Infer scope
        scope, _ = DecisionReadinessService.infer_scope(grant_dict)
        
        # Update grant with computed values
        grant.timeline_clarity = results['timeline_clarity']
        grant.winner_signal = results['winner_signal']
        grant.mission_specificity = results['mission_specificity']
        grant.application_burden = results['application_burden']
        grant.award_structure_clarity = results['award_structure_clarity']
        grant.decision_readiness = results['decision_readiness']
        grant.status_of_knowledge = results['status_of_knowledge']
        grant.scope = scope
        grant.evaluation_complete = True


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _set_nested_value(obj: Dict[str, Any], path: List[str], value: Any) -> None:
    """
    Set a value in a nested dictionary using a path list.
    
    Example:
        _set_nested_value(data, ['competition_stats', 'acceptance_rate'], '12%')
        # Sets data['competition_stats']['acceptance_rate'] = '12%'
    """
    current = obj
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[path[-1]] = value
