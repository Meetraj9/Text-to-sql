"""
Conversation memory management utilities.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from workflows.state import ConversationTurn, ConversationContext
from utils.text_to_sql.value_utils import is_empty_value
from utils.common.logger import get_logger
from utils.common.config import get_workflow_settings

logger = get_logger(__name__)

# Get workflow settings
def _get_max_conversation_turns() -> int:
    """Get max conversation turns from config."""
    settings = get_workflow_settings()
    return settings.get("max_conversation_turns", 15)


def update_conversation_memory(
    conversation_history: List[ConversationTurn],
    role: str,
    content: str,
    extracted_info_snapshot: Optional[Dict[str, Any]] = None,
    question_asked: Optional[str] = None
) -> List[ConversationTurn]:
    """
    Add new turn to conversation history.
    
    Args:
        conversation_history: Current conversation history
        role: "user" or "assistant"
        content: Message content
        extracted_info_snapshot: Snapshot of extracted info at this turn
        question_asked: Question asked (if assistant turn)
        
    Returns:
        Updated conversation history
    """
    new_turn = ConversationTurn(
        role=role,
        content=content,
        timestamp=datetime.now(),
        extracted_info_snapshot=extracted_info_snapshot,
        question_asked=question_asked
    )
    
    updated_history = conversation_history + [new_turn]
    
    # Prune old turns if needed
    max_turns = _get_max_conversation_turns()
    if len(updated_history) > max_turns:
        updated_history = updated_history[-max_turns:]
        logger.debug(f"Pruned conversation history to {max_turns} turns")
    
    return updated_history


def update_conversation_context(
    context: ConversationContext,
    turn: ConversationTurn,
    extracted_info: Dict[str, Optional[str]],
    previous_extracted_info: Optional[Dict[str, Optional[str]]] = None
) -> ConversationContext:
    """
    Update conversation context with new information.
    
    Args:
        context: Current conversation context
        turn: New conversation turn
        extracted_info: Current extracted information
        previous_extracted_info: Previous extracted information (for detecting corrections)
        
    Returns:
        Updated conversation context
    """
    # Track questions asked
    if turn.role == "assistant" and turn.question_asked:
        if turn.question_asked not in context.questions_asked:
            context.questions_asked.append(turn.question_asked)
            logger.debug(f"Tracked new question: {turn.question_asked}")
    
    # Track answers received
    if turn.role == "user" and context.questions_asked:
        # Match answer to most recent unanswered question
        for question in reversed(context.questions_asked):
            if question not in context.answers_received:
                settings = get_workflow_settings()
                truncate_length = settings.get("question_truncate_length", 50)
                context.answers_received[question] = turn.content
                logger.debug(f"Tracked answer for question: {question[:truncate_length]}...")
                break
    
    # Track corrections
    if previous_extracted_info and turn.role == "user":
        corrections = []
        for key, new_value in extracted_info.items():
            old_value = previous_extracted_info.get(key)
            if old_value and new_value and old_value != new_value:
                if not is_empty_value(old_value) and not is_empty_value(new_value):
                    corrections.append({
                        "field": key,
                        "old_value": old_value,
                        "new_value": new_value
                    })
        
        if corrections:
            context.corrections_made.extend(corrections)
            logger.debug(f"Tracked {len(corrections)} corrections")
    
    # Track update requests
    if turn.role == "user" and any(keyword in turn.content.lower() for keyword in [
        "update", "change", "modify", "edit", "revise"
    ]):
        context.update_requests.append(turn.content)
        settings = get_workflow_settings()
        truncate_length = settings.get("question_truncate_length", 50)
        logger.debug(f"Tracked update request: {turn.content[:truncate_length]}...")
    
    return context


def get_relevant_context(
    conversation_history: List[ConversationTurn],
    max_turns: Optional[int] = None
) -> List[ConversationTurn]:
    """
    Extract relevant context from conversation history.
    
    Args:
        conversation_history: Full conversation history
        max_turns: Maximum number of turns to return (defaults to config value)
        
    Returns:
        Most relevant recent turns
    """
    if max_turns is None:
        settings = get_workflow_settings()
        max_turns = settings.get("conversation_history_limit", 10)
    
    # Return most recent turns
    return conversation_history[-max_turns:] if len(conversation_history) > max_turns else conversation_history


def build_conversation_summary(context: ConversationContext) -> str:
    """
    Create a summary of conversation for LLM prompts.
    
    Args:
        context: Conversation context
        
    Returns:
        Formatted conversation summary
    """
    summary_parts = []
    
    if context.questions_asked:
        settings = get_workflow_settings()
        max_questions = settings.get("max_questions_to_show", 5)
        summary_parts.append(f"Questions asked: {len(context.questions_asked)}")
        for i, question in enumerate(context.questions_asked[-max_questions:], 1):
            answer = context.answers_received.get(question, "Not answered yet")
            summary_parts.append(f"  Q{i}: {question}")
            summary_parts.append(f"  A{i}: {answer}")
    
    if context.corrections_made:
        summary_parts.append(f"\nCorrections made: {len(context.corrections_made)}")
        for correction in context.corrections_made[-3:]:  # Last 3 corrections
            summary_parts.append(
                f"  {correction['field']}: '{correction['old_value']}' -> '{correction['new_value']}'"
            )
    
    if context.update_requests:
        settings = get_workflow_settings()
        max_updates = settings.get("max_updates_to_keep", 5)
        truncate_length = settings.get("text_truncate_length", 100)
        summary_parts.append(f"\nUpdate requests: {len(context.update_requests)}")
        for update in context.update_requests[-max_updates:]:
            summary_parts.append(f"  - {update[:truncate_length]}")
    
    return "\n".join(summary_parts) if summary_parts else "No conversation history yet."


def get_conversation_for_prompt(
    conversation_history: List[ConversationTurn],
    include_last_n: Optional[int] = None
) -> str:
    """Format conversation history for LLM prompts."""
    if include_last_n is None:
        settings = get_workflow_settings()
        include_last_n = settings.get("conversation_history_limit", 10)
    """
    Format conversation history for LLM prompts.
    
    Args:
        conversation_history: Conversation history
        include_last_n: Number of recent turns to include
        
    Returns:
        Formatted conversation string
    """
    relevant_turns = get_relevant_context(conversation_history, max_turns=include_last_n)
    
    if not relevant_turns:
        return "No previous conversation."
    
    formatted_turns = []
    for turn in relevant_turns:
        role_label = "User" if turn.role == "user" else "Assistant"
        formatted_turns.append(f"{role_label}: {turn.content}")
    
    return "\n".join(formatted_turns)


def track_question_answer(
    context: ConversationContext,
    question: str,
    answer: Optional[str] = None
) -> ConversationContext:
    """
    Track a question-answer pair.
    
    Args:
        context: Conversation context
        question: Question asked
        answer: Answer received (if available)
        
    Returns:
        Updated context
    """
    if question not in context.questions_asked:
        context.questions_asked.append(question)
    
    if answer:
        context.answers_received[question] = answer
    
    return context


def track_correction(
    context: ConversationContext,
    field: str,
    old_value: str,
    new_value: str
) -> ConversationContext:
    """
    Track a field correction.
    
    Args:
        context: Conversation context
        field: Field name
        old_value: Previous value
        new_value: New value
        
    Returns:
        Updated context
    """
    context.corrections_made.append({
        "field": field,
        "old_value": old_value,
        "new_value": new_value
    })
    return context


def prune_old_context(
    context: ConversationContext,
    keep_recent_turns: Optional[int] = None
) -> ConversationContext:
    """Prune old context to keep only most relevant information."""
    if keep_recent_turns is None:
        settings = get_workflow_settings()
        keep_recent_turns = settings.get("conversation_history_limit", 10)
    """
    Prune old context to keep only most relevant information.
    
    Args:
        context: Conversation context
        keep_recent_turns: Number of recent turns to keep
        
    Returns:
        Pruned context
    """
    if len(context.recent_turns) > keep_recent_turns:
        context.recent_turns = context.recent_turns[-keep_recent_turns:]
    
    # Keep only recent questions/answers
    if len(context.questions_asked) > keep_recent_turns:
        context.questions_asked = context.questions_asked[-keep_recent_turns:]
        # Also prune answers for removed questions
        context.answers_received = {
            q: a for q, a in context.answers_received.items()
            if q in context.questions_asked
        }
    
    # Keep only recent corrections
    settings = get_workflow_settings()
    max_corrections = settings.get("max_corrections_to_keep", 5)
    if len(context.corrections_made) > max_corrections:
        context.corrections_made = context.corrections_made[-max_corrections:]
    
    # Keep only recent update requests
    max_updates = settings.get("max_updates_to_keep", 5)
    if len(context.update_requests) > max_updates:
        context.update_requests = context.update_requests[-max_updates:]
    
    return context

