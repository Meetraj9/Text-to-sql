"""
Utility functions for value checking and normalization.
"""

from typing import Optional


def is_empty_value(value: Optional[str]) -> bool:
    """
    Check if a value is empty or represents null/none.
    
    Args:
        value: Value to check
        
    Returns:
        True if value is empty/null/none, False otherwise
    """
    if not value:
        return True
    return value.lower().strip() in ["null", "none", "", "not specified"]


def get_empty_extracted_info() -> dict:
    """
    Get an empty extracted information dictionary.
    
    Returns:
        Dictionary with all fields set to None
    """
    return {
        "geography": None,
        "industry": None,
        "target_customer_type": None,
        "title": None,
        "employee_size": None,
        "square_footage": None,
        "sales_volume": None
    }

