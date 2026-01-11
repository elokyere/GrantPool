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
    prompt_path = os.path.join(os.path.dirname(__file__), "SYSTEM_PROMPT.md")
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
        return content


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
    
    return "\n".join(parts)


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
    
    def evaluate(self, grant: GrantInfo, user: UserContext, evaluation_tier: str = "standard") -> EvaluationResult:
        """
        Evaluate a grant using the LLM with the GrantFilter system prompt.
        
        Args:
            grant: Grant information to evaluate
            user: User context and constraints
            evaluation_tier: "free", "refined", or "standard" - affects evaluation depth
            
        Returns:
            EvaluationResult with scores, recommendation, and reasoning
        """
        # Format inputs for the LLM
        grant_text = format_grant_info(grant)
        
        # For free tier, use conservative defaults (minimal context)
        if evaluation_tier == "free":
            # Use minimal/placeholder context for free tier
            user_text = """Project Stage: Not specified
Funding Need: Not specified
Urgency: Not specified
Project Description: Not specified
Note: This is a free assessment with conservative defaults. Provide a refined assessment with full project context for more accurate evaluation."""
        else:
            # Use full context for refined/standard tiers
            user_text = format_user_context(user)
        
        # Add instructions for past winner research
        research_instructions = f"""
IMPORTANT: Attempt to verify past winners for this grant to inform "winner_pattern_match".

Grant Name: {grant.name}

Suggested verification queries (attempt, but do not assume browsing is available):
- "{grant.name} recipients 2023"
- "{grant.name} awardees 2024"
- "{grant.name} past winners"

If you cannot verify past winner information:
1. Score winner_pattern_match at 4-5 (uncertainty penalty)
2. Explicitly state in reasoning that past winners could not be confirmed
3. Note in confidence_notes that winner pattern verification is missing
4. Do NOT guess winner patterns

Acknowledge inability to verify if data is unavailable.
"""
        
        # Add tier-specific instructions
        tier_instructions = ""
        if evaluation_tier == "free":
            tier_instructions = """
CRITICAL: This is a FREE TIER assessment. You MUST follow these restrictions:

1. RECOMMENDATION RESTRICTION:
   - You can ONLY return "CONDITIONAL" or "PASS"
   - NEVER return "APPLY" for free assessments
   - Free assessments create tension, not resolution

2. SCORE LIMITATIONS:
   - If award amount is undisclosed → award_structure max = 6.0
   - If no past winners found → winner_pattern_match max = 4.0 (you already do this)
   - If timeline unclear → timeline_viability max = 6.0
   - Missing critical data caps composite score (cannot exceed 6.5)

3. REASONING RESTRICTIONS:
   - Provide surface-level explanations only
   - NO decision gates or concrete conditions
   - NO success probability estimates
   - NO pattern knowledge/heuristics
   - NO opportunity cost framing
   - NO brutal truths (be diplomatic about limitations)

4. EXPLICIT UNCERTAINTY:
   - MUST include: "This assessment is limited by missing information about [specific missing data]"
   - This creates intentional friction that makes paid upgrade logical

5. CONFIDENCE NOTES:
   - State that this is an incomplete assessment
   - Note that full project context is needed for accurate evaluation
   - Do NOT include confidence_index (0-1 score) - that's paid-only

6. ACTIONABLE NEXT STEP (REQUIRED):
   - Provide exactly one concrete next step that increases certainty (non-decisional)
   - Examples: "Confirm award amount is published on the grant page", "Identify one past recipient within 30 minutes"
   - Do NOT use "apply", "don’t apply", or equivalents as the next step

REMEMBER: Free assessments should create tension. Paid assessments resolve it.
If free resolves the decision, no one pays. If free is useless, no one trusts you.
"""
        elif evaluation_tier == "refined":
            tier_instructions = """
IMPORTANT: This is a REFINED assessment with full project context.
- User has provided complete project details
- Use full context for accurate scoring
- This is an upgrade from a free tier assessment
"""
        else:  # standard (paid)
            tier_instructions = """
CRITICAL: This is a PAID TIER assessment. You MUST provide full decision compression:

1. HARD RECOMMENDATION:
   - You CAN return "APPLY" if warranted
   - Be decisive - paid users want authority, not hedging
   - If recommending PASS, be confident and direct

2. SUCCESS PROBABILITY:
   - Provide success_probability_range field (e.g., "5-12%", "25-35%")
   - Even rough ranges are powerful for decision-making
   - Base on: composite score, competition level, data availability

3. DECISION GATES (required for CONDITIONAL or APPLY):
   - Provide decision_gates array with concrete conditions
   - Example: ["Can identify ≥1 prior recipient within 30 minutes", "Not relying on this funding within 90 days"]
   - Turn analysis into action logic

4. PATTERN KNOWLEDGE:
   - Provide pattern_knowledge field with non-obvious insights
   - Example: "Funds branded as 'innovation' without published award sizes are often discretionary pools used opportunistically"
   - This is insight, not data - what free tools never give

5. OPPORTUNITY COST:
   - Provide opportunity_cost field
   - Tie decision to time and alternatives
   - Example: "The 5-10 hours required here would yield higher ROI if applied to 3 smaller, faster grants"

6. CONFIDENCE INDEX:
   - Provide confidence_index (0.0-1.0) based on data completeness
   - Higher = more confident in assessment
   - Explain primary uncertainty sources in confidence_notes

7. NO HEDGING:
   - Be opinionated and slightly uncomfortable (builds trust)
   - Include one "brutal truth" line that stings slightly
   - Example: "This grant is more likely to reward organizations already known to the funder than first-time applicants"

REMEMBER: Paid assessments remove ambiguity and transfer decision authority.
Users are paying for clarity, compression, and authority.
"""
        
        # Build JSON schema based on tier
        if evaluation_tier == "free":
            json_schema_note = """
Required JSON format (FREE TIER):
{
  "scores": {
    "timeline_viability": 0-10,
    "winner_pattern_match": 0-10,
    "mission_alignment": 0-10,
    "application_burden": 0-10,
    "award_structure": 0-10
  },
  "composite_score": 0-10,
  "recommendation": "CONDITIONAL" | "PASS" (NEVER "APPLY"),
  "reasoning": {
    "timeline": "string",
    "winner_pattern_match": "string",
    "mission_alignment": "string",
    "application_burden": "string",
    "award_structure": "string"
  },
  "key_insights": ["string"],
  "red_flags": ["string"],
  "confidence_notes": "string",
  "actionable_next_step": "string (one concrete, non-decisional next step)"
}

DO NOT include: success_probability_range, decision_gates, pattern_knowledge, opportunity_cost, confidence_index
"""
        else:  # paid tier
            json_schema_note = """
Required JSON format (PAID TIER):
{
  "scores": {
    "timeline_viability": 0-10,
    "winner_pattern_match": 0-10,
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
  "key_insights": ["string"],
  "red_flags": ["string"],
  "confidence_notes": "string",
  "success_probability_range": "string (e.g., '5-12%')",
  "decision_gates": ["string"],
  "pattern_knowledge": "string",
  "opportunity_cost": "string",
  "confidence_index": 0.0-1.0
}

All paid-tier fields are REQUIRED.
"""
        
        user_message = f"""Extracted Grant Information:
{grant_text}

User Project Context:
{user_text}

{tier_instructions}

{research_instructions}

{json_schema_note}

Evaluate this grant and return ONLY valid JSON in the required format. No prose outside JSON. No markdown.

Remember: Use the weighted formula for composite score:
Composite = (Timeline × 0.25) + (Winner Match × 0.25) + (Alignment × 0.25) + (Burden × 0.15) + (Award × 0.10)

FREE TIER recommendation rules:
- NEVER return "APPLY" (only CONDITIONAL or PASS)
- Missing data caps scores (see tier instructions above)

PAID TIER recommendation thresholds:
- 8.0+: APPLY (with decision gates)
- 6.5-7.9: CONDITIONAL (with decision gates)
- 5.0-6.4: PASS
- <5.0: PASS (hard)

Data availability enforcement:
- If award amount undisclosed → award_structure max = 6.0, composite cannot exceed 6.5
- If no past winners found → winner_pattern_match max = 4.0
- If timeline unclear → timeline_viability max = 6.0"""
        
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
        result = self._parse_result(result_dict)
        
        # Enforce free tier restrictions
        if evaluation_tier == "free":
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
        
        # Recalculate composite with capped scores
        composite = (
            scores.timeline_viability * 0.25 +
            scores.winner_pattern_match * 0.25 +
            scores.mission_alignment * 0.25 +
            scores.application_burden * 0.15 +
            scores.award_structure * 0.10
        )
        
        # Cap composite at 6.5 if critical data is missing
        has_critical_data = (
            grant.award_amount and grant.award_amount.strip() and
            (grant.deadline or grant.decision_date)
        )
        if not has_critical_data:
            composite = min(composite, 6.5)
            if "composite_score" not in result.confidence_notes.lower():
                result.confidence_notes += " Composite score capped at 6.5 due to missing critical grant information."
        
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
        
        # 5. Ensure explicit uncertainty statement in confidence_notes
        missing_info = []
        if not grant.award_amount or not grant.award_amount.strip():
            missing_info.append("award amount")
        if not grant.deadline and not grant.decision_date:
            missing_info.append("timeline information")
        if not grant.preferred_applicants:
            missing_info.append("preferred applicant details")
        
        if missing_info:
            uncertainty_note = f"This assessment is limited by missing information about {', '.join(missing_info)}."
            if uncertainty_note.lower() not in result.confidence_notes.lower():
                result.confidence_notes = f"{uncertainty_note} {result.confidence_notes}".strip()
        
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
    
    def _parse_result(self, result_dict: Dict) -> EvaluationResult:
        """Parse LLM JSON response into EvaluationResult."""
        # Validate required fields
        required_fields = ["scores", "composite_score", "recommendation", "reasoning"]
        for field in required_fields:
            if field not in result_dict:
                raise ValueError(f"Missing required field in LLM response: {field}")
        
        # Validate score fields
        scores_dict = result_dict.get("scores", {})
        required_scores = ["timeline_viability", "winner_pattern_match", "mission_alignment", 
                           "application_burden", "award_structure"]
        for score_field in required_scores:
            if score_field not in scores_dict:
                raise ValueError(f"Missing required score field: {score_field}")
        
        # Parse scores
        scores_dict = result_dict["scores"]
        def _to_float(value) -> float:
            try:
                return float(value)
            except Exception:
                return 0.0
        scores = EvaluationScores(
            timeline_viability=_to_float(scores_dict.get("timeline_viability", 0)),
            winner_pattern_match=_to_float(scores_dict.get("winner_pattern_match", 0)),
            mission_alignment=_to_float(scores_dict.get("mission_alignment", 0)),
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
        recommendation = Recommendation(rec_str)
        
        # Parse reasoning
        reasoning = result_dict.get("reasoning", {})
        if not isinstance(reasoning, dict):
            raise ValueError("Reasoning must be a dictionary")
        
        # Ensure all reasoning fields are present
        required_reasoning = ["timeline", "winner_pattern_match", "mission_alignment", 
                             "application_burden", "award_structure"]
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
        
        # Parse paid-tier fields (optional)
        success_probability_range = result_dict.get("success_probability_range")
        decision_gates = result_dict.get("decision_gates")
        if decision_gates and not isinstance(decision_gates, list):
            decision_gates = None
        pattern_knowledge = result_dict.get("pattern_knowledge")
        opportunity_cost = result_dict.get("opportunity_cost")
        confidence_index = result_dict.get("confidence_index")
        if confidence_index is not None:
            try:
                confidence_index = float(confidence_index)
            except Exception:
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

