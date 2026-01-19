"""
Scoring Service - Deterministic Grant Assessment Rubrics

This service provides pure, testable scoring functions for grant assessments.
All functions are deterministic (same inputs = same outputs) and handle
missing data gracefully (return null/unknown, never guess).

Key Principles:
- Free tier: Assess grant quality only (no project data needed)
- Paid tier: Assess personalized fit (requires project data)
- Always tag with source and confidence
- Epistemic discipline: honest about what we know vs. what we're guessing
"""

from typing import Dict, List, Optional, Literal, Any
from dataclasses import dataclass
from datetime import datetime, date
import re
import json
import logging
from decimal import Decimal, InvalidOperation
from anthropic import Anthropic
from app.core.config import settings


# Type aliases
ConfidenceLevel = Literal["high", "medium", "low", "unknown"]
SourceType = Literal["llm", "admin", "official", "estimated"]


@dataclass
class ClarityScoreResult:
    """Result of grant clarity assessment."""
    score: int  # 0-10
    rating: Literal["Excellent", "Good", "Limited", "Poor"]
    breakdown: Dict[str, Any]
    confidence: ConfidenceLevel
    source: SourceType


@dataclass
class AccessBarrierResult:
    """Result of access barrier assessment."""
    level: Literal["LOW", "MEDIUM", "HIGH"]
    estimated_hours: str  # e.g., "50-60" or "40+"
    description: str
    details: Dict[str, Any]
    confidence: ConfidenceLevel
    source: SourceType  # Added for consistency


@dataclass
class TimelineResult:
    """Result of timeline assessment."""
    status: Literal["GREEN", "YELLOW", "RED", "CLOSED", "UNKNOWN"]
    weeks_remaining: Optional[int]
    score: int  # 0-10
    message: str
    confidence: ConfidenceLevel
    source: Optional[SourceType]  # Added for consistency


@dataclass
class AwardStructureResult:
    """Result of award structure transparency assessment."""
    score: int  # 0-10
    transparency: Literal["Clear", "Partial", "Unclear"]
    details: List[str]
    confidence: ConfidenceLevel
    source: SourceType  # Added for consistency


@dataclass
class CompetitionResult:
    """Result of competition level assessment."""
    level: Optional[Literal["HIGHLY COMPETITIVE", "COMPETITIVE", "MODERATE", "ACCESSIBLE", "UNKNOWN"]]
    acceptance_rate: Optional[str]  # e.g., "~12%" or None
    applications: Optional[int]
    awards: Optional[int]
    message: str
    source: Optional[SourceType]
    confidence: ConfidenceLevel


@dataclass
class MissionAlignmentResult:
    """Result of mission alignment assessment (paid tier)."""
    score: int  # 0-10
    strong_matches: List[str]
    gaps: List[str]
    confidence: ConfidenceLevel
    source: SourceType


@dataclass
@dataclass
class ProfileMatchResult:
    """Result of profile match assessment (paid tier)."""
    score: Optional[int]  # 0-10 or None if insufficient data
    reason: Optional[Literal["INSUFFICIENT_DATA"]]  # Set if score is None
    similarities: List[str]
    differences: List[str]
    confidence: ConfidenceLevel
    recipient_count: int
    message: str
    recipient_details: List[Dict[str, Any]]  # Actual recipient data for display


@dataclass
class FundingFitResult:
    """Result of funding fit assessment (paid tier)."""
    fit: Literal["ALIGNED", "PARTIAL", "MISMATCHED", "INSUFFICIENT", "UNCERTAIN"]
    severity: Optional[Literal["CRITICAL", "HIGH", "MODERATE", "LOW"]]
    message: str
    recommendation: str
    confidence: ConfidenceLevel


@dataclass
class EffortRewardResult:
    """Result of effort-reward analysis (paid tier)."""
    assessment: Literal["WORTH_IT", "MAYBE", "SKIP"]
    estimated_hours: int
    potential_value: int  # In cents
    value_per_hour: int
    reasoning: str
    opportunity_cost: Literal["HIGH", "MODERATE", "LOW"]
    confidence: ConfidenceLevel


@dataclass
class SuccessProbabilityResult:
    """Result of success probability estimation (paid tier)."""
    range: Optional[str]  # e.g., "15-20%" or None if unknown
    base_rate: Optional[str]  # e.g., "12%" or None
    explanation: str
    confidence: ConfidenceLevel
    source: Optional[SourceType]


@dataclass
class GrantReadinessResult:
    """Result of grant data readiness assessment."""
    score: int  # 0-10
    tier: Literal["HIGH", "MEDIUM", "LOW"]
    missing_data: List[str]
    has_award_amount: bool
    has_deadline: bool
    has_eligibility: bool
    has_recipients: bool
    has_acceptance_rate: bool
    completeness_percentage: float


class ScoringService:
    """Deterministic scoring service for grant assessments."""
    
    # LLM client for emergent intelligence (optional - falls back to keyword-based if unavailable)
    _llm_client: Optional[Anthropic] = None
    
    @classmethod
    def _get_llm_client(cls) -> Optional[Anthropic]:
        """Get or create LLM client for intelligent project focus extraction."""
        if cls._llm_client is None and settings.ANTHROPIC_API_KEY:
            try:
                cls._llm_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to initialize LLM client: {e}")
        return cls._llm_client
    
    @staticmethod
    def _extract_project_focus_intelligent(project_name: str, project_description: str) -> Dict[str, Any]:
        """
        Use LLM to intelligently extract project focus areas from any project description.
        
        This is truly emergent - can understand any domain, concern, or initiative without
        hardcoded term lists. Falls back to keyword-based extraction if LLM unavailable.
        
        Returns:
            Dict with:
            - focus_areas: List of key focus areas (e.g., ["urban forestry", "climate resilience", "community engagement"])
            - primary_domain: Main domain category (e.g., "environmental", "social", "tech", "arts", "health", "education", "other")
            - key_themes: List of thematic keywords
            - human_readable_summary: Natural language summary of project focus
        """
        logger = logging.getLogger(__name__)
        
        # If no project description, return minimal info
        if not project_description or project_description.strip().lower() in ["not specified", "n/a", ""]:
            return {
                "focus_areas": [],
                "primary_domain": "unknown",
                "key_themes": [],
                "human_readable_summary": "Project focus not specified"
            }
        
        # Try LLM-based extraction first (emergent intelligence)
        llm_client = ScoringService._get_llm_client()
        if llm_client:
            try:
                system_prompt = """You are an intelligent project analysis assistant. Extract the core focus areas, capabilities, and themes from any project description, regardless of domain.

Your task:
1. Identify 2-4 key focus areas (specific initiatives or goals)
2. Determine the primary domain category (environmental, social, tech, arts, health, education, research, economic, cultural, or other)
3. Identify technical/geospatial capabilities if present (e.g., IoT sensors, GIS mapping, data monitoring, remote sensing, spatial analysis)
4. Extract 3-5 key thematic keywords
5. Create a concise human-readable summary (1-2 sentences) of what the project focuses on

IMPORTANT: Projects can be multi-faceted. An environmental project may also have technical components (IoT sensors, GIS mapping). A social project may use data systems. Recognize these hybrid capabilities.

Be intelligent and adaptive - understand the project's actual concerns, initiatives, AND capabilities, not just surface keywords.

Return ONLY valid JSON:
{
  "focus_areas": ["string", "string"],
  "primary_domain": "string",
  "technical_capabilities": ["string"] or [],
  "key_themes": ["string", "string"],
  "human_readable_summary": "string"
}"""

                user_message = f"""Analyze this project and extract its focus areas:

Project Name: {project_name}
Project Description: {project_description[:2000]}  # Limit to avoid token limits

Extract the core focus areas, domain, themes, and create a summary."""

                message = llm_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=500,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}]
                )
                
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
                    result = json.loads(response_text)
                    # Ensure technical_capabilities exists (for backward compatibility)
                    if "technical_capabilities" not in result:
                        result["technical_capabilities"] = []
                    logger.debug(f"LLM extracted project focus: domain={result.get('primary_domain')}, focus_areas={result.get('focus_areas')}, tech_capabilities={result.get('technical_capabilities')}")
                    return result
                except json.JSONDecodeError:
                    # Try to extract JSON from text if wrapped
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                        logger.info(f"LLM extracted project focus (from wrapped text): domain={result.get('primary_domain')}")
                        return result
                    else:
                        logger.warning(f"Failed to parse LLM response as JSON, falling back to keyword extraction")
            except Exception as e:
                logger.warning(f"LLM extraction failed: {e}, falling back to keyword extraction")
        
        # Fallback: Keyword-based extraction (less intelligent but always works)
        return ScoringService._extract_project_focus_keywords(project_name, project_description)
    
    @staticmethod
    def _generate_mission_alignment_explanation(
        grant_text: str, project_text: str, project_name: str, grant_name: str, score: int
    ) -> Optional[str]:
        """
        Use LLM to generate intelligent, contextual explanation of mission alignment.
        
        This provides deep, nuanced explanations that show understanding of the relationship
        between project and grant, rather than shallow template-based messages.
        """
        logger = logging.getLogger(__name__)
        
        llm_client = ScoringService._get_llm_client()
        if not llm_client:
            return None
        
        try:
            system_prompt = """You are an expert grant evaluation analyst. Your task is to provide deep, insightful explanations of mission alignment between projects and grants.

When explaining alignment (or lack thereof), you must:
1. Show deep understanding of BOTH the project and grant
2. Recognize multi-faceted projects (e.g., environmental projects with technical components)
3. Identify specific areas of alignment or misalignment
4. Provide actionable insights, not just surface-level observations
5. Be nuanced - recognize when projects have capabilities that aren't immediately obvious

For LOW scores (0-3), explain:
- What the grant actually requires (not just keywords)
- What the project actually offers (not just keywords)
- Why there's a mismatch (be specific)
- Whether the project has hidden capabilities that could align

Be intelligent, contextual, and show you understand the relationship between project and grant.

Return ONLY a clear, concise explanation (2-4 sentences). No JSON, just plain text."""

            user_message = f"""Analyze the mission alignment between this project and grant:

PROJECT: {project_name}
Project Description: {project_text[:1500]}

GRANT: {grant_name}
Grant Information: {grant_text[:1500]}

Current Alignment Score: {score}/10

Provide a deep, insightful explanation of why the alignment is {score}/10. Show understanding of what the grant requires and what the project offers. Be specific and nuanced."""

            message = llm_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            
            explanation = message.content[0].text.strip()
            logger.debug(f"Generated intelligent mission alignment explanation (score={score})")
            return explanation
            
        except Exception as e:
            logger.warning(f"Failed to generate intelligent explanation: {e}")
            return None
    
    @staticmethod
    def _extract_project_focus_keywords(project_name: str, project_description: str) -> Dict[str, Any]:
        """
        Fallback keyword-based extraction when LLM unavailable.
        Less intelligent but always works.
        """
        text = f"{project_name} {project_description}".lower()
        
        # Extract meaningful words (4+ chars, not common stop words)
        stop_words = {"project", "initiative", "program", "organization", "will", "this", "that", "with", "from", "their", "they", "them", "these", "those"}
        words = [w for w in re.findall(r'\b\w{4,}\b', text) if w not in stop_words]
        
        # Get most frequent meaningful words (focus areas)
        from collections import Counter
        word_freq = Counter(words)
        focus_areas = [word for word, count in word_freq.most_common(4)]
        
        # Determine domain (basic keyword matching)
        domain_keywords = {
            "environmental": ["environment", "climate", "sustainability", "green", "tree", "forest", "ecosystem", "conservation", "wildlife", "biodiversity", "reforestation", "canopy", "urban heat"],
            "social": ["community", "social", "welfare", "development", "urban", "neighborhood", "residents", "stakeholders"],
            "tech": ["technology", "software", "app", "platform", "digital", "system", "data", "gis", "geospatial", "iot", "sensor"],
            "arts": ["art", "artwork", "curate", "curation", "gallery", "exhibition", "artist", "creative", "museum"],
            "health": ["health", "medical", "healthcare", "wellness", "disease", "treatment", "hospital"],
            "education": ["education", "learning", "school", "university", "training", "curriculum", "students"],
            "research": ["research", "study", "analysis", "investigation", "academic", "scholarly"]
        }
        
        primary_domain = "other"
        max_matches = 0
        for domain, keywords in domain_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text)
            if matches > max_matches:
                max_matches = matches
                primary_domain = domain
        
        # Create summary
        if focus_areas:
            summary = f"Project focuses on {', '.join(focus_areas[:3])}"
        else:
            summary = "Project focus areas not clearly identifiable"
        
        return {
            "focus_areas": focus_areas[:4],
            "primary_domain": primary_domain,
            "technical_capabilities": [],  # Keyword extraction can't detect this reliably
            "key_themes": focus_areas[:5],
            "human_readable_summary": summary
        }
    
    # ==================== GRANT READINESS SCORING ====================
    
    @staticmethod
    def calculate_grant_readiness_score(grant: Dict[str, Any]) -> GrantReadinessResult:
        """
        Calculate Grant Readiness Score (0-10) based on data completeness.
        
        This determines what kind of assessment is possible:
        - HIGH (8-10): Full strategic analysis possible
        - MEDIUM (5-7): Partial analysis possible
        - LOW (0-4): Limited to mission alignment only
        
        Scoring:
        - Award amount disclosed: 3 points (most critical)
        - Deadline (non-rolling): 1 point
        - Eligibility criteria: 2 points
        - Past recipients (5+): 2 points
        - Acceptance rate: 1 point
        - Preferred applicants: 1 point
        """
        score = 0
        missing = []
        
        # CRITICAL DATA (6 points total)
        has_award_amount = False
        if grant.get("award_amount"):
            amount_str = str(grant["award_amount"]).strip()
            if amount_str and amount_str.lower() not in ["varies", "contact us", "not disclosed", "n/a", "tbd"]:
                numbers = re.findall(r'[\d,]+', amount_str.replace(',', ''))
                if numbers:
                    score += 3
                    has_award_amount = True
                else:
                    missing.append("award_amount")
            else:
                missing.append("award_amount")
        else:
            missing.append("award_amount")
        
        has_deadline = False
        deadline = grant.get("deadline")
        if deadline and deadline.lower() not in ["rolling", "ongoing", "open until", "no deadline"]:
            score += 1
            has_deadline = True
        
        has_eligibility = False
        eligibility = grant.get("eligibility") or ""
        if len(eligibility) > 50 and eligibility.strip():
            score += 2
            has_eligibility = True
        else:
            missing.append("eligibility_criteria")
        
        # STRATEGIC DATA (4 points total)
        has_recipients = False
        recipient_patterns = grant.get("recipient_patterns") or {}
        recipients = recipient_patterns.get("recipients") or []
        if recipients and len(recipients) >= 5:
            score += 2
            has_recipients = True
        else:
            missing.append("past_recipients")
        
        has_acceptance_rate = False
        # Check for acceptance rate in competition stats or grant quality data
        competition_stats = recipient_patterns.get("competition_stats") or {}
        acceptance_rate = competition_stats.get("acceptance_rate")
        if acceptance_rate is not None:
            score += 1
            has_acceptance_rate = True
        else:
            missing.append("acceptance_rate")
        
        preferred_applicants = grant.get("preferred_applicants") or ""
        if len(preferred_applicants) > 50:
            score += 1
        
        # Determine tier
        if score >= 8:
            tier = "HIGH"
        elif score >= 5:
            tier = "MEDIUM"
        else:
            tier = "LOW"
        
        completeness_percentage = (score / 10.0) * 100
        
        return GrantReadinessResult(
            score=score,
            tier=tier,
            missing_data=missing,
            has_award_amount=has_award_amount,
            has_deadline=has_deadline,
            has_eligibility=has_eligibility,
            has_recipients=has_recipients,
            has_acceptance_rate=has_acceptance_rate,
            completeness_percentage=completeness_percentage
        )
    
    # ==================== FREE TIER SCORING ====================
    
    @staticmethod
    def calculate_clarity_score(grant: Dict[str, Any]) -> ClarityScoreResult:
        """
        Calculate Opportunity Clarity Score (0-10).
        
        Assesses how well-documented and transparent the grant is.
        """
        score = 0
        breakdown = {}
        confidence = "high"
        
        # Award amount disclosed (+3)
        if grant.get("award_amount"):
            amount_str = str(grant["award_amount"]).strip()
            # Check if it's a meaningful amount (not just "varies" or "contact us")
            if amount_str and amount_str.lower() not in ["varies", "contact us", "not disclosed", "n/a", "tbd"]:
                # Try to extract numeric value
                numbers = re.findall(r'[\d,]+', amount_str.replace(',', ''))
                if numbers:
                    score += 3
                    breakdown["award_amount"] = "disclosed"
                else:
                    breakdown["award_amount"] = "mentioned but unclear"
            else:
                breakdown["award_amount"] = "not disclosed"
        else:
            breakdown["award_amount"] = "not disclosed"
        
        # Clear eligibility criteria (+2)
        eligibility = grant.get("eligibility") or ""
        if len(eligibility) > 50 and eligibility.strip():
            score += 2
            breakdown["eligibility"] = "clear"
        else:
            breakdown["eligibility"] = "vague or missing"
        
        # Past recipients available (+2)
        recipient_patterns = grant.get("recipient_patterns") or {}
        recipients = recipient_patterns.get("recipients") or []
        if recipients and len(recipients) >= 5:
            score += 2
            breakdown["recipients"] = f"available ({len(recipients)} profiles)"
        else:
            breakdown["recipients"] = "not listed or insufficient"
        
        # Selection criteria disclosed (+2)
        preferred_applicants = grant.get("preferred_applicants") or ""
        if len(preferred_applicants) > 50:
            score += 2
            breakdown["selection_criteria"] = "disclosed"
        else:
            breakdown["selection_criteria"] = "vague or missing"
        
        # Application requirements clear (+1)
        app_requirements = grant.get("application_requirements")
        if app_requirements and (isinstance(app_requirements, list) and len(app_requirements) > 0 or 
                                isinstance(app_requirements, str) and len(app_requirements) > 20):
            score += 1
            breakdown["application_requirements"] = "clear"
        else:
            breakdown["application_requirements"] = "unclear"
        
        # Determine rating
        if score >= 8:
            rating = "Excellent"
        elif score >= 6:
            rating = "Good"
        elif score >= 4:
            rating = "Limited"
        else:
            rating = "Poor"
        
        # Confidence based on data completeness
        if score >= 8:
            confidence = "high"
        elif score >= 6:
            confidence = "medium"
        else:
            confidence = "low"
        
        return ClarityScoreResult(
            score=min(score, 10),
            rating=rating,
            breakdown=breakdown,
            confidence=confidence,
            source="llm"  # Data extracted from grant page
        )
    
    @staticmethod
    def assess_access_barrier(grant: Dict[str, Any]) -> AccessBarrierResult:
        """
        Assess Access Barrier (LOW/MEDIUM/HIGH).
        
        Evaluates how difficult it is to apply.
        """
        points = 0
        details = {}
        
        # Estimate application length from requirements
        app_requirements = grant.get("application_requirements") or []
        if isinstance(app_requirements, str):
            # Try to estimate pages from text length
            estimated_pages = max(1, len(app_requirements) // 500)  # Rough estimate
        elif isinstance(app_requirements, list):
            estimated_pages = len(app_requirements)
        else:
            estimated_pages = 5  # Default assumption
        
        details["estimated_pages"] = estimated_pages
        
        # Application length scoring
        if estimated_pages > 20:
            points += 3
        elif estimated_pages > 10:
            points += 2
        else:
            points += 1
        
        # Required documentation
        doc_count = 0
        if isinstance(app_requirements, list):
            doc_count = len([req for req in app_requirements if any(keyword in req.lower() 
                          for keyword in ["letter", "reference", "document", "certificate", "proof"])])
        details["document_count"] = doc_count
        
        if doc_count > 5:
            points += 2
        elif doc_count > 2:
            points += 1
        
        # Letters of recommendation (infer from requirements)
        letters_required = 0
        requirements_text = str(app_requirements).lower() if app_requirements else ""
        if "letter of recommendation" in requirements_text or "reference letter" in requirements_text or "letters of recommendation" in requirements_text:
            # Try to extract number (digits or words)
            letter_matches = re.findall(r'(\d+)\s*(?:letter|reference)', requirements_text)
            if letter_matches:
                letters_required = int(letter_matches[0])
            elif any(word in requirements_text for word in ["two", "2", "pair"]):
                letters_required = 2
            elif any(word in requirements_text for word in ["three", "3"]):
                letters_required = 3
            elif any(word in requirements_text for word in ["one", "1", "single"]):
                letters_required = 1
            else:
                letters_required = 2  # Default assumption
        details["letters_required"] = letters_required
        
        if letters_required > 2:
            points += 2
        elif letters_required > 0:
            points += 1
        
        # Institutional requirements
        eligibility = (grant.get("eligibility") or "").lower()
        preferred = (grant.get("preferred_applicants") or "").lower()
        requires_org = any(keyword in eligibility + " " + preferred 
                          for keyword in ["organization", "institution", "affiliation", "sponsor"])
        details["requires_institutional_affiliation"] = requires_org
        
        if requires_org:
            points += 2
        
        # Fiscal sponsor requirement
        requires_fiscal = "fiscal sponsor" in eligibility.lower() or "fiscal sponsor" in preferred.lower()
        details["requires_fiscal_sponsor"] = requires_fiscal
        
        if requires_fiscal:
            points += 2
        
        # Nomination/referral required
        requires_nomination = any(keyword in eligibility.lower() + " " + preferred.lower()
                                 for keyword in ["nomination", "nominate", "referral", "sponsor"])
        details["requires_nomination"] = requires_nomination
        
        if requires_nomination:
            points += 3
        
        # Calculate estimated prep hours
        base_hours = 20
        prep_hours = base_hours
        prep_hours += estimated_pages * 2
        prep_hours += letters_required * 8
        prep_hours += doc_count * 3
        
        # Determine barrier level
        if points >= 8:
            level = "HIGH"
            hours_str = f"{prep_hours}+"
            description = "Significant time investment required"
        elif points >= 4:
            level = "MEDIUM"
            hours_str = f"{prep_hours-10}-{prep_hours}"
            description = "Moderate preparation needed"
        else:
            level = "LOW"
            hours_str = f"{prep_hours-20}-{prep_hours-10}"
            description = "Relatively straightforward application"
        
        return AccessBarrierResult(
            level=level,
            estimated_hours=hours_str,
            description=description,
            details=details,
            confidence="medium",  # Estimates based on requirements parsing
            source="llm"  # Data extracted from grant page/requirements
        )
    
    @staticmethod
    def assess_timeline(grant: Dict[str, Any], current_date: Optional[date] = None) -> TimelineResult:
        """
        Assess Timeline Viability (GREEN/YELLOW/RED).
        
        Evaluates if there's enough time before deadline.
        """
        if current_date is None:
            current_date = date.today()
        
        deadline_str = grant.get("deadline")
        if not deadline_str:
            return TimelineResult(
                status="UNKNOWN",
                weeks_remaining=None,
                score=0,
                message="Deadline not specified",
                confidence="unknown",
                source=None
            )
        
        # Try to parse deadline (simplified - may need more robust parsing)
        # This is a basic implementation - you may want to enhance date parsing
        try:
            # Try common date formats
            deadline = None
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"]:
                try:
                    deadline = datetime.strptime(deadline_str.strip(), fmt).date()
                    break
                except ValueError:
                    continue
            
            if deadline is None:
                return TimelineResult(
                    status="UNKNOWN",
                    weeks_remaining=None,
                    score=0,
                    message="Deadline format unclear",
                    confidence="low",
                    source="llm"
                )
            
            if deadline < current_date:
                return TimelineResult(
                    status="CLOSED",
                    weeks_remaining=0,
                    score=0,
                    message="Deadline has passed",
                    confidence="high",
                    source="llm"
                )
            
            # Calculate weeks remaining
            delta = deadline - current_date
            weeks = delta.days // 7
            
            # Determine status
            if weeks < 6:
                status = "RED"
                message = "Short timeline - only for experienced applicants"
                score = max(0, int((weeks / 6) * 6))
            elif weeks < 12:
                status = "YELLOW"
                message = "Moderate timeline - start preparation now"
                score = min(10, int(6 + ((weeks - 6) / 6) * 4))
            else:
                status = "GREEN"
                message = "Good timeline - ample preparation time"
                score = min(10, int((weeks / 12) * 10))
            
            return TimelineResult(
                status=status,
                weeks_remaining=weeks,
                score=score,
                message=message,
                confidence="high",
                source="llm"
            )
            
        except Exception:
            return TimelineResult(
                status="UNKNOWN",
                weeks_remaining=None,
                score=0,
                message="Unable to parse deadline",
                confidence="low",
                source="llm"
            )
    
    @staticmethod
    def assess_award_structure(grant: Dict[str, Any]) -> AwardStructureResult:
        """
        Assess Award Structure Transparency (0-10).
        
        Evaluates how clear the award structure is.
        """
        score = 0
        details = []
        
        # Award amount disclosed
        award_amount = grant.get("award_amount")
        if award_amount:
            amount_str = str(award_amount).strip()
            if amount_str and amount_str.lower() not in ["varies", "contact us", "not disclosed", "n/a", "tbd"]:
                score += 4
                details.append(f"Amount: {amount_str}")
            else:
                details.append("⚠ Amount not disclosed")
        else:
            details.append("⚠ Amount not disclosed")
        
        # Award type clear
        award_structure = grant.get("award_structure") or ""
        if award_structure and len(award_structure) > 10:
            score += 2
            details.append(f"Type: {award_structure[:50]}...")
        else:
            details.append("Award type unclear")
        
        # Duration specified (try to extract from award_structure or description)
        structure_text = (grant.get("award_structure") or "").lower() + " " + (grant.get("description") or "").lower()
        duration_match = re.search(r'(\d+)\s*(?:month|year|week)', structure_text)
        if duration_match:
            score += 2
            details.append(f"Duration: {duration_match.group(0)}")
        
        # Restrictions/allowances clear
        restrictions = grant.get("restrictions") or []
        if restrictions:
            score += 2
            details.append("Spending guidelines provided")
        
        # Determine transparency
        if score >= 7:
            transparency = "Clear"
        elif score >= 4:
            transparency = "Partial"
        else:
            transparency = "Unclear"
        
        return AwardStructureResult(
            score=min(score, 10),
            transparency=transparency,
            details=details,
            confidence="high" if score >= 7 else "medium",
            source="llm"  # Data extracted from grant page
        )
    
    @staticmethod
    def assess_competition(grant: Dict[str, Any]) -> CompetitionResult:
        """
        Assess Competition Level (if data available).
        
        Returns UNKNOWN if no data, otherwise categorizes competition level.
        """
        recipient_patterns = grant.get("recipient_patterns") or {}
        competition_stats = recipient_patterns.get("competition_stats") or {}
        
        # Check if we have official stats
        if competition_stats.get("source") == "official":
            applications = competition_stats.get("applications_received")
            awards = competition_stats.get("awards_made")
            acceptance_rate = competition_stats.get("acceptance_rate")
            
            if acceptance_rate is not None:
                rate = float(acceptance_rate)
                if rate < 5:
                    level = "HIGHLY COMPETITIVE"
                    message = "Very selective - strong applications only"
                elif rate < 15:
                    level = "COMPETITIVE"
                    message = "Selective - requires strong fit"
                elif rate < 30:
                    level = "MODERATE"
                    message = "Reasonable odds with good application"
                else:
                    level = "ACCESSIBLE"
                    message = "Higher acceptance rate"
                
                return CompetitionResult(
                    level=level,
                    acceptance_rate=f"~{int(rate)}%",
                    applications=applications,
                    awards=awards,
                    message=message,
                    source="official",
                    confidence="high"
                )
        
        # Check if we have estimated stats
        if competition_stats.get("source") == "estimated":
            acceptance_rate = competition_stats.get("acceptance_rate")
            if acceptance_rate is not None:
                rate = float(acceptance_rate)
                # Same categorization but with lower confidence
                if rate < 5:
                    level = "HIGHLY COMPETITIVE"
                elif rate < 15:
                    level = "COMPETITIVE"
                elif rate < 30:
                    level = "MODERATE"
                else:
                    level = "ACCESSIBLE"
                
                return CompetitionResult(
                    level=level,
                    acceptance_rate=f"~{int(rate)}%",
                    applications=competition_stats.get("applications_received"),
                    awards=competition_stats.get("awards_made"),
                    message=f"Estimated: {level.lower()}",
                    source="estimated",
                    confidence="medium"
                )
        
        # No data available
        return CompetitionResult(
            level="UNKNOWN",
            acceptance_rate=None,
            applications=None,
            awards=None,
            message="Competition data not available",
            source=None,
            confidence="unknown"
        )
    
    @staticmethod
    def calculate_free_composite(clarity: int, timeline: int, award: int, access: int) -> int:
        """
        Calculate composite score for free tier assessments.
        
        Formula: Weighted average of grant quality dimensions.
        """
        # Invert access barrier (low barrier = high score)
        # Access barrier: LOW=10, MEDIUM=6, HIGH=2 (approximate)
        access_score = 10 - (access if isinstance(access, int) else 6)
        
        # Weighted formula
        composite = (
            clarity * 0.30 +      # Clarity is most important
            timeline * 0.25 +     # Timeline matters
            award * 0.25 +        # Award structure transparency
            access_score * 0.20   # Access barrier (inverted)
        )
        
        return int(round(composite))
    
    # ==================== PAID TIER SCORING ====================
    
    @staticmethod
    def calculate_mission_alignment(grant: Dict[str, Any], project: Dict[str, Any]) -> MissionAlignmentResult:
        """
        Calculate Mission Alignment Score (0-10) for paid assessments.
        
        Requires project data to assess fit. Provides logical comparison of project and grant descriptions.
        
        CRITICAL: This function must use the ACTUAL project data passed in, never hardcoded values.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract full descriptions for logical comparison
        grant_mission = grant.get("mission") or ""
        grant_description = grant.get("description") or ""
        grant_name = grant.get("name") or ""
        grant_text = f"{grant_mission} {grant_description}".strip()
        
        project_description = project.get("description") or ""
        project_name = project.get("name") or ""
        project_text = f"{project_name} {project_description}".strip()
        
        # Log project data being evaluated to catch mismatches (debug level for production)
        logger.debug(f"calculate_mission_alignment called with project: name='{project_name}', description_length={len(project_description)}")
        if project_name:
            logger.debug(f"Project name: {project_name}")
        if project_description:
            logger.debug(f"Project description (first 150 chars): {project_description[:150]}...")
        
        # If no project description, cannot assess alignment
        if not project_text or project_text.lower() in ["not specified", "n/a", ""]:
            return MissionAlignmentResult(
                score=0,
                strong_matches=[],
                gaps=["Project description not provided - cannot assess mission alignment"],
                confidence="low",
                source="rule_based"
            )
        
        # Extract keywords for basic matching
        grant_keywords = set(re.findall(r'\b\w{4,}\b', grant_text.lower()))
        project_keywords = set(re.findall(r'\b\w{4,}\b', project_text.lower()))
        
        # Calculate overlap (Jaccard similarity)
        overlap = len(grant_keywords & project_keywords)
        total_unique = len(grant_keywords | project_keywords)
        keyword_overlap = overlap / total_unique if total_unique > 0 else 0
        
        # Base score from keyword overlap (scale to 0-7)
        score = int(keyword_overlap * 7)
        strong_matches = []
        gaps = []
        
        # Logical comparison: Check for fundamental mismatches
        grant_lower = grant_text.lower()
        project_lower = project_text.lower()
        
        # EMERGENT INTELLIGENCE: Use LLM to extract project focus (adapts to any domain/concern/initiative)
        project_focus_data = ScoringService._extract_project_focus_intelligent(project_name, project_description)
        project_focus_areas = project_focus_data.get("focus_areas", [])
        project_domain = project_focus_data.get("primary_domain", "unknown")
        project_summary = project_focus_data.get("human_readable_summary", "your project")
        
        # Use intelligent summary for human-readable focus description
        if project_focus_areas:
            project_focus = ", ".join(project_focus_areas[:3]) if len(project_focus_areas) > 1 else project_focus_areas[0]
        else:
            project_focus = project_summary
        
        # Extract grant domain using similar intelligent approach (simplified for now)
        grant_domain_keywords = {
            "conservation": ["conservation", "wildlife", "biodiversity", "species", "habitat"],
            "environmental": ["environment", "environmental", "climate", "sustainability", "green", "tree", "forest", "reforestation", "ecosystem"],
            "tech": ["technology", "software", "app", "platform", "digital", "system", "data", "gis", "geospatial", "iot", "sensor"],
            "art": ["art", "artwork", "curate", "curation", "gallery", "exhibition", "artist", "creative", "museum"],
            "social": ["community", "social", "welfare", "education", "health", "development", "urban", "neighborhood"]
        }
        
        grant_domains = []
        for domain, keywords in grant_domain_keywords.items():
            if any(term in grant_lower for term in keywords):
                grant_domains.append(domain)
        
        # DEEP SEMANTIC ANALYSIS: Use LLM to assess project-grant relationship intelligently
        # This replaces shallow keyword matching with understanding of multi-faceted projects
        has_fundamental_mismatch = False
        mismatch_reason = None
        
        # Check for technical/geospatial capabilities in project (even if primary domain isn't "tech")
        # Use both keyword detection AND LLM-extracted capabilities
        project_tech_capabilities_llm = project_focus_data.get("technical_capabilities", [])
        project_has_tech_capabilities_keywords = any(term in project_lower for term in [
            "iot", "sensor", "monitoring", "data", "gis", "geospatial", "mapping", "satellite",
            "technology", "digital", "software", "platform", "system", "analytics", "tracking",
            "smart", "automated", "remote sensing", "spatial", "coordinates", "gps"
        ])
        project_has_tech_capabilities = project_has_tech_capabilities_keywords or len(project_tech_capabilities_llm) > 0
        
        # Check for technical/geospatial requirements in grant
        grant_requires_tech = any(term in grant_lower for term in [
            "technical", "geospatial", "gis", "technology", "data", "sensor", "iot",
            "mapping", "satellite", "remote sensing", "spatial", "digital", "software"
        ])
        
        if grant_domains and project_domain != "unknown":
            # Conservation/environmental grants vs non-environmental projects (arts only - clear mismatch)
            if ("conservation" in grant_domains or "environmental" in grant_domains) and project_domain == "arts":
                has_fundamental_mismatch = True
                grant_focus = "conservation/environment" if "conservation" in grant_domains else "environmental sustainability"
                mismatch_reason = f"Fundamental mismatch: This grant focuses on {grant_focus}, while your project focuses on {project_focus}. These domains do not align, which significantly reduces your chances of success."
            
            # Tech grants: Deep analysis - check if project has required capabilities
            elif "tech" in grant_domains or grant_requires_tech:
                # If grant requires tech/geospatial, check if project has those capabilities
                if project_has_tech_capabilities:
                    # Project HAS technical capabilities - this is actually a STRONG match
                    score = min(10, score + 2)
                    # Extract specific tech capabilities mentioned
                    tech_capabilities = [term for term in [
                        "IoT sensors", "data monitoring", "GIS mapping", "geospatial analysis",
                        "smart technology", "digital systems", "remote sensing"
                    ] if term.lower().replace(" ", "") in project_lower.replace(" ", "")]
                    
                    if tech_capabilities:
                        strong_matches.append(f"Technical alignment: This grant requires technical/geospatial expertise, and your project includes {', '.join(tech_capabilities[:2])}, demonstrating the required capabilities.")
                    else:
                        strong_matches.append(f"Technical alignment: This grant requires technical/geospatial expertise, and your project demonstrates these capabilities through its use of technology and data systems.")
                elif project_domain == "environmental" and grant_requires_tech:
                    # Environmental project + tech grant: Check if it's a hybrid (environmental-tech)
                    # Many environmental projects use tech (IoT, sensors, GIS) - don't penalize
                    # Instead, provide nuanced assessment
                    if any(term in project_lower for term in ["monitor", "track", "measure", "analyze", "map"]):
                        # Project likely has some tech component, just not explicitly stated
                        score = max(0, score - 1)  # Minor penalty, not fundamental mismatch
                        gaps.append(f"Partial technical alignment: This grant emphasizes technical/geospatial expertise. While your project ({project_focus}) addresses environmental priorities, consider highlighting any technical components (data collection, monitoring systems, mapping tools) in your application to strengthen alignment.")
                    else:
                        # Truly no tech component
                        score = max(0, score - 2)
                        gaps.append(f"Technical capability gap: This grant requires technical or geospatial expertise (e.g., GIS mapping, data systems, remote sensing). Your project focuses on {project_focus}, which may not fully meet the technical requirements. Consider whether your project can incorporate technical components or if this grant is the right fit.")
                else:
                    # Non-environmental, non-tech project + tech grant = mismatch
                    has_fundamental_mismatch = True
                    mismatch_reason = f"Technical capability mismatch: This grant requires technical or geospatial expertise (e.g., GIS, data systems, remote sensing), but your project focuses on {project_focus} without apparent technical components. The required skills and focus areas do not align."
            
            # Positive alignment: Environmental projects + conservation/environmental grants
            elif ("conservation" in grant_domains or "environmental" in grant_domains) and project_domain == "environmental":
                score = min(10, score + 2)
                strong_matches.append(f"Strong domain alignment: This grant focuses on conservation/environment, and your project ({project_focus}) aligns with these priorities.")
        
        # Apply mismatch penalties
        if has_fundamental_mismatch:
            score = 0
            gaps.append(mismatch_reason)
        elif mismatch_reason:  # Less severe mismatch
            score = max(0, score - 3)
            gaps.append(mismatch_reason)
        
        # Geographic alignment
        grant_geo = grant.get("eligibility") or ""
        project_country = project.get("organization_country")
        if project_country and project_country.lower() in grant_geo.lower():
            score = min(10, score + 1)
            strong_matches.append(f"Geographic alignment: Your organization is located in {project_country}, which matches the grant's geographic focus.")
        elif project_country and grant_geo:
            # Show full geographic eligibility text without truncation
            gaps.append(f"Geographic mismatch: This grant targets organizations in {grant_geo.strip()}, but your organization is located in {project_country}. This geographic restriction may disqualify your application.")
        
        # Sector alignment (if available in metadata)
        project_sectors = project.get("profile_metadata", {}).get("sectors", []) or []
        if project_sectors:
            sector_text = " ".join(project_sectors).lower()
            if any(sector in grant_text.lower() for sector in project_sectors):
                score = min(10, score + 1)
                strong_matches.append(f"Sector alignment: Your project operates in {', '.join(project_sectors)}, which aligns with the grant's focus areas.")
            else:
                gaps.append(f"Sector mismatch: This grant focuses on different sectors than your project. Your project operates in {', '.join(project_sectors)}, which may not align with the funder's priorities.")
        
        # If score is 0 or very low, provide intelligent explanation using LLM
        if score <= 2 and not gaps:
            # Use LLM to generate intelligent, contextual explanation
            intelligent_explanation = ScoringService._generate_mission_alignment_explanation(
                grant_text, project_text, project_name, grant_name or "this grant", score
            )
            if intelligent_explanation:
                gaps.append(intelligent_explanation)
            else:
                # Fallback to template-based explanation
            project_desc_display = project_description.strip() if project_description else "not specified"
            grant_mission_display = (grant_mission if grant_mission else grant_description) or "not specified"
            grant_mission_display = grant_mission_display.strip()
            
            # Create a clear, grammatically correct explanation
            if project_desc_display != "not specified" and grant_mission_display != "not specified":
                gaps.append(f"Your project description does not align with the grant's mission. Your project focuses on: '{project_desc_display}'. The grant's mission states: '{grant_mission_display}'. These descriptions do not match, which indicates a fundamental misalignment that will likely result in rejection.")
            elif project_desc_display != "not specified":
                gaps.append(f"Your project description ('{project_desc_display}') does not align with the grant's mission, which is not clearly specified. Without a clear mission statement from the grant, alignment cannot be confidently assessed.")
            else:
                gaps.append("Your project description is not provided, so mission alignment cannot be assessed. Please provide a detailed project description to enable accurate alignment evaluation.")
        
        return MissionAlignmentResult(
            score=min(score, 10),
            strong_matches=strong_matches,
            gaps=gaps,
            confidence="high" if len(grant_keywords) > 10 and project_text else "medium",
            source="rule_based"
        )
    
    @staticmethod
    def calculate_profile_match(grant: Dict[str, Any], project: Dict[str, Any]) -> ProfileMatchResult:
        """
        Calculate Profile Match Score (0-10 or None) for paid assessments.
        
        Requires recipient data (minimum 5 recipients).
        """
        recipient_patterns = grant.get("recipient_patterns") or {}
        recipients = recipient_patterns.get("recipients") or []
        
        # Even with insufficient data, try to extract insights from available recipients
        similarities = []
        differences = []
        recipient_details = []  # Store actual recipient data for display
        
        # Extract recipient details for display
        for recipient in recipients:
            detail = {}
            if recipient.get("career_stage"):
                detail["career_stage"] = recipient.get("career_stage")
            if recipient.get("organization_type"):
                detail["organization_type"] = recipient.get("organization_type")
            if recipient.get("country"):
                detail["country"] = recipient.get("country")
            if recipient.get("education_level"):
                detail["education_level"] = recipient.get("education_level")
            if recipient.get("year"):
                detail["year"] = recipient.get("year")
            if detail:
                recipient_details.append(detail)
        
        # Check minimum threshold for scoring
        if len(recipients) < 5:
            # Still try to find patterns with limited data
            if recipients:
                # Career stage analysis
                career_stages = [r.get("career_stage") for r in recipients if r.get("career_stage")]
                if career_stages:
                    # Check both profile_metadata.career_stage and direct stage field
                    project_stage = project.get("profile_metadata", {}).get("career_stage") or project.get("stage")
                    if project_stage and project_stage in career_stages:
                        recipient_text = 'recipients' if len(recipients) > 1 else 'recipient'
                        similarities.append(f"Career stage matches: {project_stage} (found in {career_stages.count(project_stage)} of {len(recipients)} {recipient_text})")
                    elif career_stages:
                        most_common = max(set(career_stages), key=career_stages.count)
                        differences.append(f"Recipients are typically {most_common}, your stage: {project_stage or 'not specified'}")
                
                # Organization type analysis
                org_types = [r.get("organization_type") for r in recipients if r.get("organization_type")]
                if org_types:
                    project_org = project.get("organization_type")
                    if project_org and project_org in org_types:
                        similarities.append(f"Organization type matches: {project_org}")
                    elif org_types:
                        most_common = max(set(org_types), key=org_types.count)
                        differences.append(f"Typical recipient organizations: {most_common}")
                
                # Geographic analysis
                countries = [r.get("country") for r in recipients if r.get("country")]
                if countries:
                    project_country = project.get("organization_country")
                    if project_country and project_country in countries:
                        similarities.append(f"Geographic match: {project_country}")
                    elif countries:
                        unique_countries = list(set(countries))
                        country_text = ', '.join(unique_countries[:3])
                        if len(unique_countries) > 3:
                            country_text += '...'
                        differences.append(f"Recipients from: {country_text}")
                
                # Education level analysis (for single recipient, provide more detail)
                if len(recipients) == 1:
                    recipient = recipients[0]
                    education = recipient.get("education_level")
                    if education:
                        # Note: We don't have project education in standard fields, but can mention it
                        differences.append(f"Recipient education level: {education} (compare with your background)")
            
            # Update message to be more helpful
            if len(recipients) == 1:
                message = f"1 past recipient found - review details above to assess alignment (statistical analysis requires 5+ recipients)"
            else:
                message = f"Only {len(recipients)} past recipients available - cannot assess pattern match (need 5+)"
            
            return ProfileMatchResult(
                score=None,
                reason="INSUFFICIENT_DATA",
                similarities=similarities,
                differences=differences,
                confidence="low",
                recipient_count=len(recipients),
                message=message,
                recipient_details=recipient_details  # Include actual recipient data
            )
        
        score = 5  # Start neutral
        similarities = []
        differences = []
        
        # Career stage match
        career_stages = [r.get("career_stage") for r in recipients if r.get("career_stage")]
        if career_stages:
            # Check both profile_metadata.career_stage and direct stage field
            project_stage = project.get("profile_metadata", {}).get("career_stage") or project.get("stage")
            if project_stage:
                stage_match = career_stages.count(project_stage) / len(career_stages)
                if stage_match > 0.5:
                    score += 2
                    similarities.append(f"Career stage: {project_stage} ({int(stage_match*100)}% of recipients)")
                else:
                    score -= 1
                    most_common = max(set(career_stages), key=career_stages.count)
                    differences.append(f"Most recipients are {most_common}, you are {project_stage}")
        
        # Organization type match
        org_types = [r.get("organization_type") for r in recipients if r.get("organization_type")]
        if org_types:
            project_org = project.get("organization_type")
            if project_org:
                org_match = org_types.count(project_org) / len(org_types)
                if org_match > 0.4:
                    score += 2
                    similarities.append(f"Organization type: {project_org} ({int(org_match*100)}% match)")
                else:
                    most_common = max(set(org_types), key=org_types.count)
                    differences.append(f"Typical recipients are from {most_common} organizations")
        
        # Geographic match
        countries = [r.get("country") for r in recipients if r.get("country")]
        if countries:
            project_country = project.get("organization_country")
            if project_country:
                geo_match = project_country in countries
                if geo_match:
                    score += 1
                    similarities.append(f"Geography: {project_country}")
                else:
                    match_pct = countries.count(project_country) / len(countries) if project_country in countries else 0
                    differences.append(f"{int(match_pct*100)}% of recipients from your region")
        
        # Determine confidence
        if len(recipients) > 30:
            confidence = "high"
        elif len(recipients) > 15:
            confidence = "moderate"
        else:
            confidence = "low"
        
        # Extract recipient details for display (even when we have enough data)
        recipient_details = []
        for recipient in recipients:
            detail = {}
            if recipient.get("career_stage"):
                detail["career_stage"] = recipient.get("career_stage")
            if recipient.get("organization_type"):
                detail["organization_type"] = recipient.get("organization_type")
            if recipient.get("country"):
                detail["country"] = recipient.get("country")
            if recipient.get("education_level"):
                detail["education_level"] = recipient.get("education_level")
            if recipient.get("year"):
                detail["year"] = recipient.get("year")
            if detail:
                recipient_details.append(detail)
        
        return ProfileMatchResult(
            score=max(0, min(score, 10)),
            reason=None,
            similarities=similarities,
            differences=differences,
            confidence=confidence,
            recipient_count=len(recipients),
            message=f"Based on {len(recipients)} past recipient profiles",
            recipient_details=recipient_details
        )
    
    @staticmethod
    def assess_funding_fit(grant: Dict[str, Any], project: Dict[str, Any]) -> FundingFitResult:
        """
        Assess Funding Fit (ALIGNED/PARTIAL/MISMATCHED) for paid assessments.
        
        Compares project funding needs to grant award structure.
        """
        need_amount = project.get("funding_need_amount")  # In cents
        need_currency = project.get("funding_need_currency", "USD")
        need_purpose = (project.get("funding_need") or "").lower()
        
        # Check if it's a cash grant
        award_structure = (grant.get("award_structure") or "").lower()
        is_cash_grant = "grant" in award_structure and "fellowship" not in award_structure
        
        # If non-cash and user needs cash, it's a mismatch
        if not is_cash_grant and ("salary" in need_purpose or "equipment" in need_purpose or "staff" in need_purpose):
            return FundingFitResult(
                fit="MISMATCHED",
                severity="CRITICAL",
                message=f"You need funding for {need_purpose}, but this is a {grant.get('award_structure', 'non-cash program')} providing no direct funding",
                recommendation="Search for direct funding grants instead",
                confidence="high"
            )
        
        # Check award amount
        award_amount_str = grant.get("award_amount")
        
        # Debug logging to help diagnose issues
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Funding fit assessment - grant award_amount: {award_amount_str}, type: {type(award_amount_str)}")
        logger.debug(f"Funding fit assessment - project funding_need_amount: {project.get('funding_need_amount')}, currency: {project.get('funding_need_currency')}")
        
        if not award_amount_str or str(award_amount_str).strip() == "":
            return FundingFitResult(
                fit="UNCERTAIN",
                severity="MODERATE",
                message="Grant amount not disclosed - cannot assess funding fit",
                recommendation="Contact funder to confirm award range",
                confidence="low"
            )
        
        # Try to parse award amount with currency detection
        try:
            # Extract currency from award string (look for currency codes or symbols)
            award_str_lower = str(award_amount_str).lower().strip()
            grant_currency = None
            
            # Check for currency codes (check before removing symbols)
            if 'ghs' in award_str_lower or 'cedi' in award_str_lower or 'cedis' in award_str_lower:
                grant_currency = 'GHS'
            elif 'usd' in award_str_lower or '$' in award_str_lower or 'dollar' in award_str_lower:
                grant_currency = 'USD'
            elif 'eur' in award_str_lower or '€' in award_str_lower or 'euro' in award_str_lower:
                grant_currency = 'EUR'
            elif 'gbp' in award_str_lower or '£' in award_str_lower or 'pound' in award_str_lower:
                grant_currency = 'GBP'
            
            # Extract numbers from award string - handle $50,000 format
            # Remove currency symbols and commas, then extract numbers
            cleaned_str = str(award_amount_str).replace(',', '').replace('$', '').replace('€', '').replace('£', '').strip()
            numbers = re.findall(r'\d+', cleaned_str)
            if not numbers:
                # No numbers found in award amount string
                return FundingFitResult(
                    fit="UNCERTAIN",
                    severity="MODERATE",
                    message=f"Cannot extract numeric amount from grant award '{award_amount_str}'. Please verify the amount format (e.g., '$50,000' or '50000 USD').",
                    recommendation="Contact funder for specific amount or verify grant amount format",
                    confidence="low"
                )
            
            grant_amount_base = int(numbers[0])  # Base amount (not in cents yet)
            
            # Convert grant amount to cents based on detected currency
            if grant_currency == 'GHS':
                grant_amount_cents = grant_amount_base * 100  # GHS to pesewas
            elif grant_currency == 'USD':
                grant_amount_cents = grant_amount_base * 100  # USD to cents
            elif grant_currency == 'EUR':
                grant_amount_cents = grant_amount_base * 100  # EUR to cents
            elif grant_currency == 'GBP':
                grant_amount_cents = grant_amount_base * 100  # GBP to pence
            else:
                # Default to USD if currency not detected (backward compatibility)
                grant_currency = 'USD'
                grant_amount_cents = grant_amount_base * 100
            
            # If project has no funding need amount, we can still show the grant amount
            if not need_amount:
                # Project doesn't have funding need specified - show grant amount only
                grant_display = f"{grant_amount_base:,} {grant_currency}"
                return FundingFitResult(
                    fit="UNCERTAIN",
                    severity="LOW",
                    message=f"Grant amount is {grant_display}, but your project funding need is not specified. Cannot assess fit without project funding requirement.",
                    recommendation="Specify your project funding need to get accurate funding fit assessment",
                    confidence="low"
                )
            
            if need_amount:
                # Convert both amounts to a common currency for comparison
                # Use approximate exchange rates (update these periodically)
                # As of 2025: 1 USD ≈ 13.5 GHS, 1 EUR ≈ 1.1 USD, 1 GBP ≈ 1.25 USD
                EXCHANGE_RATES = {
                    'USD': {'GHS': 13.5, 'EUR': 0.91, 'GBP': 0.80},
                    'GHS': {'USD': 0.074, 'EUR': 0.067, 'GBP': 0.059},
                    'EUR': {'USD': 1.10, 'GHS': 14.85, 'GBP': 0.88},
                    'GBP': {'USD': 1.25, 'GHS': 16.88, 'EUR': 1.14}
                }
                
                # Convert grant amount to project's currency
                if grant_currency != need_currency:
                    # Direct conversion if available
                    if grant_currency in EXCHANGE_RATES and need_currency in EXCHANGE_RATES[grant_currency]:
                        rate = EXCHANGE_RATES[grant_currency][need_currency]
                        grant_amount_in_need_currency = grant_amount_cents * rate
                    else:
                        # Convert via USD as intermediary
                        # Step 1: Convert grant currency to USD
                        if grant_currency == 'USD':
                            grant_amount_usd_cents = grant_amount_cents
                        elif grant_currency in EXCHANGE_RATES and 'USD' in EXCHANGE_RATES[grant_currency]:
                            # Convert from grant currency to USD
                            grant_amount_usd_cents = grant_amount_cents * EXCHANGE_RATES[grant_currency]['USD']
                        else:
                            # Can't convert - assume same value (fallback)
                            grant_amount_usd_cents = grant_amount_cents
                        
                        # Step 2: Convert USD to need currency
                        if need_currency == 'USD':
                            grant_amount_in_need_currency = grant_amount_usd_cents
                        elif 'USD' in EXCHANGE_RATES and need_currency in EXCHANGE_RATES['USD']:
                            # Convert from USD to need currency
                            grant_amount_in_need_currency = grant_amount_usd_cents * EXCHANGE_RATES['USD'][need_currency]
                        else:
                            # Can't convert - use USD value (fallback)
                            grant_amount_in_need_currency = grant_amount_usd_cents
                else:
                    # Same currency - no conversion needed
                    grant_amount_in_need_currency = grant_amount_cents
                
                percentage_met = (grant_amount_in_need_currency / need_amount) * 100
                
                # Format amounts for display
                grant_display = f"{grant_amount_base:,} {grant_currency}"
                need_display = f"{need_amount/100:,.0f} {need_currency}"
                
                if percentage_met >= 80:
                    return FundingFitResult(
                        fit="ALIGNED",
                        severity=None,
                        message=f"Grant amount ({grant_display}) covers {int(percentage_met)}% of your need ({need_display})",
                        recommendation="Strong funding fit",
                        confidence="high"
                    )
                elif percentage_met >= 40:
                    return FundingFitResult(
                        fit="PARTIAL",
                        severity="MODERATE",
                        message=f"Grant ({grant_display}) covers {int(percentage_met)}% of your {need_display} need",
                        recommendation="Consider as part of a funding portfolio",
                        confidence="high"
                    )
                else:
                    return FundingFitResult(
                        fit="INSUFFICIENT",
                        severity="HIGH",
                        message=f"Grant amount ({grant_display}) only covers {int(percentage_met)}% of your {need_display} need",
                        recommendation="Look for larger funding opportunities",
                        confidence="high"
                    )
        except (ValueError, ZeroDivisionError, AttributeError) as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error parsing grant amount '{award_amount_str}': {e}", exc_info=True)
            return FundingFitResult(
                fit="UNCERTAIN",
                severity="MODERATE",
                message=f"Cannot parse grant amount '{award_amount_str}' for comparison. Please verify the amount format.",
                recommendation="Contact funder for specific amount or check grant amount format",
                confidence="low"
            )
        except Exception as e:
            # Catch any other unexpected errors
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error parsing grant amount '{award_amount_str}': {e}", exc_info=True)
            return FundingFitResult(
                fit="UNCERTAIN",
                severity="MODERATE",
                message=f"Error processing grant amount: {str(e)}",
                recommendation="Contact funder for specific amount",
                confidence="low"
            )
        
        # If we get here, parsing failed but no exception was raised (shouldn't happen)
        return FundingFitResult(
            fit="UNCERTAIN",
            severity="MODERATE",
            message=f"Cannot parse grant amount '{award_amount_str}' - no numbers found in amount string",
            recommendation="Contact funder for specific amount or verify grant amount format",
            confidence="low"
        )
    
    @staticmethod
    def assess_effort_reward(grant: Dict[str, Any], project: Dict[str, Any], 
                            mission_score: int, profile_score: Optional[int]) -> EffortRewardResult:
        """
        Assess Effort-Reward Ratio (WORTH_IT/MAYBE/SKIP) for paid assessments.
        """
        # Get access barrier to estimate hours
        access_barrier = ScoringService.assess_access_barrier(grant)
        # Parse estimated hours (simplified - takes upper bound)
        hours_str = access_barrier.estimated_hours.replace('+', '').split('-')[-1]
        try:
            estimated_hours = int(hours_str)
        except ValueError:
            estimated_hours = 50  # Default
        
        # Estimate potential value
        award_amount_str = grant.get("award_amount")
        value = 0
        if award_amount_str:
            numbers = re.findall(r'[\d,]+', str(award_amount_str).replace(',', ''))
            if numbers:
                value = int(numbers[0]) * 100  # Convert to cents
        else:
            # Estimate for non-cash fellowships
            award_structure = (grant.get("award_structure") or "").lower()
            if "fellowship" in award_structure:
                value = 1500000  # $15,000 equivalent in cents
        
        # Calculate fit multiplier
        profile_adj = profile_score if profile_score else 5
        fit_multiplier = ((mission_score + profile_adj) / 2) / 10
        adjusted_value = int(value * fit_multiplier)
        
        # Calculate value per hour
        value_per_hour = adjusted_value // estimated_hours if estimated_hours > 0 else 0
        
        # Determine assessment
        if value_per_hour > 50000 and fit_multiplier > 0.6:  # $500/hour in cents
            assessment = "WORTH_IT"
            reasoning = f"High value with strong fit. Estimated {estimated_hours} hours is a good investment."
        elif value_per_hour > 20000 or fit_multiplier > 0.7:  # $200/hour in cents
            assessment = "MAYBE"
            reasoning = "Moderate value-to-effort ratio. Consider your capacity and other deadlines."
        else:
            assessment = "SKIP"
            reasoning = "Low value-to-effort ratio given your fit. Better opportunities likely exist."
        
        # Opportunity cost
        if estimated_hours > 60:
            opp_cost = "HIGH"
        elif estimated_hours > 40:
            opp_cost = "MODERATE"
        else:
            opp_cost = "LOW"
        
        return EffortRewardResult(
            assessment=assessment,
            estimated_hours=estimated_hours,
            potential_value=value,
            value_per_hour=value_per_hour,
            reasoning=reasoning,
            opportunity_cost=opp_cost,
            confidence="medium"
        )
    
    @staticmethod
    def estimate_success_probability(grant: Dict[str, Any], mission_score: int, 
                                   profile_score: Optional[int], competition: CompetitionResult) -> SuccessProbabilityResult:
        """
        Estimate Success Probability Range for paid assessments.
        """
        # Get base rate from competition stats
        base_rate = None
        if competition.acceptance_rate:
            try:
                base_rate = float(competition.acceptance_rate.replace('~', '').replace('%', ''))
            except ValueError:
                pass
        
        if base_rate is None:
            return SuccessProbabilityResult(
                range=None,
                base_rate=None,
                explanation="Cannot estimate success probability - no competition data available",
                confidence="unknown",
                source=None
            )
        
        # Adjust based on fit scores
        adjusted_rate = base_rate
        
        # Mission alignment adjustment
        if mission_score >= 8:
            adjusted_rate *= 1.3
        elif mission_score >= 6:
            adjusted_rate *= 1.1
        elif mission_score < 4:
            adjusted_rate *= 0.7
        
        # Profile match adjustment
        if profile_score:
            if profile_score >= 8:
                adjusted_rate *= 1.2
            elif profile_score < 5:
                adjusted_rate *= 0.8
        
        # Cap at reasonable maximum (50% base, so upper bound can be 60%)
        adjusted_rate = min(adjusted_rate, 50)
        
        lower = max(int(adjusted_rate * 0.8), 1)
        upper = min(int(adjusted_rate * 1.2), 60)  # Cap upper bound at 60%
        
        return SuccessProbabilityResult(
            range=f"{lower}-{upper}%",
            base_rate=f"{int(base_rate)}%",
            explanation=f"Base rate: {int(base_rate)}% | Your fit profile adjusts this {'upward' if adjusted_rate > base_rate else 'downward'}",
            confidence=competition.confidence,
            source=competition.source
        )
    
    @staticmethod
    def calculate_paid_composite(mission: int, profile: Optional[int], funding_fit: str, 
                                effort_reward: str) -> int:
        """
        Calculate composite score for paid tier assessments.
        
        Formula: Weighted average of fit dimensions.
        """
        # Convert profile score (use 5 if None)
        profile_adj = profile if profile is not None else 5
        
        # Convert funding fit to score
        funding_score = 10 if funding_fit == "ALIGNED" else (6 if funding_fit == "PARTIAL" else 2)
        
        # Convert effort-reward to score
        effort_score = 10 if effort_reward == "WORTH_IT" else (6 if effort_reward == "MAYBE" else 2)
        
        # Weighted formula
        composite = (
            mission * 0.30 +        # Mission alignment is most important
            profile_adj * 0.25 +     # Profile match matters
            funding_score * 0.25 +   # Funding fit is critical
            effort_score * 0.20      # Effort-reward ratio
        )
        
        return int(round(composite))
