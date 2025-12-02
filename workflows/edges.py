"""
Conditional edge logic for LangGraph workflow.
"""

from workflows.state import WorkflowState
from utils.common.logger import get_logger
from utils.common.config import get_workflow_settings

logger = get_logger(__name__)


def should_clarify(state: WorkflowState) -> str:
    """
    Determine if clarification is needed.
    
    Returns:
        "clarify" if missing required fields exist OR contextual questions should be asked, "generate" otherwise
    """
    missing_fields = state.get("missing_fields", [])
    extracted_info = state.get("extracted_info", {})
    
    # Check for required fields (geography, industry)
    required_missing = [f for f in missing_fields if f in ["geography", "industry"]]
    
    if required_missing:
        logger.debug(f"Clarification needed for required fields: {required_missing}")
        return "clarify"
    
    if missing_fields:
        logger.debug(f"Recommended fields missing: {missing_fields}, checking for questions")
        return "clarify"
    
    # Check how many questions have been asked
    conversation_context = state.get("conversation_context")
    questions_asked = conversation_context.questions_asked if conversation_context else []
    question_count = len(questions_asked) if questions_asked else 0
    
    geography = extracted_info.get("geography")
    industry = extracted_info.get("industry")
    if geography and industry:
        settings = get_workflow_settings()
        max_contextual = settings.get("max_contextual_questions_before_sql", 1)
        if question_count < max_contextual:
            logger.debug("All required fields present, allowing contextual questions check")
            return "clarify"
        else:
            logger.debug(f"Already asked {question_count} questions - proceeding to SQL generation")
    
    logger.debug("All required fields present, proceeding to SQL generation")
    return "generate"


def should_ask_followup(state: WorkflowState) -> str:
    """
    Determine if we should ask follow-up questions after SQL is generated.
    
    Returns:
        "clarify" if we should ask follow-up questions, "end" otherwise
    """
    sql_query = state.get("sql_query")
    sql_valid = state.get("sql_valid")
    
    logger.info("=" * 80)
    logger.info("EDGE: should_ask_followup - Checking if follow-up question needed")
    logger.info(f"SQL query exists: {sql_query is not None}")
    logger.info(f"SQL valid: {sql_valid}")
    
    # Only ask follow-up if SQL is valid and generated
    if not sql_query or not sql_valid:
        logger.info("No valid SQL - ending workflow")
        logger.info("=" * 80)
        return "end"
    
    # Check how many questions have been asked
    conversation_context = state.get("conversation_context")
    questions_asked = conversation_context.questions_asked if conversation_context else []
    question_count = len(questions_asked) if questions_asked else 0
    
    logger.info(f"SQL generated - routing to clarification (questions asked so far: {question_count})")
    logger.info("=" * 80)
    return "clarify"


def route_after_extraction(state: WorkflowState) -> str:
    """
    Route after extraction based on whether this is an update or new request.
    
    Returns:
        "update" if SQL exists, "validate" otherwise
    """
    sql_query = state.get("sql_query")
    extracted_info = state.get("extracted_info", {})
    
    logger.info("=" * 80)
    logger.info("EDGE: route_after_extraction - Determining routing")
    logger.info(f"SQL query exists: {sql_query is not None}")
    logger.info(f"Extracted info: {extracted_info}")
    
    if sql_query:
        logger.info("Routing to UPDATE flow (SQL exists)")
        logger.info("=" * 80)
        return "update"
    else:
        logger.info("Routing to VALIDATE flow (new request)")
        logger.info("=" * 80)
        return "validate"



