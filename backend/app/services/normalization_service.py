"""
Grant normalization service for generating curated/canonical versions of grant data.

This service generates draft normalizations (canonical_title, canonical_summary, timeline_status)
from raw grant data using Claude API. Normalizations are presented for admin approval
via Slack before being saved to the database.

Ethics: Normalization describes the grant. Evaluation judges the grant relative to a user.
Never merge those layers.
"""

import json
import re
from typing import Dict, Optional
from datetime import datetime
from anthropic import Anthropic
from app.core.config import settings


class NormalizationService:
    """Service for generating grant normalizations (canonical presentation fields)."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the normalization service."""
        api_key = api_key or settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable."
            )
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-haiku-20240307"  # Using Haiku for cost efficiency
    
    def generate_normalization(self, grant: Dict) -> Dict:
        """
        Generate draft normalization for a grant.
        
        Creates:
        - canonical_title: Standardized title (clean, consistent format)
        - canonical_summary: One-paragraph summary (concise, neutral)
        - timeline_status: 'active', 'closed', 'rolling', or 'unknown'
        - confidence_level: 'high', 'medium', or 'low' (based on how explicit the data is)
        
        Args:
            grant: Dictionary with grant data (name, description, deadline, etc.)
            
        Returns:
            Dictionary with normalization fields:
            {
                'canonical_title': str,
                'canonical_summary': str,
                'timeline_status': 'active'|'closed'|'rolling'|'unknown',
                'confidence_level': 'high'|'medium'|'low'
            }
        """
        # Prepare grant context for Claude
        grant_context = self._prepare_grant_context(grant)
        
        # Generate normalization using Claude
        normalization = self._generate_with_claude(grant_context)
        
        return normalization
    
    def _prepare_grant_context(self, grant: Dict) -> str:
        """Prepare grant context string for Claude."""
        context_parts = []
        
        if grant.get('name'):
            context_parts.append(f"Name: {grant['name']}")
        if grant.get('description'):
            context_parts.append(f"Description: {grant['description'][:1000]}...")  # Limit length
        if grant.get('mission'):
            context_parts.append(f"Mission: {grant['mission'][:500]}...")
        if grant.get('deadline'):
            context_parts.append(f"Deadline: {grant['deadline']}")
        if grant.get('decision_date'):
            context_parts.append(f"Decision Date: {grant['decision_date']}")
        if grant.get('award_amount'):
            context_parts.append(f"Award Amount: {grant['award_amount']}")
        
        return "\n".join(context_parts)
    
    def _generate_with_claude(self, grant_context: str) -> Dict:
        """
        Use Claude API to generate normalization fields.
        
        Args:
            grant_context: Formatted grant information
            
        Returns:
            Dictionary with normalization fields
        """
        system_prompt = """You are a grant information normalization assistant. Your job is to create clean, standardized presentation fields from raw grant data.

Your task is to:
1. Create a canonical_title: Standardized, clean title (remove extra formatting, consistent capitalization)
   - Extract year if present (e.g., "Sustainable Communities Grant (2026)")
   - Remove redundant prefixes like "CFP:", "RFP:", etc.
   - Keep it clear and concise (max 150 chars)

2. Create a canonical_summary: One-paragraph summary (2-4 sentences, neutral tone)
   - Based on description and mission
   - Focus on what the grant offers, who it's for
   - Do NOT add evaluation/judgment (no "worth applying", "good fit", etc.)
   - Simply describe the grant objectively

3. Determine timeline_status:
   - 'active': Clear deadline in the future
   - 'closed': Deadline has passed or explicitly closed
   - 'rolling': Rolling applications, no fixed deadline
   - 'unknown': Cannot determine from available information

4. Set confidence_level:
   - 'high': Information explicitly stated (clear deadline, explicit status)
   - 'medium': Information inferred but reasonably certain
   - 'low': Information uncertain or missing

Return ONLY valid JSON in this format:
{
  "canonical_title": "string (standardized title)",
  "canonical_summary": "string (one paragraph, 2-4 sentences)",
  "timeline_status": "active" | "closed" | "rolling" | "unknown",
  "confidence_level": "high" | "medium" | "low"
}

Be accurate. Only use information that is clearly stated. For timeline_status, prefer 'unknown' over guessing."""

        user_message = f"""Generate normalization for this grant:

{grant_context}

Create canonical_title, canonical_summary, timeline_status, and confidence_level. Return as JSON."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )
            
            # Extract JSON from response
            response_text = message.content[0].text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            
            if response_text.endswith("```"):
                response_text = response_text[:-3].strip()
            
            # Parse JSON
            try:
                normalization_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                # Try to extract JSON from text if wrapped
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    normalization_data = json.loads(json_match.group())
                else:
                    raise ValueError(f"Failed to parse Claude response as JSON: {e}")
            
            # Validate and clean the data
            return self._validate_normalization(normalization_data)
            
        except Exception as e:
            error_msg = str(e)
            # Provide fallback normalization if Claude fails
            logger = __import__('logging').getLogger(__name__)
            logger.warning(f"Normalization generation failed: {error_msg}")
            
            # Return fallback with low confidence
            return {
                'canonical_title': None,  # Will use raw title
                'canonical_summary': None,  # Will use description
                'timeline_status': 'unknown',
                'confidence_level': 'low'
            }
    
    def _validate_normalization(self, data: Dict) -> Dict:
        """
        Validate and clean normalization data.
        
        Args:
            data: Raw normalization data from Claude
            
        Returns:
            Validated normalization data
        """
        # Validate timeline_status
        valid_timeline_statuses = ['active', 'closed', 'rolling', 'unknown']
        timeline_status = data.get('timeline_status', 'unknown')
        if timeline_status not in valid_timeline_statuses:
            timeline_status = 'unknown'
        
        # Validate confidence_level
        valid_confidence_levels = ['high', 'medium', 'low']
        confidence_level = data.get('confidence_level', 'low')
        if confidence_level not in valid_confidence_levels:
            confidence_level = 'low'
        
        # Clean canonical_title (limit length, remove None)
        canonical_title = data.get('canonical_title')
        if canonical_title:
            canonical_title = canonical_title.strip()[:150]  # Max 150 chars
            if not canonical_title:
                canonical_title = None
        
        # Clean canonical_summary (limit length, remove None)
        canonical_summary = data.get('canonical_summary')
        if canonical_summary:
            canonical_summary = canonical_summary.strip()[:1000]  # Max 1000 chars
            if not canonical_summary:
                canonical_summary = None
        
        return {
            'canonical_title': canonical_title,
            'canonical_summary': canonical_summary,
            'timeline_status': timeline_status,
            'confidence_level': confidence_level
        }
    
    def infer_timeline_status(self, deadline: Optional[str], decision_date: Optional[str]) -> tuple[str, str]:
        """
        Infer timeline status from deadline/decision_date (fallback method).
        
        Args:
            deadline: Deadline string
            decision_date: Decision date string
            
        Returns:
            Tuple of (timeline_status, confidence_level)
        """
        if not deadline and not decision_date:
            return ('unknown', 'low')
        
        deadline_lower = (deadline or '').lower()
        
        # Check for rolling status indicators
        rolling_indicators = ['rolling', 'ongoing', 'open until', 'no deadline', 'continuous']
        if any(indicator in deadline_lower for indicator in rolling_indicators):
            return ('rolling', 'medium')
        
        # Try to parse date (basic check)
        # For now, assume if there's a date string, it's likely active (unless past)
        # More sophisticated date parsing could be added later
        if deadline:
            return ('active', 'low')  # Low confidence without actual date parsing
        
        return ('unknown', 'low')
