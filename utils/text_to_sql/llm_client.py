"""
Utility for creating LLM client instances.
"""

from langchain_openai import ChatOpenAI
from typing import Optional

from utils.common.config import get_llm_settings
from utils.common.logger import get_logger

logger = get_logger(__name__)


def create_llm_client(
    model: Optional[str] = None,
    temperature: Optional[float] = None
) -> ChatOpenAI:
    """
    Create and return a configured ChatOpenAI client.
    
    Args:
        model: Model name (defaults to LLM_MODEL from config/env)
        temperature: Temperature setting (defaults to LLM_TEMPERATURE from config/env)
        
    Returns:
        Configured ChatOpenAI instance
        
    Raises:
        ValueError: If OpenAI API key is not set
    """
    llm_settings = get_llm_settings()
    
    if not llm_settings.api_key:
        logger.error("LLM_API_KEY not set in environment variables")
        raise ValueError("LLM_API_KEY not set in environment variables")
    
    resolved_model = model or llm_settings.model
    resolved_temperature = (
        temperature if temperature is not None else llm_settings.temperature
    )
    
    return ChatOpenAI(
        model=resolved_model,
        temperature=resolved_temperature,
        api_key=llm_settings.api_key
    )

