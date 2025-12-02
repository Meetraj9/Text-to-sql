"""
Clarification and question generation node.
"""

import json

from workflows.state import WorkflowState, ConversationContext
from workflows.memory import (
    get_conversation_for_prompt,
    build_conversation_summary,
    track_question_answer
)
from workflows.nodes.shared import (
    get_llm,
    get_question_prompt
)
from workflows.models import QuestionResponse
from utils.text_to_sql.value_utils import is_empty_value
from utils.common.logger import get_logger
from utils.common.config import get_workflow_settings

logger = get_logger(__name__)


def request_clarification_node(state: WorkflowState) -> WorkflowState:
    """
    Generate context-aware clarifying question (HITL interrupt point).
    Supports both missing field questions and contextual questions.
    """
    missing_fields = state.get("missing_fields", [])
    extracted_info = state.get("extracted_info", {})
    
    # Get conversation context
    settings = get_workflow_settings()
    conversation_history_limit = settings.get("conversation_history_limit", 10)
    conversation_history = state.get("conversation_history", [])
    conversation_text = get_conversation_for_prompt(
        conversation_history,
        include_last_n=conversation_history_limit
    )
    
    context_summary = build_conversation_summary(state.get("conversation_context", ConversationContext()))
    
    # Check how many questions have been asked
    questions_asked = state.get("conversation_context", ConversationContext()).questions_asked
    question_count = len(questions_asked) if questions_asked else 0
    
    # Check if SQL is already generated - this means we're asking follow-up questions
    sql_exists = state.get("sql_query") is not None
    sql_valid = state.get("sql_valid", False)
    
    logger.info("=" * 80)
    logger.info("NODE: request_clarification - Generating question")
    logger.info(f"SQL exists: {sql_exists}, SQL valid: {sql_valid}")
    logger.info(f"Missing fields: {missing_fields}")
    logger.info(f"Questions asked so far: {question_count}")
    
    # If SQL exists and is valid, we're in follow-up mode - always try to ask a question
    if sql_exists and sql_valid:
        logger.info("SQL generated - generating follow-up refinement question")
        should_ask_contextual = True
        # Don't check missing_fields when SQL exists - we want to ask follow-up regardless
    else:
        # Check if we should ask contextual questions even when all required fields are present
        should_ask_contextual = False
        if not missing_fields or (missing_fields and "title" in missing_fields and len(missing_fields) == 1):
            # All required fields present, or only title missing (which is optional)
            geography = extracted_info.get("geography")
            industry = extracted_info.get("industry")
            if geography and industry and not is_empty_value(geography) and not is_empty_value(industry):
                # Limit contextual questions before SQL generation
                max_contextual = settings.get("max_contextual_questions_before_sql", 1)
                if question_count < max_contextual:
                    should_ask_contextual = True
                    logger.info("All required fields present - checking for contextual questions")
                else:
                    logger.info(f"Already asked {question_count} questions - skipping more contextual questions")
    
    if not missing_fields and not should_ask_contextual:
        logger.info("No missing fields and no contextual questions needed - proceeding to SQL generation")
        logger.info("=" * 80)
        state["needs_human_input"] = False
        state["current_question"] = None
        return state
    
    # Build prompt
    prompt_template = get_question_prompt()
    
    # Format missing fields
    required_missing = [f for f in missing_fields if f in ["geography", "industry"]]
    missing_fields_str = ", ".join(missing_fields) if missing_fields else "None"
    
    # Enable contextual mode if we should ask questions (either missing fields or follow-up after SQL)
    contextual_mode = "true" if (should_ask_contextual and not required_missing) or (sql_exists and sql_valid) else "false"
    
    sql_generated = "true" if sql_exists and sql_valid else "false"
    
    json_indent = settings.get("json_indent", 2)
    prompt = prompt_template.format(
        extracted_info=json.dumps(extracted_info, indent=json_indent),
        missing_fields=missing_fields_str,
        contextual_mode=contextual_mode,
        sql_generated=sql_generated
    )
    
    # Build comprehensive context for LLM to detect user intent to proceed
    context_parts = []
    if conversation_text and conversation_text != "No previous conversation.":
        context_parts.append(f"Recent conversation:\n{conversation_text}")
    
    if questions_asked:
        context_parts.append(f"Questions already asked: {', '.join(questions_asked)}")
    
    if context_summary and context_summary != "No conversation history yet.":
        context_parts.append(f"Context summary:\n{context_summary}")
    
    if context_parts:
        context_text = "\n\n".join(context_parts)
        prompt = f"{context_text}\n\n{prompt}"
    
    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(QuestionResponse)
        response = structured_llm.invoke(prompt)
        
        # Use structured output - more reliable than string matching
        if not response.needs_clarification:
            state["needs_human_input"] = False
            state["current_question"] = None
            if sql_exists and sql_valid:
                logger.info("LLM determined no follow-up question needed (user may want to proceed)")
            else:
                logger.info("All information present - no clarification needed")
            logger.info("=" * 80)
            return state
        
        # Validate question is provided when clarification is needed
        min_question_length = settings.get("min_question_length", 10)
        if not response.question or len(response.question.strip()) < min_question_length:
            logger.error("LLM returned needs_clarification=True but question is missing or too short")
            state["needs_human_input"] = False
            state["current_question"] = None
            return state
        
        question = response.question.strip()
        state["current_question"] = question
        state["needs_human_input"] = True
        state["workflow_state"] = "clarifying"
        
        # Add question as assistant message to conversation history
        from workflows.memory import update_conversation_memory
        state["conversation_history"] = update_conversation_memory(
            state.get("conversation_history", []),
            role="assistant",
            content=question,
            extracted_info_snapshot=state.get("extracted_info"),
            question_asked=question
        )
        
        # Track question
        if state.get("conversation_context"):
            state["conversation_context"] = track_question_answer(
                state["conversation_context"],
                question
            )
        
        logger.info(f"Generated question: {question}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error generating question: {e}", exc_info=True)
        logger.info("=" * 80)
        state["needs_human_input"] = False
        state["current_question"] = None
    
    return state

