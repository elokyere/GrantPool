"""
GrantFilter - Decisive Grant Triage System

This module provides the core evaluation logic for determining whether
a grant is worth applying to based on user constraints.
"""

from typing import Dict, List, Optional, Literal
from dataclasses import dataclass
from enum import Enum


class Recommendation(Enum):
    APPLY = "APPLY"
    CONDITIONAL = "CONDITIONAL"
    PASS = "PASS"


@dataclass
class GrantInfo:
    """Extracted grant information from grant page."""
    name: str
    description: str
    deadline: Optional[str] = None
    decision_date: Optional[str] = None
    award_amount: Optional[str] = None
    award_structure: Optional[str] = None
    eligibility: Optional[str] = None
    application_requirements: Optional[List[str]] = None
    reporting_requirements: Optional[str] = None
    restrictions: Optional[List[str]] = None
    preferred_applicants: Optional[str] = None
    mission: Optional[str] = None


@dataclass
class UserContext:
    """User project context and constraints."""
    project_stage: str
    funding_need: str
    urgency: str  # e.g., "critical", "moderate", "flexible"
    project_description: str
    founder_type: Optional[str] = None  # e.g., "solo", "startup", "institution"
    timeline_constraints: Optional[str] = None


@dataclass
class EvaluationScores:
    """Individual dimension scores."""
    timeline_viability: float  # 0-10
    winner_pattern_match: float  # 0-10
    mission_alignment: float  # 0-10
    application_burden: float  # 0-10
    award_structure: float  # 0-10


@dataclass
class EvaluationResult:
    """Complete evaluation result."""
    scores: EvaluationScores
    composite_score: float  # 0-10
    recommendation: Recommendation
    reasoning: Dict[str, str]
    key_insights: List[str]
    red_flags: List[str]
    confidence_notes: str
    # Free-tier UX aid (always present for free tier; optional otherwise)
    actionable_next_step: Optional[str] = None
    # Paid-tier fields (None for free assessments)
    success_probability_range: Optional[str] = None  # e.g., "5-12%"
    decision_gates: Optional[List[str]] = None  # Concrete conditions for APPLY
    pattern_knowledge: Optional[str] = None  # Non-obvious pattern insights
    opportunity_cost: Optional[str] = None  # Time/alternative framing
    confidence_index: Optional[float] = None  # 0-1 confidence score

    def to_json(self) -> Dict:
        """Convert to JSON-serializable format."""
        result = {
            "scores": {
                "timeline_viability": self.scores.timeline_viability,
                "winner_pattern_match": self.scores.winner_pattern_match,
                "mission_alignment": self.scores.mission_alignment,
                "application_burden": self.scores.application_burden,
                "award_structure": self.scores.award_structure,
            },
            "composite_score": self.composite_score,
            "recommendation": self.recommendation.value,
            "reasoning": self.reasoning,
            "key_insights": self.key_insights,
            "red_flags": self.red_flags,
            "confidence_notes": self.confidence_notes,
        }
        if self.actionable_next_step:
            result["actionable_next_step"] = self.actionable_next_step
        # Add paid-tier fields if present
        if self.success_probability_range:
            result["success_probability_range"] = self.success_probability_range
        if self.decision_gates:
            result["decision_gates"] = self.decision_gates
        if self.pattern_knowledge:
            result["pattern_knowledge"] = self.pattern_knowledge
        if self.opportunity_cost:
            result["opportunity_cost"] = self.opportunity_cost
        if self.confidence_index is not None:
            result["confidence_index"] = self.confidence_index
        return result


class GrantEvaluator:
    """
    Evaluates grants using the GrantFilter decisive mode criteria.
    
    This evaluator is designed to be skeptical and protect user time
    by recommending PASS when grants are not worth pursuing.
    """
    
    def evaluate(self, grant: GrantInfo, user: UserContext) -> EvaluationResult:
        """
        Evaluate a grant against user constraints.
        
        Returns a decisive recommendation with detailed reasoning.
        """
        # Score each dimension
        timeline_score, timeline_reasoning = self._score_timeline(grant, user)
        winner_score, winner_reasoning = self._score_winner_pattern_match(grant, user)
        mission_score, mission_reasoning = self._score_mission_alignment(grant, user)
        burden_score, burden_reasoning = self._score_application_burden(grant, user)
        award_score, award_reasoning = self._score_award_structure(grant, user)
        
        scores = EvaluationScores(
            timeline_viability=timeline_score,
            winner_pattern_match=winner_score,
            mission_alignment=mission_score,
            application_burden=burden_score,
            award_structure=award_score,
        )
        
        # Calculate composite score (weighted average per quality guide)
        # Timeline 0.25, Winner Match 0.25, Alignment 0.25, Burden 0.15, Award 0.10
        composite = (
            timeline_score * 0.25 +
            winner_score * 0.25 +
            mission_score * 0.25 +
            burden_score * 0.15 +
            award_score * 0.10
        )
        
        # Identify red flags
        red_flags = self._identify_red_flags(scores, grant, user)
        
        # Generate key insights
        key_insights = self._generate_insights(grant, user, scores)
        
        # Assess confidence
        confidence_notes = self._assess_confidence(grant)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(
            composite, scores, red_flags, grant, user
        )
        
        return EvaluationResult(
            scores=scores,
            composite_score=composite,
            recommendation=recommendation,
            reasoning={
                "timeline": timeline_reasoning,
                "winner_pattern_match": winner_reasoning,
                "mission_alignment": mission_reasoning,
                "application_burden": burden_reasoning,
                "award_structure": award_reasoning,
            },
            key_insights=key_insights,
            red_flags=red_flags,
            confidence_notes=confidence_notes,
        )
    
    def _score_timeline(self, grant: GrantInfo, user: UserContext) -> tuple[float, str]:
        """Score timeline viability (0-10)."""
        # If no decision date, penalize heavily
        if not grant.decision_date:
            return 3.0, "Decision date not specified; cannot assess timeline alignment with user urgency."
        
        # If user has critical urgency but decision is far out, penalize
        if user.urgency == "critical":
            # Would need date parsing logic here
            return 4.0, "Decision timing may not align with critical funding urgency."
        
        # Default moderate score if timeline info is available
        return 6.0, "Timeline appears workable, but verify against specific deadlines."
    
    def _score_mission_alignment(self, grant: GrantInfo, user: UserContext) -> tuple[float, str]:
        """Score mission alignment (0-10)."""
        if not grant.mission:
            return 4.0, "Mission statement unclear; alignment cannot be confidently assessed."
        
        # Basic keyword matching (would be enhanced with NLP in production)
        project_lower = user.project_description.lower()
        mission_lower = grant.mission.lower()
        
        # Simple overlap check
        if any(word in mission_lower for word in project_lower.split()[:5]):
            return 7.0, "Some thematic alignment detected, but verify specific focus areas."
        
        return 5.0, "Mission alignment unclear from available information."
    
    def _score_winner_pattern_match(self, grant: GrantInfo, user: UserContext) -> tuple[float, str]:
        """
        Score winner pattern match (0-10).
        
        This requires researching past winners. Since this is a rule-based evaluator,
        we can only make inferences from grant language. For accurate scoring,
        use the LLM evaluator which can search for past winners.
        """
        # Without past winner data, we can only infer from grant language
        # This is a limitation of rule-based evaluation
        if grant.preferred_applicants:
            preferred_lower = grant.preferred_applicants.lower()
            
            # Check for institutional bias
            institutional_keywords = ["institution", "organization", "established", "prior grantee"]
            if any(keyword in preferred_lower for keyword in institutional_keywords):
                if user.founder_type == "solo":
                    return 2.0, "Grant explicitly favors institutions; solo founders are unlikely to be competitive. Past winner data needed to confirm pattern."
                return 5.0, "Grant shows preference for established entities. Past winner research recommended to verify actual patterns."
        
        # Default moderate score with uncertainty note
        return 5.0, "Winner pattern cannot be assessed without past winner data. Use LLM evaluator for accurate pattern matching based on research."
    
    def _score_application_burden(self, grant: GrantInfo, user: UserContext) -> tuple[float, str]:
        """Score application burden (0-10). Higher burden = lower score."""
        if not grant.application_requirements:
            return 5.0, "Application requirements not fully specified; burden cannot be assessed."
        
        burden_indicators = ["interview", "presentation", "detailed budget", "references", "letters"]
        burden_count = sum(1 for req in grant.application_requirements 
                          if any(indicator in req.lower() for indicator in burden_indicators))
        
        # More requirements = higher burden = lower score
        if burden_count >= 4:
            return 3.0, f"Application requires {burden_count}+ complex elements; burden is high relative to potential award."
        elif burden_count >= 2:
            return 5.0, "Moderate application burden with multiple required components."
        else:
            return 7.0, "Application burden appears reasonable."
    
    def _score_award_structure(self, grant: GrantInfo, user: UserContext) -> tuple[float, str]:
        """Score award structure (0-10). Penalize restrictions and gating."""
        score = 7.0
        issues = []
        
        if grant.restrictions:
            score -= len(grant.restrictions) * 0.5
            issues.append(f"{len(grant.restrictions)} restriction(s) specified")
        
        if grant.reporting_requirements:
            if "quarterly" in grant.reporting_requirements.lower() or "monthly" in grant.reporting_requirements.lower():
                score -= 2.0
                issues.append("Frequent reporting required")
        
        if grant.award_structure and "milestone" in grant.award_structure.lower():
            score -= 1.5
            issues.append("Milestone-gated payments")
        
        reasoning = "Award structure appears acceptable." if score >= 6.0 else \
                   f"Award structure has concerns: {', '.join(issues)}."
        
        return max(0.0, min(10.0, score)), reasoning
    
    def _identify_red_flags(self, scores: EvaluationScores, grant: GrantInfo, user: UserContext) -> List[str]:
        """Identify critical red flags."""
        flags = []
        
        if scores.timeline_viability <= 3:
            flags.append("Timeline does not align with user urgency")
        
        if scores.winner_pattern_match <= 3:
            flags.append("Winner pattern suggests poor fit—past winners don't match user profile")
        
        if scores.mission_alignment < 6:
            flags.append("Mission alignment too weak—would require significant narrative contortion")
        
        if scores.application_burden <= 3:
            flags.append("Application burden is disproportionate to award size")
        
        if not grant.decision_date and user.urgency == "critical":
            flags.append("Decision date unknown; cannot verify timeline alignment")
        
        return flags
    
    def _generate_insights(self, grant: GrantInfo, user: UserContext, scores: EvaluationScores) -> List[str]:
        """Generate key insights about the grant."""
        insights = []
        
        if scores.composite_score >= 7.5:
            insights.append("Strong overall alignment across multiple dimensions")
        elif scores.composite_score <= 4.0:
            insights.append("Multiple weak dimensions suggest this grant is not a good fit")
        
        if grant.preferred_applicants and user.founder_type:
            insights.append(f"Grant preferences: {grant.preferred_applicants[:100]}")
        
        return insights
    
    def _assess_confidence(self, grant: GrantInfo) -> str:
        """Assess confidence in evaluation based on information completeness."""
        missing = []
        
        if not grant.decision_date:
            missing.append("decision date")
        if not grant.award_amount:
            missing.append("award amount")
        if not grant.application_requirements:
            missing.append("application requirements")
        
        if missing:
            return f"Confidence reduced due to missing information: {', '.join(missing)}."
        return "Evaluation based on complete grant information."
    
    def _determine_recommendation(
        self,
        composite: float,
        scores: EvaluationScores,
        red_flags: List[str],
        grant: GrantInfo,
        user: UserContext
    ) -> Recommendation:
        """Determine final recommendation based on hard constraints per quality guide."""
        
        # Override rules (ignore composite if triggered)
        if scores.timeline_viability < 4 and user.urgency in ["critical", "moderate"]:
            # Check if user needs funds in <6 months (inferred from urgency)
            return Recommendation.PASS
        
        if scores.winner_pattern_match < 5:
            # No explicit "seeking new applicant types" check - default to PASS
            return Recommendation.PASS
        
        if scores.mission_alignment < 6:
            return Recommendation.PASS  # Don't perform for wrong fit
        
        if scores.application_burden < 4 and composite < 7.5:
            return Recommendation.PASS  # Not worth the effort
        
        # Standard thresholds per quality guide
        if composite >= 8.0:
            return Recommendation.APPLY
        
        if composite >= 6.5:
            return Recommendation.CONDITIONAL
        
        if composite >= 5.0:
            return Recommendation.PASS  # Soft pass
        
        # Default to hard pass
        return Recommendation.PASS

