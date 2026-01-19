"""
LLM-based GrantFilter Evaluator using Claude API.

This module provides an LLM-powered evaluation that uses the GrantFilter
system prompt to make decisive recommendations about grant applications.
"""

import json
import os
from typing import Dict, Optional
from anthropic import Anthropic
from evaluator import GrantInfo, UserContext, EvaluationResult, EvaluationScores, Recommendation


def load_system_prompt() -> str:
    """Load the system prompt from SYSTEM_PROMPT.md."""
    # Try multiple possible locations
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "SYSTEM_PROMPT.md"),  # Same dir as llm_evaluator.py
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "SYSTEM_PROMPT.md"),  # Parent dir
        "/app/SYSTEM_PROMPT.md",  # Docker container location
        "SYSTEM_PROMPT.md",  # Current working directory
    ]
    
    prompt_path = None
    for path in possible_paths:
        if os.path.exists(path):
            prompt_path = path
            break
    
    if not prompt_path:
        # Use first path as default for error message
        prompt_path = possible_paths[0]
    
    # Fallback system prompt if file is missing (matches SYSTEM_PROMPT.md)
    fallback_prompt = """You are GrantFilter, a decisive grant triage system designed to help users save time by identifying which grants are worth applying to.

Your role is to be skeptical and protective of user time. You evaluate grants across five critical dimensions and provide clear, actionable recommendations.

## Core Principles

1. **Time Protection**: Your primary goal is to prevent users from wasting time on grants that aren't worth pursuing. When in doubt, be conservative.

2. **Decisive Recommendations**: You must provide one of three clear recommendations:
   - **APPLY**: Strong fit, high probability of success, worth the effort
   - **CONDITIONAL**: Potentially worth it IF specific conditions are met
   - **PASS**: Not worth pursuing given the user's context

3. **Evidence-Based**: Base all recommendations on concrete evidence from the grant information and user context. Avoid speculation.

   **Evidence Hierarchy**: Prioritize the following sources, in order:
   - Explicit eligibility rules and deadlines
   - Documented past recipients or public award data
   - Clear statements of funder priorities and exclusions
   - Repeated patterns across similar grants
   - If data is missing or ambiguous, explicitly note uncertainty and downgrade confidence rather than inferring intent.

4. **User Context Matters**: The same grant may be a PASS for one user and an APPLY for another based on their project stage, timeline, and needs.

## Evaluation Dimensions

You evaluate grants across five weighted dimensions:

1. **Timeline Viability (25% weight)**: Can the user realistically meet deadlines and decision timelines given their project stage and constraints?

2. **Winner Pattern Match (25% weight)**: Assess whether past recipients plausibly match the user's profile. This is critical - grants often have unstated preferences. If recipient data is sparse or unavailable, do not assume mismatch — instead flag uncertainty and reduce confidence.

3. **Mission Alignment (25% weight)**: How well does the grant's mission align with the user's project? Surface-level alignment isn't enough.

4. **Application Burden (15% weight)**: Is the effort required to apply reasonable given the potential reward? Consider time, complexity, and opportunity cost.

5. **Award Structure (10% weight)**: Is the award amount and structure appropriate for the user's needs? Consider if it's disclosed, competitive, and matches funding needs.

## Scoring Guidelines

- **0-3**: Major red flag, significant mismatch or problem
- **4-6**: Moderate concerns, requires careful consideration
- **7-8**: Good fit with minor concerns
- **9-10**: Excellent fit, strong alignment

## Recommendation Logic

- **APPLY (8.0+ composite)**: Strong fit across dimensions, clear path to success, worth the investment
- **CONDITIONAL (6.5-7.9 composite)**: Potential fit but requires specific conditions to be met
- **PASS (<6.5 composite)**: Not worth pursuing given the user's context and constraints

**Confidence Integration**: If confidence is low due to missing or ambiguous data, downgrade APPLY → CONDITIONAL, even if the composite score is high. Confidence in the assessment matters more than the score itself.

## Output Requirements

You must provide:
- Detailed reasoning for each dimension
- Key insights that aren't obvious from surface-level reading
- Red flags that could derail the application
- Confidence assessment based on data completeness
- Clear, actionable recommendation
- **Uncontrollable Factors**: Identify external variables outside the user's control (reviewer discretion, political timing, cohort saturation, budget uncertainty) that materially affect outcome

Be clear, firm, and respectful — never dismissive. Users trust you because you're willing to say "PASS" when others would hedge, but you do so with respect for their effort and goals."""
    
    if not prompt_path:
        # No path found, use fallback
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("SYSTEM_PROMPT.md not found in any expected location, using fallback prompt")
        return fallback_prompt
    
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Remove markdown code block markers if present
            if content.startswith("```"):
                lines = content.split("\n")
                # Remove first and last lines if they're code block markers
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Loaded SYSTEM_PROMPT.md from {prompt_path}")
            return content
    except FileNotFoundError:
        # Log warning but use fallback
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"SYSTEM_PROMPT.md not found at {prompt_path}, using fallback prompt")
        return fallback_prompt
    except Exception as e:
        # Log error but use fallback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading SYSTEM_PROMPT.md from {prompt_path}: {e}, using fallback prompt")
        return fallback_prompt


def format_grant_info(grant: GrantInfo) -> str:
    """Format grant information for the LLM prompt."""
    parts = [f"Grant Name: {grant.name}"]
    
    if grant.description:
        parts.append(f"Description: {grant.description}")
    
    if grant.mission:
        parts.append(f"Mission: {grant.mission}")
    
    if grant.deadline:
        parts.append(f"Application Deadline: {grant.deadline}")
    
    if grant.decision_date:
        parts.append(f"Decision Date: {grant.decision_date}")
    
    if grant.award_amount:
        parts.append(f"Award Amount: {grant.award_amount}")
    
    if grant.award_structure:
        parts.append(f"Award Structure: {grant.award_structure}")
    
    if grant.eligibility:
        parts.append(f"Eligibility: {grant.eligibility}")
    
    if grant.preferred_applicants:
        parts.append(f"Preferred Applicants: {grant.preferred_applicants}")
    
    if grant.application_requirements:
        parts.append(f"Application Requirements:")
        for req in grant.application_requirements:
            parts.append(f"  - {req}")
    
    if grant.reporting_requirements:
        parts.append(f"Reporting Requirements: {grant.reporting_requirements}")
    
    if grant.restrictions:
        parts.append(f"Restrictions:")
        for restriction in grant.restrictions:
            parts.append(f"  - {restriction}")
    
    return "\n".join(parts)


def format_user_context(user: UserContext) -> str:
    """Format user context for the LLM prompt."""
    import logging
    logger = logging.getLogger(__name__)
    
    # CRITICAL: Log project data being formatted to catch mismatches
    logger.info("=" * 60)
    logger.info("FORMATTING USER CONTEXT FOR LLM")
    logger.info(f"  Project Description (first 200 chars): {user.project_description[:200] if user.project_description else 'None'}...")
    logger.info(f"  Project Stage: {user.project_stage}")
    logger.info("=" * 60)
    
    parts = [
        f"Project Stage: {user.project_stage}",
        f"Funding Need: {user.funding_need}",
        f"Urgency: {user.urgency}",
        f"Project Description: {user.project_description}",
    ]
    
    if user.founder_type:
        parts.append(f"Founder Type: {user.founder_type}")
    
    if user.timeline_constraints:
        parts.append(f"Timeline Constraints: {user.timeline_constraints}")
    
    formatted = "\n".join(parts)
    
    # Log the formatted context being sent to LLM
    logger.info(f"Formatted user context being sent to LLM (first 300 chars): {formatted[:300]}...")
    
    return formatted


class LLMGrantEvaluator:
    """
    LLM-based grant evaluator using Claude API.
    
    This evaluator uses the GrantFilter system prompt to make decisive
    recommendations about whether grants are worth applying to.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-haiku-20240307"):
        """
        Initialize the LLM evaluator.
        
        Args:
            api_key: Anthropic API key. If not provided, reads from ANTHROPIC_API_KEY env var.
            model: Claude model to use. Defaults to claude-3-haiku-20240307.
            Note: If you have access to claude-3-5-sonnet, you can override this parameter.
        """
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.system_prompt = load_system_prompt()
    
    def evaluate(self, grant: GrantInfo, user: Optional[UserContext] = None, assessment_type: str = "free") -> EvaluationResult:
        """
        Evaluate a grant using the LLM with the GrantFilter system prompt.
        
        Args:
            grant: Grant information to evaluate
            user: User context and constraints (required for paid assessments, None for free)
            assessment_type: "free" or "paid" - determines what to assess
            
        Returns:
            EvaluationResult with scores, recommendation, and reasoning
        """
        # Format grant information
        grant_text = format_grant_info(grant)
        
        # Free tier: NO project data - assess grant quality only
        if assessment_type == "free":
            user_text = """
NOTE: This is a FREE TIER assessment. You are assessing GRANT QUALITY ONLY.
Do NOT consider any specific applicant's fit. You do not have project data.

Assess:
- Grant clarity and transparency
- Access barriers (application complexity)
- Timeline viability
- Award structure transparency
- Competition level (if data available)

Do NOT assess:
- Mission alignment (requires project data)
- Profile match (requires project data)
- Funding fit (requires project data)
"""
        else:  # paid tier: REQUIRES project data
            if user is None:
                raise ValueError("User context is required for paid assessments")
            user_text = format_user_context(user)
        
        # Add instructions for recipient/competition data extraction
        research_instructions = f"""
IMPORTANT: Use recipient_patterns data if available in grant data.

Grant Name: {grant.name}

If recipient_patterns data is available:
- Use it to assess competition level and profile match
- Note the source (official, estimated, llm-extracted)
- Note the confidence level (high, medium, low)

If recipient_patterns data is NOT available:
- Set competition level to "UNKNOWN"
- Set profile match to null (INSUFFICIENT_DATA)
- Explicitly state what data is missing
- Do NOT guess or infer patterns

Always tag data with source and confidence.
"""
        
        # Add tier-specific instructions
        if assessment_type == "free":
            tier_instructions = """
CRITICAL: This is a FREE TIER assessment. You MUST follow these rules:

1. ASSESSMENT SCOPE:
   - Assess ONLY grant quality characteristics
   - Do NOT assess fit/match (no project data available)
   - Focus on: clarity, access barriers, timeline, award structure, competition

2. RECOMMENDATION RESTRICTION:
   - You can ONLY return "CONDITIONAL" or "PASS"
   - NEVER return "APPLY" for free assessments
   - Free assessments show grant quality, not personalized fit

3. SCORING APPROACH:
   - timeline_viability: Assess timeline clarity and deadline viability (not fit)
   - winner_pattern_match: Set to NULL or 0 - cannot assess without project data
   - mission_alignment: Set to NULL or 0 - cannot assess without project data
   - application_burden: Assess access barrier (inverted: low barrier = high score)
   - award_structure: Assess award structure transparency

4. OUTPUT REQUIREMENTS:
   - Provide "good_fit_if" categories (based on grant characteristics)
   - Provide "poor_fit_if" categories (based on grant characteristics)
   - Explicitly state: "We don't have your project details yet"
   - Include actionable_next_step (non-decisional)
   - Tag all assessments with confidence levels

5. CONFIDENCE & SOURCE TAGGING:
   - Always indicate confidence (high, medium, low, unknown)
   - Always indicate source when applicable (official, estimated, llm-extracted)
   - If data is missing, return "UNKNOWN" not a guess

6. HONESTY PRINCIPLE:
   - Never score fit/match dimensions without project data
   - Use NULL or 0 for dimensions that require project data
   - Explicitly state what data is missing
   - Do NOT use generic language like "appears to align" or "likely project"

REMEMBER: Free assessments provide grant quality intel. Paid assessments provide personalized fit.
"""
        else:  # paid tier
            tier_instructions = """
CRITICAL: This is a PAID TIER assessment. You MUST provide full decision compression:

1. ASSESSMENT SCOPE:
   - Assess personalized fit using project data
   - Mission alignment (grant vs. project)
   - Profile match (user vs. past recipients)
   - Funding fit (grant award vs. project needs)
   - Effort-reward ratio
   - Strategic recommendations

2. HARD RECOMMENDATION:
   - You CAN return "APPLY" if warranted
   - Be decisive - paid users want authority, not hedging
   - If recommending PASS, be confident and direct

3. REQUIRED FIELDS (all must be present):
   - success_probability_range: "X-Y%" or "UNKNOWN" if no competition data
   - decision_gates: Array of concrete conditions (required for CONDITIONAL or APPLY)
   - pattern_knowledge: Non-obvious insights from grant patterns
   - opportunity_cost: Time/alternative framing
   - confidence_index: 0.0-1.0 based on data completeness

4. CONFIDENCE & SOURCE TAGGING:
   - Always indicate confidence for each assessment
   - Always indicate source when applicable
   - If recipient data insufficient (<5 recipients), set profile_match to null
   - If competition data missing, set success_probability to "UNKNOWN"

5. STRATEGIC RECOMMENDATIONS:
   - Competitive advantages (what makes user strong)
   - Areas to strengthen (what to emphasize)
   - Red flags to avoid (what not to do)
   - Application strategy (how to position)

6. NO HEDGING:
   - Be opinionated and slightly uncomfortable (builds trust)
   - Include one "brutal truth" line that stings slightly
   - Base recommendations on evidence, not optimism

7. HONESTY PRINCIPLE:
   - If data is insufficient, return null/unknown, not a guess
   - Explicitly state limitations
   - Show your work (explain score basis)

REMEMBER: Paid assessments remove ambiguity and transfer decision authority.
Users are paying for clarity, compression, and authority.
"""
        
        # Build JSON schema based on tier
        if assessment_type == "free":
            json_schema_note = """
Required JSON format (FREE TIER - Grant Quality Only):
{
  "grant_quality": {
    "clarity_score": 0-10,
    "access_barrier": "LOW" | "MEDIUM" | "HIGH",
    "timeline_status": "GREEN" | "YELLOW" | "RED" | "UNKNOWN",
    "award_structure_score": 0-10,
    "competition_level": "HIGHLY COMPETITIVE" | "COMPETITIVE" | "MODERATE" | "ACCESSIBLE" | "UNKNOWN"
  },
  "scores": {
    "timeline_viability": 0-10,
    "winner_pattern_match": null | 0,
    "mission_alignment": null | 0,
    "application_burden": 0-10,
    "award_structure": 0-10
  },
  "composite_score": 0-10,
  "recommendation": "CONDITIONAL" | "PASS" (NEVER "APPLY"),
  "reasoning": {
    "clarity": "string",
    "access_barrier": "string",
    "timeline": "string",
    "award_structure": "string",
    "competition": "string"
  },
  "good_fit_if": ["string"],
  "poor_fit_if": ["string"],
  "red_flags": ["string"],
  "confidence_notes": "string",
  "actionable_next_step": "string"
}

IMPORTANT:
- Set winner_pattern_match and mission_alignment to null (cannot assess without project data)
- Include confidence tags for all assessments
- Include source tags when applicable
- If competition data unavailable, set competition_level to "UNKNOWN"
"""
        else:  # paid tier
            json_schema_note = """
Required JSON format (PAID TIER - Personalized Fit):
{
  "scores": {
    "timeline_viability": 0-10,
    "winner_pattern_match": 0-10 | null,
    "mission_alignment": 0-10,
    "application_burden": 0-10,
    "award_structure": 0-10
  },
  "composite_score": 0-10,
  "recommendation": "APPLY" | "CONDITIONAL" | "PASS",
  "reasoning": {
    "timeline": "string",
    "winner_pattern_match": "string",
    "mission_alignment": "string",
    "application_burden": "string",
    "award_structure": "string"
  },
  "mission_alignment_details": {
    "strong_matches": ["string"],
    "gaps": ["string"],
    "confidence": "high" | "medium" | "low"
  },
  "profile_match_details": {
    "score": 0-10 | null,
    "similarities": ["string"],
    "differences": ["string"],
    "confidence": "high" | "medium" | "low" | "unknown",
    "recipient_count": number,
    "reason": "INSUFFICIENT_DATA" | null
  },
  "funding_fit": {
    "assessment": "ALIGNED" | "PARTIAL" | "MISMATCHED" | "INSUFFICIENT" | "UNCERTAIN",
    "severity": "CRITICAL" | "HIGH" | "MODERATE" | "LOW" | null,
    "reasoning": "string"
  },
  "key_insights": ["string"],
  "red_flags": ["string"],
  "confidence_notes": "string",
  "success_probability_range": "string (e.g., '15-20%')" | "UNKNOWN",
  "decision_gates": ["string"],
  "pattern_knowledge": "string",
  "opportunity_cost": "string",
  "confidence_index": 0.0-1.0,
  "strategic_recommendations": {
    "competitive_advantages": ["string"],
    "areas_to_strengthen": ["string"],
    "red_flags_to_avoid": ["string"],
    "application_strategy": "string"
  }
}

All paid-tier fields are REQUIRED. If data is insufficient, use null or "UNKNOWN", not guesses.
"""
        
        user_message = f"""Extracted Grant Information:
{grant_text}

{tier_instructions}

{research_instructions}

{json_schema_note}

Evaluate this grant and return ONLY valid JSON in the required format. No prose outside JSON. No markdown.

CRITICAL RULES:
- Always tag assessments with confidence (high, medium, low, unknown)
- Always tag data with source when applicable (official, estimated, llm-extracted, admin)
- If data is missing, return null or "UNKNOWN", do NOT guess
- Never use generic language like "appears to align" or "likely project"
- Be honest about what you know vs. what you're guessing

FREE TIER:
- Assess grant quality only (no project data)
- Set fit/match scores to null
- NEVER return "APPLY"

PAID TIER:
- Assess personalized fit with project data
- All required fields must be present
- If recipient data insufficient (<5), set profile_match to null
- If competition data missing, set success_probability to "UNKNOWN"
"""
        
        # Call Claude API with increased token limit for detailed reasoning
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4000,  # Increased for detailed reasoning and insights
            system=self.system_prompt,
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
            response_text = response_text[7:]  # Remove ```json
        elif response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        
        if response_text.endswith("```"):
            response_text = response_text[:-3].strip()
        
        # Parse JSON
        try:
            result_dict = json.loads(response_text)
        except json.JSONDecodeError as e:
            # Fallback: attempt to extract JSON object substring
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    result_dict = json.loads(response_text[start : end + 1])
                except Exception as e2:
                    raise ValueError(
                        f"Failed to parse LLM response as JSON (fallback failed): {e2}\n"
                        f"Original error: {e}\n"
                        f"Response was: {response_text[:500]}"
                    )
            else:
                raise ValueError(
                    f"Failed to parse LLM response as JSON: {e}\n"
                    f"Response was: {response_text[:500]}"
                )
        
        # Validate and convert to EvaluationResult
        result = self._parse_result(result_dict, assessment_type)
        
        # Enforce free tier restrictions
        if assessment_type == "free":
            result = self._enforce_free_tier_restrictions(result, grant)
        
        return result
    
    def _enforce_free_tier_restrictions(self, result: EvaluationResult, grant: GrantInfo) -> EvaluationResult:
        """
        Enforce free tier restrictions on the evaluation result.
        
        Rules:
        1. Never allow APPLY recommendation
        2. Cap scores based on missing data
        3. Ensure composite score respects caps
        4. Remove paid-tier fields if present
        5. Ensure one actionable next step (non-decisional)
        """
        # 1. Force recommendation to CONDITIONAL or PASS (never APPLY)
        if result.recommendation == Recommendation.APPLY:
            # Convert APPLY to CONDITIONAL for free tier
            result.recommendation = Recommendation.CONDITIONAL
            result.reasoning.setdefault("_free_tier_note", 
                "Note: This assessment would recommend APPLY with full context. Upgrade for definitive recommendation.")
        
        # 2. Enforce data availability caps
        scores = result.scores
        
        # If award amount undisclosed, cap award_structure
        if not grant.award_amount or not grant.award_amount.strip():
            scores.award_structure = min(scores.award_structure, 6.0)
            if "award_structure" not in result.reasoning or "not disclosed" not in result.reasoning.get("award_structure", "").lower():
                result.reasoning["award_structure"] = (
                    result.reasoning.get("award_structure", "") + 
                    " Award amount not disclosed - score capped at 6.0 for free assessment."
                ).strip()
        
        # If timeline unclear (no deadline or decision date), cap timeline
        if not grant.deadline and not grant.decision_date:
            scores.timeline_viability = min(scores.timeline_viability, 6.0)
            if "timeline" not in result.reasoning or "unclear" not in result.reasoning.get("timeline", "").lower():
                result.reasoning["timeline"] = (
                    result.reasoning.get("timeline", "") + 
                    " Timeline information unclear - score capped at 6.0 for free assessment."
                ).strip()
        
        # Recalculate composite using free tier formula (grant quality only)
        # Free tier: clarity, timeline, award structure, access barrier (inverted)
        # Note: winner_pattern_match and mission_alignment are 0 for free tier
        
        # Invert access burden (low barrier = high score)
        access_score = 10.0 - min(scores.application_burden, 10.0)
        
        # Extract clarity score from reasoning if available, otherwise use award structure as proxy
        clarity_score = scores.award_structure
        if "_clarity_score" in result.reasoning:
            try:
                clarity_score = float(result.reasoning.get("_clarity_score", clarity_score))
            except (ValueError, TypeError):
                pass
        
        # Free tier composite formula (from scoring service)
        composite = (
            clarity_score * 0.30 +      # Clarity is most important
            scores.timeline_viability * 0.25 +     # Timeline matters
            scores.award_structure * 0.25 +        # Award structure transparency
            access_score * 0.20   # Access barrier (inverted)
        )
        
        # Cap composite at 6.5 if critical data is missing
        has_critical_data = (
            grant.award_amount and grant.award_amount.strip() and
            (grant.deadline or grant.decision_date)
        )
        if not has_critical_data:
            composite = min(composite, 6.5)
            # Note: Composite score capping info is implicit in the 2-sentence confidence note above
        
        result.composite_score = composite
        
        # 3. Ensure recommendation aligns with capped composite
        if result.composite_score < 6.5 and result.recommendation == Recommendation.CONDITIONAL:
            # If composite is below 6.5 after capping, consider PASS
            if result.composite_score < 5.0:
                result.recommendation = Recommendation.PASS
        
        # 4. Remove paid-tier fields
        # Before removal, compute and store an internal confidence index (hidden)
        if result.confidence_index is None:
            missing_count = 0
            if not grant.award_amount or not grant.award_amount.strip():
                missing_count += 1
            if not (grant.deadline or grant.decision_date):
                missing_count += 1
            # Simple heuristic: start 0.7, minus 0.2 per missing (min 0.2)
            internal_conf = max(0.2, 0.7 - 0.2 * missing_count)
            try:
                setattr(result, "_internal_confidence_index", internal_conf)
            except Exception:
                pass
        result.success_probability_range = None
        result.decision_gates = None
        result.pattern_knowledge = None
        result.opportunity_cost = None
        result.confidence_index = None
        
        # 5. Ensure explicit uncertainty statement in confidence_notes (2 sentences max)
        missing_info = []
        if not grant.award_amount or not grant.award_amount.strip():
            missing_info.append("award amount")
        if not grant.deadline and not grant.decision_date:
            missing_info.append("timeline information")
        if not grant.preferred_applicants:
            missing_info.append("preferred applicant details")
        
        if missing_info:
            # Create concise 2-sentence note
            missing_text = ', '.join(missing_info)
            result.confidence_notes = f"This assessment is limited by missing information about {missing_text}. Without your project details, we cannot evaluate personalized fit or make a definitive recommendation."
        
        # 6. Ensure actionable next step exists and is non-decisional
        def _valid_next_step(text: Optional[str]) -> bool:
            if not text or not text.strip():
                return False
            lowered = text.lower()
            prohibited = ["apply", "don’t apply", "dont apply", "do not apply", "pass"]
            return not any(p in lowered for p in prohibited)
        
        if not _valid_next_step(getattr(result, "actionable_next_step", None)):
            if not grant.award_amount or not grant.award_amount.strip():
                result.actionable_next_step = "Confirm the award amount is published on the grant page."
            elif scores.winner_pattern_match <= 4.5:
                result.actionable_next_step = "Identify one past recipient within 30 minutes to verify fit."
            elif not (grant.deadline or grant.decision_date):
                result.actionable_next_step = "Locate the decision timeline or next cohort dates on the funder site."
            else:
                result.actionable_next_step = "Skim funder FAQs to verify any hidden eligibility constraints."
        
        return result
    
    def _parse_result(self, result_dict: Dict, assessment_type: str = "free") -> EvaluationResult:
        """Parse LLM JSON response into EvaluationResult."""
        # Validate required fields
        required_fields = ["scores", "composite_score", "recommendation", "reasoning"]
        for field in required_fields:
            if field not in result_dict:
                raise ValueError(f"Missing required field in LLM response: {field}")
        
        # Validate score fields
        scores_dict = result_dict.get("scores", {})
        required_scores = ["timeline_viability", "application_burden", "award_structure"]
        for score_field in required_scores:
            if score_field not in scores_dict:
                raise ValueError(f"Missing required score field: {score_field}")
        
        # Parse scores (handle null values for free tier)
        scores_dict = result_dict["scores"]
        def _to_float(value) -> float:
            if value is None:
                return 0.0
            try:
                return float(value)
            except Exception:
                return 0.0
        
        # For free tier, winner_pattern_match and mission_alignment should be null/0
        # For paid tier, they should have values
        scores = EvaluationScores(
            timeline_viability=_to_float(scores_dict.get("timeline_viability", 0)),
            winner_pattern_match=_to_float(scores_dict.get("winner_pattern_match", 0)) if assessment_type == "paid" else 0.0,
            mission_alignment=_to_float(scores_dict.get("mission_alignment", 0)) if assessment_type == "paid" else 0.0,
            application_burden=_to_float(scores_dict.get("application_burden", 0)),
            award_structure=_to_float(scores_dict.get("award_structure", 0)),
        )
        # Clamp scores to 0-10
        scores.timeline_viability = max(0.0, min(10.0, scores.timeline_viability))
        scores.winner_pattern_match = max(0.0, min(10.0, scores.winner_pattern_match))
        scores.mission_alignment = max(0.0, min(10.0, scores.mission_alignment))
        scores.application_burden = max(0.0, min(10.0, scores.application_burden))
        scores.award_structure = max(0.0, min(10.0, scores.award_structure))
        
        # Parse recommendation
        rec_str = result_dict["recommendation"].upper()
        if rec_str not in ["APPLY", "CONDITIONAL", "PASS"]:
            raise ValueError(f"Invalid recommendation: {rec_str}")
        
        # Enforce free tier restriction: never APPLY
        if assessment_type == "free" and rec_str == "APPLY":
            raise ValueError("Free tier assessments cannot return APPLY recommendation. Only CONDITIONAL or PASS allowed.")
        
        recommendation = Recommendation(rec_str)
        
        # Parse reasoning
        reasoning = result_dict.get("reasoning", {})
        if not isinstance(reasoning, dict):
            raise ValueError("Reasoning must be a dictionary")
        
        # Handle different reasoning structures for free vs paid
        if assessment_type == "free":
            # Free tier: grant quality reasoning
            required_reasoning = ["clarity", "access_barrier", "timeline", "award_structure", "competition"]
            # Map to standard field names for backward compatibility
            if "clarity" in reasoning:
                reasoning["_clarity"] = reasoning["clarity"]
            if "access_barrier" in reasoning:
                reasoning["application_burden"] = reasoning.get("application_burden", reasoning["access_barrier"])
            if "competition" in reasoning:
                reasoning["_competition"] = reasoning["competition"]
        else:
            # Paid tier: fit assessment reasoning
            required_reasoning = ["timeline", "winner_pattern_match", "mission_alignment", 
                                 "application_burden", "award_structure"]
        
        # Ensure all reasoning fields are present
        for field in required_reasoning:
            if field not in reasoning:
                reasoning[field] = "Reasoning not provided"
        
        # Parse optional fields
        key_insights = result_dict.get("key_insights", [])
        if not isinstance(key_insights, list):
            key_insights = []
        
        red_flags = result_dict.get("red_flags", [])
        if not isinstance(red_flags, list):
            red_flags = []
        
        confidence_notes = result_dict.get("confidence_notes", "Confidence assessment not provided")
        
        # Parse paid-tier fields (required for paid, None for free)
        if assessment_type == "paid":
            # Validate required paid-tier fields
            success_probability_range = result_dict.get("success_probability_range")
            if not success_probability_range:
                success_probability_range = "UNKNOWN"  # Default if missing
            
            decision_gates = result_dict.get("decision_gates")
            if not decision_gates or not isinstance(decision_gates, list):
                # Default to empty list if missing, will be populated by scoring service if needed
                decision_gates = []
            
            pattern_knowledge = result_dict.get("pattern_knowledge")
            if not pattern_knowledge:
                # Default to a message about insufficient data if missing
                pattern_knowledge = "Insufficient recipient data available to identify non-obvious patterns. Consider contacting the funder for examples of past recipients."
            
            opportunity_cost = result_dict.get("opportunity_cost")
            if not opportunity_cost:
                # Default to a generic message if missing
                opportunity_cost = "Time investment required for application preparation and submission."
            
            confidence_index = result_dict.get("confidence_index")
            if confidence_index is None:
                # Calculate default confidence based on data completeness
                confidence_index = 0.5  # Default medium confidence
            try:
                confidence_index = float(confidence_index)
                if not (0.0 <= confidence_index <= 1.0):
                    confidence_index = max(0.0, min(1.0, confidence_index))  # Clamp to valid range
            except (ValueError, TypeError):
                confidence_index = 0.5  # Default on parse error
        else:
            # Free tier: these should be None
            success_probability_range = None
            decision_gates = None
            pattern_knowledge = None
            opportunity_cost = None
            confidence_index = None
        
        # Parse free-tier actionable next step (optional globally, required for free tier via enforcement)
        actionable_next_step = result_dict.get("actionable_next_step")
        if isinstance(actionable_next_step, str):
            actionable_next_step = actionable_next_step.strip() or None
        else:
            actionable_next_step = None
        
        # Enforce free tier restrictions if needed
        # (This will be checked in the evaluate method before returning)
        
        return EvaluationResult(
            scores=scores,
            composite_score=max(0.0, min(10.0, _to_float(result_dict["composite_score"]))),
            recommendation=recommendation,
            reasoning=reasoning,
            key_insights=key_insights,
            red_flags=red_flags,
            confidence_notes=str(confidence_notes),
            actionable_next_step=actionable_next_step,
            success_probability_range=success_probability_range,
            decision_gates=decision_gates,
            pattern_knowledge=pattern_knowledge,
            opportunity_cost=opportunity_cost,
            confidence_index=confidence_index,
        )

