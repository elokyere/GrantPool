"""
Decision Readiness Service

Computes the 5 bucket states and derived fields for grant decision readiness.
Replaces opaque "Data: X/10" scores with explainable uncertainty indicators.
"""

import re
from typing import Dict, Any, Literal, Optional, Tuple
from enum import Enum


BucketState = Literal['known', 'partial', 'unknown']


class DecisionReadinessService:
    """Service for computing grant decision readiness indicators."""
    
    @staticmethod
    def compute_timeline_clarity(grant: Dict[str, Any]) -> Tuple[BucketState, str]:
        """
        Compute timeline clarity bucket state.
        
        🟢 Known: Deadline date parsed
        🟡 Partial: Rolling or vague language ("ongoing")
        🔴 Unknown: No timing info found
        
        Returns:
            Tuple of (state, explanation)
        """
        deadline = grant.get("deadline")
        decision_date = grant.get("decision_date")
        
        if not deadline and not decision_date:
            return ('unknown', 'No timing information found')
        
        deadline_lower = (deadline or "").lower().strip()
        decision_lower = (decision_date or "").lower().strip()
        
        # Check for rolling/vague language
        vague_terms = ['rolling', 'ongoing', 'open until', 'no deadline', 'continuous', 'always open']
        is_vague = any(term in deadline_lower for term in vague_terms)
        
        # Check if we have a specific date (contains numbers that look like dates)
        has_specific_date = False
        if deadline:
            # Look for date patterns: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, or month names with numbers
            date_patterns = [
                r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
                r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # MM/DD/YYYY or DD/MM/YYYY
                r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',  # Month name + day
            ]
            for pattern in date_patterns:
                if re.search(pattern, deadline, re.IGNORECASE):
                    has_specific_date = True
                    break
        
        if has_specific_date and not is_vague:
            explanation = f"Deadline: {deadline}"
            if decision_date:
                explanation += f", Decision: {decision_date}"
            return ('known', explanation)
        elif is_vague or (deadline and not has_specific_date):
            return ('partial', f"Timing: {deadline or 'ongoing'} (vague or rolling)")
        else:
            return ('partial', f"Some timing info available but unclear")
    
    @staticmethod
    def compute_winner_signal(grant: Dict[str, Any]) -> Tuple[BucketState, str]:
        """
        Compute winner signal bucket state.
        
        🟢 Known: Named past recipients
        🟡 Partial: Aggregate stats only
        🔴 Unknown: Nothing public
        
        Returns:
            Tuple of (state, explanation)
        """
        recipient_patterns = grant.get("recipient_patterns") or {}
        recipients = recipient_patterns.get("recipients") or []
        competition_stats = recipient_patterns.get("competition_stats") or {}
        
        # Check for named recipients
        if recipients and isinstance(recipients, list):
            # Count recipients with meaningful data
            named_recipients = [r for r in recipients if isinstance(r, dict) and (
                r.get("career_stage") or 
                r.get("organization_type") or 
                r.get("country") or
                r.get("name")  # Some grants list recipient names
            )]
            
            if len(named_recipients) >= 1:
                return ('known', f"{len(named_recipients)} past recipient{'s' if len(named_recipients) > 1 else ''} found")
        
        # Check for aggregate stats
        has_stats = any([
            competition_stats.get("applications_received"),
            competition_stats.get("awards_made"),
            competition_stats.get("acceptance_rate")
        ])
        
        if has_stats:
            return ('partial', 'Aggregate competition statistics available, but no individual recipient data')
        
        return ('unknown', 'No public recipient data found')
    
    @staticmethod
    def compute_mission_specificity(grant: Dict[str, Any]) -> Tuple[BucketState, str]:
        """
        Compute mission specificity bucket state.
        
        🟢 Known: Narrow domain + explicit priorities
        🟡 Partial: Broad mission with examples
        🔴 Unknown: Generic "innovation / impact" language
        
        Returns:
            Tuple of (state, explanation)
        """
        mission = (grant.get("mission") or "").strip()
        preferred_applicants = (grant.get("preferred_applicants") or "").strip()
        eligibility = (grant.get("eligibility") or "").strip()
        
        combined_text = f"{mission} {preferred_applicants} {eligibility}".lower()
        
        if not combined_text or len(combined_text.strip()) < 20:
            return ('unknown', 'No mission or priority information found')
        
        # Check for generic/vague language
        generic_terms = [
            'innovation', 'impact', 'positive change', 'make a difference',
            'support', 'help', 'improve', 'advance', 'promote'
        ]
        generic_count = sum(1 for term in generic_terms if term in combined_text)
        
        # Check for specific/domain language
        specific_indicators = [
            'sector', 'field', 'discipline', 'geographic', 'population',
            'target', 'focus area', 'priority', 'theme', 'category'
        ]
        specific_count = sum(1 for term in specific_indicators if term in combined_text)
        
        # Check for explicit priorities or examples
        has_examples = any([
            'example' in combined_text,
            'including' in combined_text,
            'such as' in combined_text,
            'focus on' in combined_text,
            'priority' in combined_text
        ])
        
        # Determine state
        if specific_count >= 2 and (has_examples or len(mission) > 100):
            return ('known', 'Narrow domain with explicit priorities or examples')
        elif specific_count >= 1 or has_examples or len(mission) > 50:
            return ('partial', 'Broad mission with some specificity or examples')
        elif generic_count >= 2:
            return ('unknown', 'Generic mission language without specific focus')
        else:
            return ('partial', 'Mission information available but clarity unclear')
    
    @staticmethod
    def compute_application_burden(grant: Dict[str, Any]) -> Tuple[BucketState, str]:
        """
        Compute application burden bucket state.
        
        🟢 Known: Length + steps disclosed
        🟡 Partial: Partial info
        🔴 Unknown: No application detail
        
        Returns:
            Tuple of (state, explanation)
        """
        application_requirements = grant.get("application_requirements") or []
        
        # Convert to list if it's a string
        if isinstance(application_requirements, str):
            # Try to parse as JSON or split by newlines
            try:
                import json
                application_requirements = json.loads(application_requirements)
            except:
                application_requirements = [application_requirements] if application_requirements else []
        
        if not application_requirements or len(application_requirements) == 0:
            return ('unknown', 'No application requirements information found')
        
        # Check for length/steps information
        requirements_text = ' '.join(str(req) for req in application_requirements).lower()
        
        has_length_info = any([
            'page' in requirements_text,
            'word' in requirements_text,
            'character' in requirements_text,
            'length' in requirements_text,
            'limit' in requirements_text
        ])
        
        has_steps_info = any([
            'step' in requirements_text,
            'stage' in requirements_text,
            'phase' in requirements_text,
            'round' in requirements_text
        ])
        
        has_docs_info = any([
            'document' in requirements_text,
            'letter' in requirements_text,
            'reference' in requirements_text,
            'cv' in requirements_text,
            'resume' in requirements_text,
            'portfolio' in requirements_text
        ])
        
        # Count how many types of info we have
        info_count = sum([has_length_info, has_steps_info, has_docs_info])
        
        if info_count >= 2:
            details = []
            if has_length_info:
                details.append('length')
            if has_steps_info:
                details.append('steps')
            if has_docs_info:
                details.append('documents')
            return ('known', f"Application details disclosed: {', '.join(details)}")
        elif info_count == 1 or len(application_requirements) > 0:
            return ('partial', f"{len(application_requirements)} requirement(s) listed, but details incomplete")
        else:
            return ('unknown', 'Application requirements mentioned but no detail available')
    
    @staticmethod
    def compute_award_structure_clarity(grant: Dict[str, Any]) -> Tuple[BucketState, str]:
        """
        Compute award structure clarity bucket state.
        
        🟢 Known: Amount + terms clear
        🟡 Partial: Range or conditional amounts
        🔴 Unknown: No award info
        
        Returns:
            Tuple of (state, explanation)
        """
        award_amount = grant.get("award_amount")
        award_structure = grant.get("award_structure") or ""
        
        if not award_amount and not award_structure:
            return ('unknown', 'No award information found')
        
        amount_str = (award_amount or "").strip().lower()
        structure_str = award_structure.lower() if award_structure else ""
        
        # Check for "not disclosed" or vague language
        vague_terms = ['varies', 'contact us', 'not disclosed', 'n/a', 'tbd', 'upon request', 'negotiable']
        is_vague = any(term in amount_str for term in vague_terms)
        
        if is_vague:
            return ('unknown', 'Award amount not disclosed or vague')
        
        # Check for specific numeric amount
        if award_amount:
            # Look for numbers (could be single amount or range)
            numbers = re.findall(r'[\d,]+', award_amount.replace(',', ''))
            if numbers:
                # Check if it's a range
                if '-' in award_amount or 'to' in amount_str or 'range' in amount_str:
                    return ('partial', f"Award range: {award_amount}")
                else:
                    # Check if we have currency and terms
                    has_currency = any([
                        '$' in award_amount,
                        'usd' in amount_str,
                        'ghs' in amount_str,
                        'eur' in amount_str,
                        'gbp' in amount_str,
                        'cedi' in amount_str
                    ])
                    
                    if has_currency and award_structure:
                        return ('known', f"Award amount and structure: {award_amount}")
                    elif has_currency:
                        return ('partial', f"Award amount: {award_amount} (terms unclear)")
                    else:
                        return ('partial', f"Award amount mentioned: {award_amount}")
        
        # If only structure but no amount
        if award_structure and len(award_structure) > 20:
            return ('partial', 'Award structure described but amount unclear')
        
        return ('unknown', 'Award information insufficient')
    
    @staticmethod
    def compute_decision_readiness(
        timeline_clarity: BucketState,
        winner_signal: BucketState,
        mission_specificity: BucketState,
        application_burden: BucketState,
        award_structure_clarity: BucketState
    ) -> str:
        """
        Compute Decision Readiness label from bucket states.
        
        Ready for Evaluation: 🟢 or 🟡 in all 5 buckets, no 🔴 in Timeline or Award
        Partial — Missing Signals: 1–2 🔴 buckets, but Timeline OR Award is still known
        Low Confidence Grant: 🔴 Timeline OR 🔴 Award OR 3+ 🔴 buckets total
        """
        buckets = [timeline_clarity, winner_signal, mission_specificity, application_burden, award_structure_clarity]
        unknown_count = buckets.count('unknown')
        
        # Hard blockers: Timeline or Award Structure unknown
        if timeline_clarity == 'unknown' or award_structure_clarity == 'unknown':
            return 'Low Confidence Grant'
        
        # 3+ unknown buckets
        if unknown_count >= 3:
            return 'Low Confidence Grant'
        
        # 1-2 unknown buckets (but not Timeline or Award)
        if unknown_count >= 1:
            return 'Partial — Missing Signals'
        
        # All buckets are known or partial
        return 'Ready for Evaluation'
    
    @staticmethod
    def compute_status_of_knowledge(
        timeline_clarity: BucketState,
        winner_signal: BucketState,
        mission_specificity: BucketState,
        application_burden: BucketState,
        award_structure_clarity: BucketState
    ) -> str:
        """
        Compute Status of Knowledge label from bucket states.
        
        Well-Specified: All 5 buckets 🟢 or 🟡, no 🔴 in Timeline or Award
        Partially Opaque: 1–2 🔴 buckets, not Timeline or Award
        Structurally Vague: 🔴 Timeline OR 🔴 Award OR 3+ 🔴 total
        """
        buckets = [timeline_clarity, winner_signal, mission_specificity, application_burden, award_structure_clarity]
        unknown_count = buckets.count('unknown')
        
        # Hard blockers
        if timeline_clarity == 'unknown' or award_structure_clarity == 'unknown':
            return 'Structurally Vague'
        
        # 3+ unknown
        if unknown_count >= 3:
            return 'Structurally Vague'
        
        # 1-2 unknown (not Timeline or Award)
        if unknown_count >= 1:
            return 'Partially Opaque'
        
        # All known or partial
        return 'Well-Specified'
    
    @staticmethod
    def compute_all_buckets(grant: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute all 5 bucket states and derived fields for a grant.
        
        Returns:
            Dictionary with:
            - timeline_clarity: (state, explanation)
            - winner_signal: (state, explanation)
            - mission_specificity: (state, explanation)
            - application_burden: (state, explanation)
            - award_structure_clarity: (state, explanation)
            - decision_readiness: str
            - status_of_knowledge: str
        """
        timeline_state, timeline_explanation = DecisionReadinessService.compute_timeline_clarity(grant)
        winner_state, winner_explanation = DecisionReadinessService.compute_winner_signal(grant)
        mission_state, mission_explanation = DecisionReadinessService.compute_mission_specificity(grant)
        burden_state, burden_explanation = DecisionReadinessService.compute_application_burden(grant)
        award_state, award_explanation = DecisionReadinessService.compute_award_structure_clarity(grant)
        
        decision_readiness = DecisionReadinessService.compute_decision_readiness(
            timeline_state, winner_state, mission_state, burden_state, award_state
        )
        
        status_of_knowledge = DecisionReadinessService.compute_status_of_knowledge(
            timeline_state, winner_state, mission_state, burden_state, award_state
        )
        
        return {
            'timeline_clarity': timeline_state,
            'timeline_clarity_explanation': timeline_explanation,
            'winner_signal': winner_state,
            'winner_signal_explanation': winner_explanation,
            'mission_specificity': mission_state,
            'mission_specificity_explanation': mission_explanation,
            'application_burden': burden_state,
            'application_burden_explanation': burden_explanation,
            'award_structure_clarity': award_state,
            'award_structure_clarity_explanation': award_explanation,
            'decision_readiness': decision_readiness,
            'status_of_knowledge': status_of_knowledge,
        }
    
    @staticmethod
    def infer_scope(grant: Dict[str, Any]) -> Tuple[str, str]:
        """
        Infer grant scope (Local / National / International / Unclear).
        
        Priority order:
        1. Explicit geography in grant text (regex + keywords)
        2. Eligibility clauses ("open to applicants in...")
        3. Funder jurisdiction (if available)
        4. Manual override (not handled here - would be in admin)
        
        Returns:
            Tuple of (scope, explanation)
        """
        # Combine all text fields that might contain geographic info
        text_fields = [
            grant.get("description") or "",
            grant.get("mission") or "",
            grant.get("eligibility") or "",
            grant.get("preferred_applicants") or "",
        ]
        # Filter out empty strings and join
        combined_text = ' '.join(filter(None, text_fields)).lower()
        
        # Keywords for each scope level
        local_keywords = [
            'local', 'city', 'municipal', 'town', 'county', 'district',
            'community', 'neighborhood', 'regional (local)', 'within city',
            'city-wide', 'municipality'
        ]
        
        national_keywords = [
            'national', 'country', 'nation-wide', 'country-wide',
            'domestic', 'within [country]', 'all [country]', 'entire country'
        ]
        
        international_keywords = [
            'international', 'global', 'worldwide', 'cross-border',
            'multiple countries', 'developing countries', 'africa', 'asia',
            'europe', 'latin america', 'world', 'any country', 'globally'
        ]
        
        # Check for explicit scope mentions
        local_matches = sum(1 for keyword in local_keywords if keyword in combined_text)
        national_matches = sum(1 for keyword in national_keywords if keyword in combined_text)
        international_matches = sum(1 for keyword in international_keywords if keyword in combined_text)
        
        # Check eligibility clauses
        eligibility = (grant.get("eligibility") or "").lower()
        if eligibility:
            # Look for "open to applicants in..." patterns
            if re.search(r'open to.*in\s+([a-z\s]+)', eligibility):
                # Try to extract location
                location_match = re.search(r'in\s+([a-z\s]{3,30})', eligibility)
                if location_match:
                    location = location_match.group(1).strip()
                    # Check if it's a country name or region
                    if any(term in location for term in ['country', 'nation', 'state']):
                        return ('National', f"Eligibility: {location}")
                    elif any(term in location for term in ['city', 'town', 'local', 'region']):
                        return ('Local', f"Eligibility: {location}")
                    elif any(term in location for term in ['international', 'global', 'world', 'any']):
                        return ('International', f"Eligibility: {location}")
        
        # Determine scope based on keyword matches
        if international_matches > 0 and international_matches >= max(national_matches, local_matches):
            return ('International', 'International scope indicated in grant text')
        elif national_matches > 0 and national_matches >= local_matches:
            return ('National', 'National scope indicated in grant text')
        elif local_matches > 0:
            return ('Local', 'Local scope indicated in grant text')
        
        # If no clear indicators, return Unclear
        return ('Unclear', 'Geographic scope not clearly specified')
