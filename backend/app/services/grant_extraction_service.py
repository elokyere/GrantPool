"""
Grant extraction service using web scraping and Claude API.

This service scrapes grant pages and uses Claude to extract structured
grant information from the page content.
"""

import json
import re
from typing import Dict, Optional
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from anthropic import Anthropic
from app.core.config import settings
from app.core.sanitization import validate_url_security


class GrantExtractionService:
    """Service for extracting grant information from URLs using Claude API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the extraction service."""
        api_key = api_key or settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable."
            )
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-3-haiku-20240307"  # Using Haiku for cost efficiency
    
    def extract_grant_from_url(self, url: str) -> Dict:
        """
        Extract grant information from a URL.
        
        Steps:
        1. Validate URL security (SSRF protection)
        2. Scrape the web page content (raw_content - immutable source of record)
        3. Clean and structure the content
        4. Use Claude to extract grant details
        5. Return structured grant data including raw data
        
        Args:
            url: The grant page URL
            
        Returns:
            Dictionary with extracted grant information including:
            - raw_title: Raw title from source (immutable)
            - raw_content: Raw scraped content (immutable)
            - All extracted/structured fields (name, description, etc.)
            
        Raises:
            ValueError: If URL is invalid or dangerous
        """
        # Step 0: Validate URL security before processing
        is_valid, error_msg = validate_url_security(url)
        if not is_valid:
            raise ValueError(f"Invalid or dangerous URL: {error_msg}")
        
        # Step 1: Scrape the page (this is our raw_content - immutable source of record)
        raw_content = self._scrape_url(url)
        
        # Step 2: Extract grant information using Claude
        grant_data = self._extract_with_claude(url, raw_content)
        
        # Step 3: Extract recipient patterns and competition stats (if available)
        try:
            recipient_patterns = self._extract_recipient_patterns(url, raw_content, grant_data.get('name'))
            if recipient_patterns:
                grant_data['recipient_patterns'] = recipient_patterns
        except Exception as e:
            # Non-critical - continue without recipient patterns
            # Log but don't fail the extraction
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to extract recipient patterns: {str(e)}")
        
        # Step 4: Store raw data (immutable source of record)
        # raw_title is the extracted name before any sanitization/normalization
        raw_title = grant_data.get('name') or None
        grant_data['raw_title'] = raw_title
        grant_data['raw_content'] = raw_content  # Store full raw scraped content
        
        return grant_data
    
    def _scrape_url(self, url: str, timeout: int = 30) -> str:
        """
        Scrape content from a URL.
        
        Args:
            url: The URL to scrape
            timeout: Request timeout in seconds
            
        Returns:
            Cleaned text content from the page
        """
        try:
            # Set headers to mimic a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            # Additional SSRF protection: validate URL again before making request
            is_valid, error_msg = validate_url_security(url)
            if not is_valid:
                raise ValueError(f"Cannot scrape URL: {error_msg}")
            
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                
                # Check if redirect led to a private IP
                if response.url:
                    final_url = str(response.url)
                    is_valid_final, error_msg_final = validate_url_security(final_url)
                    if not is_valid_final:
                        raise ValueError(f"Redirect led to dangerous URL: {error_msg_final}")
                
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                # Extract text content
                text = soup.get_text()
                
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
                # Limit content length to avoid token limits (keep first 50k chars)
                if len(text) > 50000:
                    text = text[:50000] + "\n\n[Content truncated...]"
                
                if not text or len(text.strip()) < 50:
                    raise ValueError(f"Page content too short or empty. The URL might not contain grant information.")
                
                return text
                
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 404:
                raise ValueError(f"Grant page not found (404). Please check the URL and try again.")
            elif status_code == 403:
                raise ValueError(f"Access denied (403). The grant page may require authentication or block automated access.")
            elif status_code >= 500:
                raise ValueError(f"Server error ({status_code}) when fetching URL. The grant website may be temporarily unavailable.")
            else:
                raise ValueError(f"HTTP error {status_code} when fetching URL: {e.response.text[:200]}")
        except httpx.TimeoutException:
            raise ValueError(f"Request to {url} timed out after {timeout} seconds. The website may be slow or unreachable.")
        except httpx.RequestError as e:
            raise ValueError(f"Failed to fetch URL. Please check your internet connection and the URL: {str(e)}")
        except ValueError:
            # Re-raise ValueError as-is (from validation or content checks)
            raise
        except Exception as e:
            raise ValueError(f"Unexpected error scraping URL: {str(e)}")
    
    def _extract_with_claude(self, url: str, page_content: str) -> Dict:
        """
        Use Claude API to extract structured grant information from page content.
        
        Args:
            url: The source URL
            page_content: The scraped page content
            
        Returns:
            Dictionary with extracted grant fields
        """
        system_prompt = """You are a grant information extraction assistant. Extract structured grant information from web page content.

Extract the following information if available:
- name: Grant name/title
- description: Grant description/overview
- mission: Grant mission/purpose
- deadline: Application deadline (format as text, e.g., "March 15, 2024" or "Rolling")
- decision_date: When decisions are made (format as text)
- award_amount: Award amount/range (e.g., "$10,000 - $50,000" or "Up to $25,000")
- award_structure: How funds are disbursed (e.g., "One-time payment", "Milestone-based")
- eligibility: Eligibility requirements
- preferred_applicants: Preferred applicant types
- application_requirements: List of required materials/documents
- reporting_requirements: Reporting obligations
- restrictions: Any restrictions on use of funds

Return ONLY valid JSON in this format:
{
  "name": "string or null",
  "description": "string or null",
  "mission": "string or null",
  "deadline": "string or null",
  "decision_date": "string or null",
  "award_amount": "string or null",
  "award_structure": "string or null",
  "eligibility": "string or null",
  "preferred_applicants": "string or null",
  "application_requirements": ["string"] or null,
  "reporting_requirements": "string or null",
  "restrictions": ["string"] or null
}

If information is not found, use null. Do not guess or invent information. Be accurate and only extract what is clearly stated."""

        user_message = f"""Extract grant information from this web page:

URL: {url}

Page Content:
{page_content[:40000]}  # Limit to avoid token limits

Extract all available grant information and return as JSON."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
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
                grant_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                # Try to extract JSON from text if wrapped
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    grant_data = json.loads(json_match.group())
                else:
                    raise ValueError(f"Failed to parse Claude response as JSON: {e}")
            
            # Ensure source_url is included
            grant_data['source_url'] = url
            
            # Validate and clean the data
            return self._validate_extracted_data(grant_data)
            
        except Exception as e:
            error_msg = str(e)
            # Provide more specific error messages
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower() or "401" in error_msg:
                raise ValueError(f"Anthropic API authentication failed. Please check your ANTHROPIC_API_KEY: {error_msg}")
            elif "rate limit" in error_msg.lower() or "429" in error_msg:
                raise ValueError(f"Anthropic API rate limit exceeded. Please try again later: {error_msg}")
            elif "timeout" in error_msg.lower():
                raise ValueError(f"Request to Claude API timed out. Please try again: {error_msg}")
            else:
                raise ValueError(f"Failed to extract grant information with Claude: {error_msg}")
    
    def _validate_extracted_data(self, data: Dict) -> Dict:
        """
        Validate and clean extracted grant data.
        
        Args:
            data: Raw extracted data
            
        Returns:
            Validated and cleaned data
        """
        # Ensure all expected fields exist
        validated = {
            'name': data.get('name') or None,
            'description': data.get('description') or None,
            'mission': data.get('mission') or None,
            'deadline': data.get('deadline') or None,
            'decision_date': data.get('decision_date') or None,
            'award_amount': data.get('award_amount') or None,
            'award_structure': data.get('award_structure') or None,
            'eligibility': data.get('eligibility') or None,
            'preferred_applicants': data.get('preferred_applicants') or None,
            'application_requirements': data.get('application_requirements') or [],
            'reporting_requirements': data.get('reporting_requirements') or None,
            'restrictions': data.get('restrictions') or [],
            'source_url': data.get('source_url') or None,
        }
        
        # Ensure name exists (use URL as fallback)
        if not validated['name']:
            try:
                parsed = urlparse(validated['source_url'] or '')
                validated['name'] = f"{parsed.netloc}{parsed.path}".replace('/', ' ').strip()[:100]
                if not validated['name']:
                    validated['name'] = "Grant from URL"
            except:
                validated['name'] = "Grant from URL"
        
        # Clean lists - ensure they're lists of strings
        if validated['application_requirements'] and not isinstance(validated['application_requirements'], list):
            validated['application_requirements'] = [str(validated['application_requirements'])]
        
        if validated['restrictions'] and not isinstance(validated['restrictions'], list):
            validated['restrictions'] = [str(validated['restrictions'])]
        
        return validated
    
    def _extract_recipient_patterns(self, url: str, page_content: str, grant_name: Optional[str] = None) -> Optional[Dict]:
        """
        Extract recipient patterns and competition statistics from grant page.
        
        This method attempts to extract:
        - Past recipient profiles (career stage, organization type, country, etc.)
        - Competition statistics (applications received, awards made, acceptance rate)
        
        All extracted data is tagged with source ("llm") and confidence levels.
        
        Args:
            url: The source URL
            page_content: The scraped page content
            grant_name: Optional grant name for context
            
        Returns:
            Dictionary with recipient_patterns structure or None if no data found
        """
        system_prompt = """You are a grant data extraction assistant. Extract recipient patterns and competition statistics from grant page content.

Extract the following information if clearly available:

1. PAST RECIPIENTS (if listed):
   - Extract individual recipient profiles with:
     * career_stage (e.g., "Early-career", "Mid-career", "Senior")
     * organization_type (e.g., "NGO", "University", "Government")
     * country (ISO 2-letter code if possible, or country name)
     * education_level (if mentioned)
     * year (award year if mentioned)
   - Tag each field with confidence: "high" (explicitly stated), "medium" (inferred from context), "low" (weak inference)
   - Source for all recipient data: "llm"

2. COMPETITION STATISTICS (if available):
   - applications_received (number)
   - awards_made (number)
   - acceptance_rate (percentage, e.g., 12.5 for 12.5%)
   - year (the year these stats are for)
   - source: "official" if explicitly stated, "estimated" if calculated from numbers, "unknown" if not available
   - confidence: "high" if official, "medium" if estimated, "unknown" if not available
   - notes: Brief explanation of where the data came from

IMPORTANT RULES:
- Only extract data that is CLEARLY stated or can be CONFIDENTLY inferred
- If recipient data is insufficient (< 5 recipients), still extract but note low confidence
- If competition stats are not explicitly stated, set source to "unknown" and confidence to "unknown"
- Do NOT guess or invent data
- If no recipient or competition data is available, return null for that section

Return ONLY valid JSON in this format:
{
  "recipients": [
    {
      "career_stage": "string or null",
      "career_stage_confidence": "high|medium|low",
      "career_stage_source": "llm",
      "organization_type": "string or null",
      "organization_type_confidence": "high|medium|low",
      "organization_type_source": "llm",
      "country": "string or null",
      "country_confidence": "high|medium|low",
      "country_source": "llm",
      "education_level": "string or null",
      "education_level_confidence": "high|medium|low",
      "education_level_source": "llm",
      "year": integer or null,
      "locked": false
    }
  ] or null,
  "competition_stats": {
    "applications_received": integer or null,
    "awards_made": integer or null,
    "acceptance_rate": float or null,
    "year": integer or null,
    "source": "official|estimated|unknown",
    "confidence": "high|medium|low|unknown",
    "notes": "string or null"
  } or null
}

If no recipient or competition data is found, return:
{
  "recipients": null,
  "competition_stats": null
}"""

        user_message = f"""Extract recipient patterns and competition statistics from this grant page:

Grant Name: {grant_name or 'Unknown'}
URL: {url}

Page Content:
{page_content[:40000]}  # Limit to avoid token limits

Extract recipient profiles and competition statistics if available. Return as JSON."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=3000,  # More tokens for recipient data
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
                patterns_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                # Try to extract JSON from text if wrapped
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    patterns_data = json.loads(json_match.group())
                else:
                    # If parsing fails, return None (non-critical)
                    return None
            
            # Validate structure
            if not isinstance(patterns_data, dict):
                return None
            
            # Validate recipients array
            recipients = patterns_data.get("recipients")
            if recipients is not None:
                if not isinstance(recipients, list):
                    recipients = None
                else:
                    # Validate each recipient has required fields
                    validated_recipients = []
                    for recipient in recipients:
                        if isinstance(recipient, dict):
                            # Ensure all required fields exist with defaults
                            validated_recipient = {
                                "career_stage": recipient.get("career_stage"),
                                "career_stage_confidence": recipient.get("career_stage_confidence", "low"),
                                "career_stage_source": recipient.get("career_stage_source", "llm"),
                                "organization_type": recipient.get("organization_type"),
                                "organization_type_confidence": recipient.get("organization_type_confidence", "low"),
                                "organization_type_source": recipient.get("organization_type_source", "llm"),
                                "country": recipient.get("country"),
                                "country_confidence": recipient.get("country_confidence", "low"),
                                "country_source": recipient.get("country_source", "llm"),
                                "education_level": recipient.get("education_level"),
                                "education_level_confidence": recipient.get("education_level_confidence", "low"),
                                "education_level_source": recipient.get("education_level_source", "llm"),
                                "year": recipient.get("year"),
                                "locked": False
                            }
                            validated_recipients.append(validated_recipient)
                    recipients = validated_recipients if validated_recipients else None
            
            # Validate competition_stats
            competition_stats = patterns_data.get("competition_stats")
            if competition_stats is not None:
                if not isinstance(competition_stats, dict):
                    competition_stats = None
                else:
                    # Ensure required fields
                    validated_stats = {
                        "applications_received": competition_stats.get("applications_received"),
                        "awards_made": competition_stats.get("awards_made"),
                        "acceptance_rate": competition_stats.get("acceptance_rate"),
                        "year": competition_stats.get("year"),
                        "source": competition_stats.get("source", "unknown"),
                        "confidence": competition_stats.get("confidence", "unknown"),
                        "notes": competition_stats.get("notes")
                    }
                    # Calculate acceptance_rate if we have applications and awards
                    if validated_stats["applications_received"] and validated_stats["awards_made"]:
                        if not validated_stats["acceptance_rate"]:
                            try:
                                rate = (validated_stats["awards_made"] / validated_stats["applications_received"]) * 100
                                validated_stats["acceptance_rate"] = round(rate, 2)
                                if validated_stats["source"] == "unknown":
                                    validated_stats["source"] = "estimated"
                                    validated_stats["confidence"] = "medium"
                                    validated_stats["notes"] = "Calculated from applications and awards numbers"
                            except (ZeroDivisionError, TypeError):
                                pass
                    competition_stats = validated_stats
            
            # Return None if both are null
            if recipients is None and competition_stats is None:
                return None
            
            return {
                "recipients": recipients,
                "competition_stats": competition_stats
            }
            
        except Exception as e:
            # Non-critical - log and return None
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error extracting recipient patterns: {str(e)}")
            return None


