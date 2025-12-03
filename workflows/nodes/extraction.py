"""
Information extraction and validation nodes.
"""

from workflows.state import WorkflowState, ConversationContext
from workflows.memory import (
    get_conversation_for_prompt,
    build_conversation_summary
)
from workflows.nodes.shared import (
    get_llm,
    get_extraction_prompt
)
from utils.text_to_sql.value_utils import is_empty_value, get_empty_extracted_info
from workflows.models import ExtractedInfoWithMentioned
from utils.common.logger import get_logger
from utils.common.config import get_workflow_settings

logger = get_logger(__name__)


def extract_info_node(state: WorkflowState) -> WorkflowState:
    """
    Extract structured information from user input with full conversation context.
    """
    if not state["messages"]:
        logger.warning("No messages in state, skipping extraction")
        return state
    
    latest_message = state["messages"][-1]
    user_input = latest_message.get("content", "")
    
    logger.info(f"User input: {user_input}")
    
    if not user_input:
        logger.warning("Empty user input, skipping extraction")
        return state
    
    # Build enhanced prompt with conversation context
    settings = get_workflow_settings()
    conversation_history_limit = settings.get("conversation_history_limit", 10)
    conversation_text = get_conversation_for_prompt(
        state.get("conversation_history", []),
        include_last_n=conversation_history_limit
    )
    
    context_summary = build_conversation_summary(state.get("conversation_context", ConversationContext()))
    
    # Determine if this is an update request
    is_update_request = state.get("sql_query") is not None
    
    # Build context parts
    context_parts = []
    
    if is_update_request:
        context_parts.append("CRITICAL: This is an UPDATE request. The user wants to modify an existing SQL query.")
        context_parts.append("ONLY extract fields that are EXPLICITLY mentioned in the user's current response.")
        context_parts.append("For fields NOT mentioned, return null/None - DO NOT infer values from context.")
    
    # Add conversation context
    if conversation_text and conversation_text != "No previous conversation.":
        context_parts.append(f"Conversation history:\n{conversation_text}")
    
    if context_summary and context_summary != "No conversation history yet.":
        context_parts.append(f"Conversation summary:\n{context_summary}")
    
    # Add existing extracted info
    existing_info = state.get("extracted_info", {})
    if existing_info:
        existing_fields = []
        for key, value in existing_info.items():
            if value and not is_empty_value(value):
                existing_fields.append(f"{key}: {value}")
        if existing_fields:
            if is_update_request:
                context_parts.append(f"Current SQL query parameters: {', '.join(existing_fields)}")
                context_parts.append("IMPORTANT: If user wants to ADD/APPEND to existing values (indicated by phrases like 'too', 'also', 'both', 'include', 'add'), extract ALL values including existing ones. If user wants to REPLACE (no append indicators), extract only the new value.")
                context_parts.append("Only update fields that are EXPLICITLY mentioned in the user's update request.")
            else:
                context_parts.append(f"Previously extracted information: {', '.join(existing_fields)}")
    
    # Build enhanced query
    if context_parts:
        enhanced_query = "\n".join(context_parts) + f"\n\nUser's CURRENT input (extract ONLY from this): {user_input}"
    else:
        enhanced_query = user_input
    
    # For update requests, be extra explicit
    if is_update_request:
        enhanced_query += "\n\nREMINDER: This is an UPDATE request. ONLY extract fields EXPLICITLY mentioned in the user's CURRENT input above. For any field NOT mentioned, return null."
    
    # Get prompt template and format
    prompt_template = get_extraction_prompt()
    prompt = prompt_template.format(user_query=enhanced_query)
    
    try:
        # Always use ExtractedInfoWithMentioned - mentioned flags are False for new requests
        extraction_llm = get_llm().with_structured_output(ExtractedInfoWithMentioned)
        extracted = extraction_llm.invoke(prompt)
        
        extracted_dict = {
            "geography": extracted.geography,
            "industry": extracted.industry,
            "target_customer_type": extracted.target_customer_type,
            "title": extracted.title,
            "employee_size": extracted.employee_size,
            "square_footage": extracted.square_footage,
            "sales_volume": extracted.sales_volume
        }
        
        # Track extraction attempt
        extraction_history = state.get("extraction_history", [])
        extraction_history.append({
            "input": user_input,
            "extracted": extracted_dict,
            "is_update": is_update_request
        })
        state["extraction_history"] = extraction_history
        
        if is_update_request:
            # For updates, use mentioned flags to determine which fields to update
            # extracted is ExtractedInfoWithMentioned for update requests
            mentioned_fields = set()
            if extracted.geography_mentioned:
                mentioned_fields.add("geography")
            if extracted.industry_mentioned:
                mentioned_fields.add("industry")
            if extracted.title_mentioned:
                mentioned_fields.add("title")
            if extracted.employee_size_mentioned:
                mentioned_fields.add("employee_size")
            if extracted.square_footage_mentioned:
                mentioned_fields.add("square_footage")
            if extracted.sales_volume_mentioned:
                mentioned_fields.add("sales_volume")
            if extracted.target_customer_type_mentioned:
                mentioned_fields.add("target_customer_type")
            
            # Store mentioned fields in state so other nodes can check
            state["mentioned_fields"] = list(mentioned_fields)
            
            # Start with existing extracted_info to preserve all unmentioned fields
            current_extracted = dict(state.get("extracted_info", {}))
            
            # Only update fields that were explicitly mentioned
            for field in mentioned_fields:
                extracted_value = extracted_dict.get(field)
                if extracted_value and not is_empty_value(extracted_value):
                    current_extracted[field] = extracted_value
                elif extracted_value is None:
                    current_extracted[field] = None
            
            # Explicitly preserve all fields NOT in mentioned_fields
            all_fields = ["geography", "industry", "target_customer_type", "title", "employee_size", "square_footage", "sales_volume"]
            for field in all_fields:
                if field not in mentioned_fields:
                    # Preserve existing value - do NOT use extracted value even if LLM provided one
                    existing_value = state.get("extracted_info", {}).get(field)
                    current_extracted[field] = existing_value
                    logger.debug(f"Preserving unmentioned field '{field}': {existing_value}")
            
            state["extracted_info"] = current_extracted
        else:
            # For new queries, track mentioned fields based on mentioned flags
            # This allows us to distinguish "explicitly said 'any'" from "not mentioned"
            mentioned_fields = set()
            if extracted.geography_mentioned:
                mentioned_fields.add("geography")
            if extracted.industry_mentioned:
                mentioned_fields.add("industry")
            if extracted.title_mentioned:
                mentioned_fields.add("title")
            if extracted.employee_size_mentioned:
                mentioned_fields.add("employee_size")
            if extracted.square_footage_mentioned:
                mentioned_fields.add("square_footage")
            if extracted.sales_volume_mentioned:
                mentioned_fields.add("sales_volume")
            if extracted.target_customer_type_mentioned:
                mentioned_fields.add("target_customer_type")
            
            state["mentioned_fields"] = list(mentioned_fields)
            
            # Update extracted info - include all fields, even if null (to preserve "any" = null)
            current_extracted = dict(state.get("extracted_info", {}))
            for field, value in extracted_dict.items():
                # Always update with extracted value (even if null) if field was mentioned
                if field in mentioned_fields:
                    current_extracted[field] = value
                elif value and not is_empty_value(value):
                    # If not explicitly mentioned but has value, update it
                    current_extracted[field] = value
            
            state["extracted_info"] = current_extracted
        
        logger.info(f"Extracted information: {state['extracted_info']}")
        state["workflow_state"] = "extracting"
        
    except Exception as e:
        logger.error(f"Error during information extraction: {e}", exc_info=True)
        # Fallback to empty extracted info
        if not state.get("extracted_info"):
            state["extracted_info"] = get_empty_extracted_info()
    
    return state


def validate_completeness_node(state: WorkflowState) -> WorkflowState:
    """
    Check if all required fields are present.
    
    CRITICAL: If a field is in mentioned_fields but is null, that means the user
    explicitly said "any" or "remove" for that field, so it should NOT be added
    to missing_fields (user explicitly wants no filter for that field).
    """
    logger.info("=" * 80)
    logger.info("NODE: validate_completeness_node - Checking field completeness")
    logger.info("=" * 80)
    
    extracted_info = state.get("extracted_info", {})
    mentioned_fields = set(state.get("mentioned_fields", []))
    logger.info(f"Current extracted info: {extracted_info}")
    logger.info(f"Mentioned fields: {mentioned_fields}")
    
    # Check if this is an update request - if SQL exists, skip validation for optional fields
    is_update_request = state.get("sql_query") is not None
    logger.info(f"Is update request: {is_update_request}")
    
    missing_fields = []
    
    # Required fields (always required)
    required_fields = ["geography", "industry"]
    for field in required_fields:
        value = extracted_info.get(field)
        # If field is explicitly mentioned but null, user said "any" - don't treat as missing
        if field in mentioned_fields and value is None:
            logger.info(f"Field '{field}' explicitly mentioned as 'any' (null) - not treating as missing")
            continue
        if is_empty_value(value):
            missing_fields.append(field)
            logger.info(f"Missing required field: {field}")
        else:
            logger.info(f"Required field '{field}' present: {value}")
    
    # Recommended fields (ask but proceed if not provided)
    if not is_update_request:
        title = extracted_info.get("title")
        # If title is explicitly mentioned but null, user said "any" - don't treat as missing
        if "title" in mentioned_fields and title is None:
            logger.info("Title explicitly mentioned as 'any' (null) - not treating as missing")
        elif is_empty_value(title):
            missing_fields.append("title")
            logger.info("Missing recommended field: title")
        else:
            logger.info(f"Title present: {title}")
        
        employee_size = extracted_info.get("employee_size")
        # If employee_size is explicitly mentioned but null, user said "any size" - don't treat as missing
        if "employee_size" in mentioned_fields and employee_size is None:
            logger.info("Employee size explicitly mentioned as 'any' (null) - not treating as missing")
        elif is_empty_value(employee_size):
            missing_fields.append("employee_size")
            logger.info("Missing recommended field: employee_size")
        else:
            logger.info(f"Employee size present: {employee_size}")
    else:
        employee_size = extracted_info.get("employee_size")
        if is_empty_value(employee_size):
            logger.info("Employee size is None in update - user may have cleared it, not asking again")
        else:
            logger.info(f"Employee size in update: {employee_size}")
    
    # Conditional field: square_footage (only if industry requires it)
    industry = extracted_info.get("industry")
    if not is_empty_value(industry):
        industry_lower = industry.lower()
        requires_sqft = any(keyword in industry_lower for keyword in [
            "pest control", "cleaning", "construction", "builder", "builders"
        ])
        
        if requires_sqft:
            square_footage = extracted_info.get("square_footage")
            # If square_footage is explicitly mentioned but null, user said "any" - don't treat as missing
            if "square_footage" in mentioned_fields and square_footage is None:
                logger.info("Square footage explicitly mentioned as 'any' (null) - not treating as missing")
            elif is_empty_value(square_footage):
                if not is_update_request:  # Only ask for new requests
                    missing_fields.append("square_footage")
    
    state["missing_fields"] = missing_fields
    
    return state

