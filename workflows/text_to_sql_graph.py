"""
Main LangGraph workflow for text-to-SQL with conversation memory.
"""

from typing import Optional
from langgraph.graph import StateGraph, END

from workflows.state import WorkflowState, ConversationContext
from workflows.nodes import (
    conversation_manager_node,
    extract_info_node,
    validate_completeness_node,
    request_clarification_node,
    map_industry_node,
    map_title_node,
    generate_sql_node,
    validate_sql_node,
    handle_update_node
)
from workflows.edges import (
    should_clarify,
    route_after_extraction,
    should_ask_followup
)
from utils.text_to_sql.value_utils import get_empty_extracted_info
from utils.common.logger import get_logger

logger = get_logger(__name__)


def create_text_to_sql_workflow() -> StateGraph:
    """
    Create and configure the LangGraph workflow for text-to-SQL.
    
    Returns:
        Configured StateGraph instance
    """
    logger.info("Creating text-to-SQL workflow graph")
    
    # Create state graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("conversation_manager", conversation_manager_node)
    workflow.add_node("extract_info", extract_info_node)
    workflow.add_node("validate_completeness", validate_completeness_node)
    workflow.add_node("request_clarification", request_clarification_node)
    workflow.add_node("map_industry", map_industry_node)
    workflow.add_node("map_title", map_title_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("validate_sql", validate_sql_node)
    workflow.add_node("handle_update", handle_update_node)
    
    # Set entry point
    workflow.set_entry_point("conversation_manager")
    
    # Add edges from conversation_manager
    workflow.add_edge("conversation_manager", "extract_info")
    
    # Add conditional edge after extract_info
    workflow.add_conditional_edges(
        "extract_info",
        route_after_extraction,
        {
            "update": "handle_update",
            "validate": "validate_completeness"
        }
    )
    
    # Add conditional edge after validate_completeness
    workflow.add_conditional_edges(
        "validate_completeness",
        should_clarify,
        {
            "clarify": "request_clarification",
            "generate": "map_industry"
        }
    )
    
    # Add edge from request_clarification (HITL interrupt point)
    # When needs_human_input is True, workflow will pause at END (interrupt)
    workflow.add_edge("request_clarification", END)
    
    # Add edges for SQL generation flow
    workflow.add_edge("map_industry", "map_title")
    workflow.add_edge("map_title", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    
    # After SQL validation, check if we should ask follow-up questions
    workflow.add_conditional_edges(
        "validate_sql",
        should_ask_followup,
        {
            "clarify": "request_clarification",
            "end": END
        }
    )
    
    # Add edges for update flow
    # After handling update, skip validation and go directly to mapping
    workflow.add_edge("handle_update", "map_industry")
    
    logger.info("Workflow graph created successfully")
    return workflow


def create_initial_state(user_input: str, existing_state: Optional[WorkflowState] = None) -> WorkflowState:
    """
    Create initial workflow state from user input.
    If existing_state is provided, preserve it and just add the new message.
    
    Args:
        user_input: Initial user input
        existing_state: Optional existing state to preserve
        
    Returns:
        Initial WorkflowState
    """
    if existing_state:
        # Preserve existing state, just add new message
        new_state = existing_state.copy()
        new_state["messages"].append({"role": "user", "content": user_input})
        return new_state
    
    # Create fresh state
    return {
        "messages": [{"role": "user", "content": user_input}],
        "conversation_history": [],
        "conversation_context": ConversationContext(),
        "extracted_info": get_empty_extracted_info(),
        "extraction_history": [],
        "missing_fields": [],
        "sql_query": None,
        "sql_valid": None,
        "sql_error": None,
        "sic_context": None,
        "title_sql_condition": None,
        "mentioned_fields": [],
        "workflow_state": "extracting",
        "needs_human_input": False,
        "current_question": None,
        "last_extraction_confidence": None
    }



