"""
State schema definitions for LangGraph workflow.
"""

from typing import TypedDict, List, Optional, Dict, Any, Literal
from typing_extensions import Annotated
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversationTurn:
    """Single turn in conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    extracted_info_snapshot: Optional[Dict[str, Any]] = None
    question_asked: Optional[str] = None


@dataclass
class ConversationContext:
    """Rich conversation context for memory."""
    recent_turns: List[ConversationTurn] = field(default_factory=list)  # Last 10-15 turns
    questions_asked: List[str] = field(default_factory=list)  # Track what we've asked
    answers_received: Dict[str, str] = field(default_factory=dict)  # Map question -> answer
    corrections_made: List[Dict[str, str]] = field(default_factory=list)  # Track field corrections
    update_requests: List[str] = field(default_factory=list)  # History of update requests
    ambiguities_resolved: List[Dict[str, Any]] = field(default_factory=list)  # Track resolved ambiguities


class WorkflowState(TypedDict):
    """State schema for LangGraph workflow."""
    messages: Annotated[List[Dict[str, str]], "add_messages"]
    conversation_history: List[ConversationTurn]  # Short-term memory
    conversation_context: ConversationContext  # Rich context object
    extracted_info: Dict[str, Optional[str]]
    extraction_history: List[Dict[str, Any]]  # History of extraction attempts
    missing_fields: List[str]
    sql_query: Optional[str]
    sql_valid: Optional[bool]
    sql_error: Optional[str]
    sic_context: Optional[Dict[str, Any]]
    title_sql_condition: Optional[str]  # SQL condition for title tier mapping
    mentioned_fields: Optional[List[str]]  # Fields mentioned in current update request
    workflow_state: Literal["extracting", "clarifying", "generating", "complete", "updating"]
    needs_human_input: bool
    current_question: Optional[str]
    last_extraction_confidence: Optional[float]  # Track extraction confidence

