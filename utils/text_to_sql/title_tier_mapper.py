"""
Title tier mapping utility for matching titles by tier.
"""

from typing import List, Optional

from utils.common.config_loader import load_config
from utils.common.logger import get_logger

logger = get_logger(__name__)


class TitleTierMapper:
    """Map title keywords to tier-based SQL conditions."""
    
    def __init__(self, config_path: str = None):
        """Initialize mapper with configuration."""
        self.config = load_config(config_path)
        
        self.title_tiers = self.config.get('title_tiers', {})
        # Load keyword mappings from config (no duplication)
        tier_keywords = self.title_tiers.get('tier_keywords', {})
        self.tier_i_keywords = tier_keywords.get('tier_i', [])
        self.tier_ii_keywords = tier_keywords.get('tier_ii', [])
        self.tier_iii_keywords = tier_keywords.get('tier_iii', [])
    
    def get_tier_titles(self, tier: str) -> List[str]:
        """Get all titles for a specific tier."""
        # Exclude tier_keywords from the titles list
        if tier == 'tier_keywords':
            return []
        return self.title_tiers.get(tier, [])
    
    def match_title_to_tier(self, title_keyword: str) -> Optional[str]:
        """
        Match a title keyword to a tier.
        
        Args:
            title_keyword: Title keyword from user (e.g., "owner", "CEO", "director")
            
        Returns:
            Tier name ("tier_i", "tier_ii", "tier_iii") or None
        """
        logger.debug(f"Matching title keyword to tier: {title_keyword}")
        if not title_keyword:
            return None
        
        normalized = title_keyword.lower().strip()
        
        # Check Tier I keywords
        for keyword in self.tier_i_keywords:
            if keyword in normalized or normalized in keyword:
                logger.info(f"Matched '{title_keyword}' to tier_i (keyword: {keyword})")
                return "tier_i"
        
        # Check Tier II keywords
        for keyword in self.tier_ii_keywords:
            if keyword in normalized or normalized in keyword:
                logger.info(f"Matched '{title_keyword}' to tier_ii (keyword: {keyword})")
                return "tier_ii"
        
        # Check Tier III keywords
        for keyword in self.tier_iii_keywords:
            if keyword in normalized or normalized in keyword:
                logger.info(f"Matched '{title_keyword}' to tier_iii (keyword: {keyword})")
                return "tier_iii"
        
        logger.debug(f"No tier match found for title: {title_keyword}")
        return None
    
    def generate_title_sql_condition(self, title_keyword: str) -> Optional[str]:
        """
        Generate SQL WHERE condition for title matching using tier system.
        Returns tier-based condition if match found, None otherwise (let LLM decide).
        
        Args:
            title_keyword: Title keyword from user (e.g., "owner", "CEO")
            
        Returns:
            SQL condition string (e.g., "title_tier = 'tier_i'") or None if no match
        """
        logger.debug(f"Generating SQL condition for title: {title_keyword}")
        if not title_keyword:
            return None
        
        tier = self.match_title_to_tier(title_keyword)
        
        if tier:
            # Use title_tier column for efficient filtering
            result = f"title_tier = '{tier}'"
            logger.info(f"Generated tier-based SQL condition using title_tier column: {result}")
            return result
        
        # No tier match - return None to let LLM classify
        logger.debug(f"No tier match found for '{title_keyword}', LLM will classify")
        return None


def get_title_tier_mapper() -> TitleTierMapper:
    """Get singleton instance of TitleTierMapper."""
    if not hasattr(get_title_tier_mapper, '_instance'):
        get_title_tier_mapper._instance = TitleTierMapper()
    return get_title_tier_mapper._instance

