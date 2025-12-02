"""
Industry name to SIC code mapping using LLM knowledge.
"""

from typing import Dict, List, Optional, Tuple

from workflows.models import IndustrySICMapping
from utils.text_to_sql.llm_client import create_llm_client
from utils.text_to_sql.prompt_loader import load_prompt
from utils.common.logger import get_logger

logger = get_logger(__name__)


class IndustryNotFoundError(Exception):
    """Raised when no SIC codes can be found for an industry description."""
    
    def __init__(self, industry_name: str, rationale: Optional[str] = None):
        self.industry_name = industry_name
        self.rationale = rationale or "The provided industry description is not a valid or recognizable industry."
        message = f"We don't have data regarding the industry '{industry_name}'. {self.rationale}"
        super().__init__(message)


class IndustryMapper:
    """Map industry descriptions to 4-digit SIC codes via LLM."""
    
    def __init__(self):
        """Initialize mapper with LLM client and prompt."""
        # Use temperature from config/env (no hardcoded values)
        self.llm = create_llm_client()
        self.structured_llm = self.llm.with_structured_output(IndustrySICMapping)
        self.prompt_template = load_prompt("industry_sic_prompt.yaml")
        self.cache: Dict[str, IndustrySICMapping] = {}
    
    def _get_mapping(self, industry_name: str, exclusion_context: Optional[str] = None) -> Optional[IndustrySICMapping]:
        """Retrieve mapping from cache or LLM."""
        if not industry_name:
            logger.debug("Industry name is empty")
            return None
        
        normalized = industry_name.strip().lower()
        if not normalized:
            logger.debug("Industry name normalized to empty string")
            return None
        
        # Include exclusion context in cache key if provided
        cache_key = normalized
        if exclusion_context:
            cache_key = f"{normalized}::exclude::{exclusion_context.strip().lower()}"
        
        if cache_key in self.cache:
            logger.debug(f"Returning cached SIC mapping for '{industry_name}'")
            return self.cache[cache_key]
        
        # Build prompt with exclusion context if provided
        exclusion_text = ""
        if exclusion_context:
            exclusion_text = f"\nEXCLUSION CONTEXT (IMPORTANT): {exclusion_context}\nPlease exclude any SIC codes that match the excluded categories mentioned above."
        
        prompt = self.prompt_template.format(
            industry_name=industry_name,
            exclusion_context=exclusion_text
        )
        try:
            logger.debug(f"Invoking LLM for SIC mapping: {industry_name}")
            response: IndustrySICMapping = self.structured_llm.invoke(prompt)
            
            # Check if LLM returned empty codes (industry is irrelevant)
            if not response.codes:
                logger.warning(f"LLM returned no SIC codes for industry: {industry_name}")
                raise IndustryNotFoundError(
                    industry_name=industry_name,
                    rationale=response.rationale
                )
            
            logger.info(f"LLM mapped '{industry_name}' to SIC codes: {response.codes}")
            self.cache[cache_key] = response
            return response
        except IndustryNotFoundError:
            # Re-raise our custom exception (with rationale)
            raise
        except Exception as e:
            logger.error(f"Failed to map industry '{industry_name}' to SIC codes: {e}", exc_info=True)
            raise IndustryNotFoundError(
                industry_name=industry_name,
                rationale="Please provide a more specific or standard industry name."
            )
    
    def map_industry_to_sic(self, industry_name: str) -> Optional[List[str]]:
        """
        Map industry name to list of 4-digit SIC codes (0000-8999).
        """
        mapping = self._get_mapping(industry_name)
        return mapping.codes if mapping else None
    
    def get_sic_codes_for_query(self, industry_name: str, exclusion_context: Optional[str] = None) -> Tuple[str, IndustrySICMapping]:
        """
        Get SIC codes formatted for SQL IN clause along with mapping details.
        
        Args:
            industry_name: Industry description
            exclusion_context: Optional context about what to exclude (e.g., "filter out recreation clubs")
            
        Raises:
            IndustryNotFoundError: If no SIC codes can be found for the industry
        """
        logger.debug(f"Formatting SIC codes for SQL query: {industry_name}")
        if exclusion_context:
            logger.debug(f"Exclusion context provided: {exclusion_context}")
        mapping = self._get_mapping(industry_name, exclusion_context)
        if not mapping:
            raise IndustryNotFoundError(
                industry_name=industry_name,
                rationale="Please provide a more specific or standard industry name."
            )
        
        result = ", ".join([f"'{code}'" for code in mapping.codes])
        logger.debug(f"Formatted SIC codes for SQL: {result}")
        return result, mapping


def get_industry_mapper() -> IndustryMapper:
    """Get singleton instance of IndustryMapper."""
    if not hasattr(get_industry_mapper, '_instance'):
        get_industry_mapper._instance = IndustryMapper()
    return get_industry_mapper._instance

