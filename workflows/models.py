"""
Pydantic models for structured output parsing.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ExtractedInfoWithMentioned(BaseModel):
    """Structured information extracted from user queries with mentioned flags for updates."""
    
    geography: Optional[str] = Field(
        None,
        description="Location (state or city) where clients are located. Can be single value (e.g., 'Phoenix') or comma-separated list for multiple locations (e.g., 'Texas, Arizona' or 'Phoenix, New York'). Extract ALL locations mentioned."
    )
    industry: Optional[str] = Field(
        None,
        description="Type of business/industry. Can be single value (e.g., 'restaurants') or comma-separated list for multiple industries (e.g., 'restaurants, hotels'). Extract ALL industries mentioned."
    )
    title: Optional[str] = Field(
        None,
        description="Decision maker role/title. Can be single value (e.g., 'owner') or comma-separated list for multiple titles (e.g., 'owner, CEO, manager'). Extract ALL titles mentioned."
    )
    employee_size: Optional[str] = Field(
        None,
        description="Company size - can be specific number (e.g., '50 employees', '100') or bucket keywords: 'micro'/'small' (1-20), 'small-medium'/'medium' (21-200), 'enterprise'/'large' (200+)"
    )
    square_footage: Optional[str] = Field(
        None,
        description="Property size - only for industries like commercial cleaning, builders, pest control. Bucket keywords: 'small' (<5,000), 'medium' (5,000-20,000), 'large' (20,000+)"
    )
    sales_volume: Optional[str] = Field(
        None,
        description="Sales volume/revenue - can be specific number (e.g., '50M', '$50M', '50 million'), range (e.g., 'below 50M', 'above 100M', 'between 10M and 50M'), or phrases like 'less than 50M', 'under 50M', 'over 100M'. Preserve the exact format as provided by user."
    )
    target_customer_type: Optional[str] = Field(
        None,
        description="Target customer type qualifier (e.g., 'startups', 'small businesses', 'enterprises', 'restaurants') mentioned in phrases like 'to startups', 'for small businesses', 'targeting enterprises'. Extract only if explicitly mentioned. This is a qualifier about who buys the service/product, not the industry itself."
    )
    geography_mentioned: bool = Field(
        False,
        description="True if geography/location is explicitly mentioned in the user's request (only relevant for update requests)"
    )
    industry_mentioned: bool = Field(
        False,
        description="True if industry is explicitly mentioned in the user's request (only relevant for update requests)"
    )
    title_mentioned: bool = Field(
        False,
        description="True if title/role is explicitly mentioned in the user's request (only relevant for update requests)"
    )
    employee_size_mentioned: bool = Field(
        False,
        description="True if employee_size/company size is explicitly mentioned in the user's request (only relevant for update requests)"
    )
    square_footage_mentioned: bool = Field(
        False,
        description="True if square_footage is explicitly mentioned in the user's request (only relevant for update requests)"
    )
    sales_volume_mentioned: bool = Field(
        False,
        description="True if sales_volume/revenue is explicitly mentioned in the user's request (only relevant for update requests)"
    )
    target_customer_type_mentioned: bool = Field(
        False,
        description="True if target_customer_type is explicitly mentioned in the user's request (only relevant for update requests)"
    )


class QuestionResponse(BaseModel):
    """Structured response for question generation."""
    
    needs_clarification: bool = Field(
        ...,
        description="True if a clarifying question is needed, False if all information is present"
    )
    question: Optional[str] = Field(
        None,
        description="The clarifying question to ask the user. Required if needs_clarification is True, None if needs_clarification is False."
    )
    
    @model_validator(mode='after')
    def validate_question_consistency(self):
        """Ensure question is provided when needs_clarification is True."""
        if self.needs_clarification and not self.question:
            raise ValueError("question is required when needs_clarification is True")
        if not self.needs_clarification and self.question:
            # If no clarification needed, question should be None
            self.question = None
        return self


class IndustrySICMapping(BaseModel):
    """
    LLM response for SIC code mapping.
    
    CRITICAL: The industry description represents what the user SELLS (service/product).
    The codes field contains SIC codes for PRIMARY BUYERS (companies that purchase the service/product),
    NOT companies that provide it.
    """
    
    industry: str = Field(
        ...,
        description="Industry description provided by the user"
    )
    codes: List[str] = Field(
        default_factory=list,
        description="List of 4-digit SIC codes (0000-8999) for PRIMARY BUYERS of the service/product. These represent companies that PURCHASE the service/product regularly, NOT companies that provide it. Empty list if industry is irrelevant/nonsensical. Return all genuinely relevant codes - include as many as are truly relevant primary buyers, but do not add extra codes just to reach a certain number. Quality over quantity.",
        max_items=50  # High limit for validation, but LLM should return only genuinely relevant codes
    )
    rationale: Optional[str] = Field(
        None,
        description="Detailed explanation of the SIC code selection with examples. Format: Start with category description (e.g., 'core outpatient / practice healthcare codes'), then list each code with its official description (e.g., 'o 8011 Offices and clinics of doctors of medicine'). Include notes about related codes if applicable. If codes are empty, explain why the industry is not valid."
    )
    
    @field_validator('codes')
    @classmethod
    def validate_codes(cls, codes: List[str]) -> List[str]:
        """Ensure codes are numeric 4-digit strings within 0000-8999. Allow empty list."""
        cleaned_codes = []
        for code in codes:
            if not code:
                continue
            digits = ''.join(filter(str.isdigit, code))
            if len(digits) != 4:
                continue
            if 0 <= int(digits) <= 8999:
                cleaned_codes.append(digits)
        # Allow empty list - will be handled by IndustryMapper
        return cleaned_codes

