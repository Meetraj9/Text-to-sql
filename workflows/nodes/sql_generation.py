"""
SQL generation and validation nodes.
"""

from workflows.state import WorkflowState
from workflows.memory import get_conversation_for_prompt
from workflows.nodes.shared import (
    get_llm,
    get_sql_prompt,
    get_sql_validator,
    get_info_tool
)
from utils.text_to_sql.value_utils import is_empty_value
from utils.common.logger import get_logger
from utils.common.config import get_db_settings

logger = get_logger(__name__)


def generate_sql_node(state: WorkflowState) -> WorkflowState:
    """
    Generate SQL query with full conversation context.
    
    Note: This node uses extracted_info which already preserves unmentioned fields from update requests.
    It also uses sic_context and title_sql_condition which are preserved by map_industry_node and map_title_node
    when those fields are not mentioned in update requests.
    
    All filters follow the same preservation pattern:
    - geography: Preserved in extracted_info if not mentioned
    - industry: Preserved in extracted_info + sic_context if not mentioned
    - title: Preserved in extracted_info + title_sql_condition if not mentioned
    - employee_size: Preserved in extracted_info if not mentioned
    - square_footage: Preserved in extracted_info if not mentioned
    """
    extracted_info = state.get("extracted_info", {})
    
    # Get schema information
    try:
        info_tool = get_info_tool()
        schema_info = info_tool.run("icp_data")
    except Exception as e:
        logger.error(f"Failed to get schema info: {e}")
        state["sql_error"] = f"Unable to retrieve database schema: {str(e)}"
        state["sql_valid"] = False
        return state
    
    # Get industry with SIC codes - handle multiple industries
    sic_context = state.get("sic_context", {})
    industry = extracted_info.get("industry", "Not specified")
    
    if not industry or is_empty_value(industry):
        industry_value = "Not specified (OMIT this filter - do not include industry condition)"
    elif "," in industry:
        # Multiple industries - need to map each
        industries_list = [i.strip() for i in industry.split(",")]
        industry_value = f"Multiple industries: {', '.join(industries_list)} (map each to SIC codes and combine with OR)"
    elif sic_context.get("codes"):
        sic_codes = sic_context["codes"]
        if not sic_codes or len(sic_codes) == 0:
            industry_value = "Not specified (OMIT this filter - do not include industry condition)"
        else:
            sic_codes_str = ", ".join([f"'{code}'" for code in sic_codes])
            rationale = sic_context.get("rationale", "")
            # Format explicitly: show the exact SQL condition needed with reasoning
            if rationale:
                industry_value = f"{industry} - REQUIRED SQL condition: industry IN ({sic_codes_str})\nSIC Code Reasoning: {rationale}"
            else:
                industry_value = f"{industry} - REQUIRED SQL condition: industry IN ({sic_codes_str})"
    else:
        industry_value = "Not specified (OMIT this filter - do not include industry condition)"
    
    # Get title with SQL condition - handle multiple titles
    title = extracted_info.get("title", "Not specified")
    title_sql_condition = state.get("title_sql_condition")
    
    if not title or is_empty_value(title):
        title_value = "Not specified (OMIT this filter - do not include title_tier condition)"
    elif "," in title:
        # Multiple titles
        titles_list = [t.strip() for t in title.split(",")]
        title_value = f"Multiple titles: {', '.join(titles_list)} (classify each into appropriate tier and combine with OR)"
    elif title_sql_condition:
        title_value = f"{title} (SQL condition: {title_sql_condition})"
    else:
        title_value = f"{title} (classify into tier_i, tier_ii, or tier_iii)"
    
    # Get conversation context for SQL generation
    from utils.common.config import get_workflow_settings
    settings = get_workflow_settings()
    conversation_history_limit = settings.get("conversation_history_limit", 10)
    conversation_text = get_conversation_for_prompt(
        state.get("conversation_history", []),
        include_last_n=conversation_history_limit
    )
    
    # Format prompt - explicitly handle None values
    prompt_template = get_sql_prompt()
    
    # Check for None/empty values and format accordingly
    geography = extracted_info.get("geography")
    employee_size = extracted_info.get("employee_size")
    square_footage = extracted_info.get("square_footage")
    sales_volume = extracted_info.get("sales_volume")
    
    if geography and not is_empty_value(geography):
        if "," in geography:
            # Multiple locations - format for OR condition (database-agnostic)
            locations = [loc.strip() for loc in geography.split(",")]
            geography_str = f"Multiple locations: {', '.join(locations)} (use OR conditions: LOWER(geography) LIKE LOWER('%{locations[0]}%') OR LOWER(geography) LIKE LOWER('%{locations[1]}%') ...)"
        else:
            geography_str = geography
    else:
        geography_str = "Not specified (OMIT this filter)"
    
    employee_size_str = employee_size if employee_size and not is_empty_value(employee_size) else "Not specified (OMIT this filter - do not include employee_size condition)"
    square_footage_str = square_footage if square_footage and not is_empty_value(square_footage) else "Not specified (OMIT this filter - do not include square_footage condition)"
    sales_volume_str = sales_volume if sales_volume and not is_empty_value(sales_volume) else "Not specified (OMIT this filter - do not include sales_volume condition)"
    
    # Get database type for context-aware SQL generation
    db_settings = get_db_settings()
    db_type = db_settings.db_type or "postgresql"
    
    prompt = prompt_template.format(
        schema_info=schema_info,
        geography=geography_str,
        industry=industry_value,
        title=title_value,
        employee_size=employee_size_str,
        square_footage=square_footage_str,
        sales_volume=sales_volume_str
    )
    
    # Add database type context for better SQL generation
    if db_type.lower() != "postgresql":
        prompt = f"Database Type: {db_type.upper()}\nUse standard SQL syntax compatible with {db_type}.\n\n{prompt}"
    
    # Add conversation context if available
    if conversation_text and conversation_text != "No previous conversation.":
        prompt = f"Conversation context:\n{conversation_text}\n\n{prompt}"
    
    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        sql_query = response.content.strip()
        
        # Clean up SQL query (remove markdown code blocks if present)
        if sql_query.startswith("```"):
            parts = sql_query.split("```")
            if len(parts) >= 2:
                sql_query = parts[1]
                if sql_query.startswith("sql"):
                    sql_query = sql_query[3:]
                sql_query = sql_query.strip()
        
        state["sql_query"] = sql_query
        state["workflow_state"] = "generating"
        logger.info(f"Generated SQL query: {sql_query}")
        
        # Verify industry filter is included if SIC codes exist
        industry = extracted_info.get("industry")
        sic_context = state.get("sic_context", {})
        sic_codes = sic_context.get("codes", [])
        
        if industry and not is_empty_value(industry) and sic_codes:
            if "industry" not in sql_query.lower():
                logger.warning(f"Industry '{industry}' has SIC codes {sic_codes} but SQL doesn't include industry filter")
        
        # Verify employee_size filter is omitted if None
        if not employee_size or is_empty_value(employee_size):
            if "employee_size" in sql_query.lower():
                logger.warning(f"employee_size is None but SQL still contains employee_size filter")
        
    except Exception as e:
        logger.error(f"Error generating SQL: {e}", exc_info=True)
        state["sql_error"] = str(e)
        state["sql_valid"] = False
    
    return state


def validate_sql_node(state: WorkflowState) -> WorkflowState:
    """
    Validate SQL query.
    """
    logger.debug("Running validate_sql_node")
    
    sql_query = state.get("sql_query")
    if not sql_query:
        state["sql_valid"] = False
        state["sql_error"] = "No SQL query to validate"
        return state
    
    sql_validator = get_sql_validator()
    is_valid, error_message = sql_validator.validate(sql_query)
    
    state["sql_valid"] = is_valid
    state["sql_error"] = error_message if not is_valid else None
    
    if is_valid:
        state["workflow_state"] = "complete"
        logger.info("SQL query validation: PASSED")
    else:
        logger.warning(f"SQL query validation: FAILED - {error_message}")
    
    return state

