"""
Shared resources and utilities for workflow nodes.
"""

from utils.text_to_sql.llm_client import create_llm_client
from utils.text_to_sql.prompt_loader import load_prompt
from utils.text_to_sql.industry_mapper import get_industry_mapper as _create_industry_mapper
from utils.text_to_sql.title_tier_mapper import get_title_tier_mapper as _create_title_tier_mapper
from utils.text_to_sql.sql_validator import SQLValidator
from utils.common.db import get_info_sql_database_tool

# Initialize shared resources (singletons)
_llm = None
_extraction_prompt_template = None
_question_prompt_template = None
_sql_prompt_template = None
_industry_mapper = None
_title_tier_mapper = None
_sql_validator = None
_info_tool = None


def get_llm():
    """Get or create LLM client (singleton)."""
    global _llm
    if _llm is None:
        _llm = create_llm_client()
    return _llm


def get_extraction_prompt():
    """Get extraction prompt template."""
    global _extraction_prompt_template
    if _extraction_prompt_template is None:
        _extraction_prompt_template = load_prompt("information_extraction_prompt.yaml")
    return _extraction_prompt_template


def get_question_prompt():
    """Get question generation prompt template."""
    global _question_prompt_template
    if _question_prompt_template is None:
        _question_prompt_template = load_prompt("question_generation_prompt.yaml")
    return _question_prompt_template


def get_sql_prompt():
    """Get SQL generation prompt template."""
    global _sql_prompt_template
    if _sql_prompt_template is None:
        _sql_prompt_template = load_prompt("sql_generation_prompt.yaml")
    return _sql_prompt_template


def get_industry_mapper():
    """Get industry mapper (singleton)."""
    global _industry_mapper
    if _industry_mapper is None:
        _industry_mapper = _create_industry_mapper()
    return _industry_mapper


def get_title_tier_mapper():
    """Get title tier mapper (singleton)."""
    global _title_tier_mapper
    if _title_tier_mapper is None:
        _title_tier_mapper = _create_title_tier_mapper()
    return _title_tier_mapper


def get_sql_validator():
    """Get SQL validator (singleton)."""
    global _sql_validator
    if _sql_validator is None:
        _sql_validator = SQLValidator()
    return _sql_validator


def get_info_tool():
    """Get info SQL database tool (singleton)."""
    global _info_tool
    if _info_tool is None:
        _info_tool = get_info_sql_database_tool()
    return _info_tool

