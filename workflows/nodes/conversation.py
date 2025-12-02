"""
Conversation management node.
"""

from workflows.state import WorkflowState, ConversationContext
from workflows.memory import (
    update_conversation_memory,
    update_conversation_context,
    prune_old_context
)
from utils.common.logger import get_logger

logger = get_logger(__name__)


def conversation_manager_node(state: WorkflowState) -> WorkflowState:
    """
    Manage conversation memory and context.
    
    Updates conversation history and context with the latest turn.
    """
    logger.debug("Running conversation_manager_node")
    
    # Get the latest message
    if not state["messages"]:
        return state
    
    latest_message = state["messages"][-1]
    role = latest_message.get("role", "user")
    content = latest_message.get("content", "")
    
    # Update conversation history
    previous_extracted_info = state.get("extracted_info", {})
    state["conversation_history"] = update_conversation_memory(
        state.get("conversation_history", []),
        role=role,
        content=content,
        extracted_info_snapshot=state.get("extracted_info"),
        question_asked=state.get("current_question")
    )
    
    # Update conversation context
    if not state.get("conversation_context"):
        state["conversation_context"] = ConversationContext()
    
    latest_turn = state["conversation_history"][-1] if state["conversation_history"] else None
    if latest_turn:
        state["conversation_context"] = update_conversation_context(
            state["conversation_context"],
            latest_turn,
            state.get("extracted_info", {}),
            previous_extracted_info
        )
    
    # Prune old context if needed
    state["conversation_context"] = prune_old_context(state["conversation_context"])
    
    logger.debug("Conversation memory updated")
    return state

