"""
Mapping nodes for industry (SIC codes) and title (tiers).
"""

from workflows.state import WorkflowState
from workflows.nodes.shared import (
    get_industry_mapper,
    get_title_tier_mapper
)
from utils.text_to_sql.value_utils import is_empty_value
from utils.text_to_sql.industry_mapper import IndustryNotFoundError
from utils.common.logger import get_logger

logger = get_logger(__name__)


def map_industry_node(state: WorkflowState) -> WorkflowState:
    """
    Map industry to SIC codes of PRIMARY BUYERS (companies that purchase the service/product).
    Preservation rule: Only re-maps if industry was mentioned in update request, 
    otherwise preserves existing sic_context (same pattern as all other filters).
    """
    extracted_info = state.get("extracted_info", {})
    industry = extracted_info.get("industry")
    target_customer_type = extracted_info.get("target_customer_type")
    mentioned_fields = state.get("mentioned_fields", [])
    is_update_request = state.get("sql_query") is not None
    
    # Preservation: If this is an update request and industry was NOT mentioned, preserve existing sic_context
    if is_update_request and "industry" not in mentioned_fields:
        existing_sic_context = state.get("sic_context")
        if existing_sic_context:
            logger.info(f"Industry not mentioned in update - preserving existing sic_context")
            return state
    
    if not industry or is_empty_value(industry):
        return state

    if is_update_request and "industry" in mentioned_fields:
        existing_sic_context = state.get("sic_context")
        if existing_sic_context:
            existing_industry_input = existing_sic_context.get("industry_input", "")
            # Compare industry values (case-insensitive, trimmed)
            if existing_industry_input and existing_industry_input.lower().strip() == industry.lower().strip():
                logger.info(f"Industry value unchanged ('{industry}') - preserving existing sic_context")
                return state
    
    # Build descriptive industry sentence combining industry + target customer type
    if target_customer_type and not is_empty_value(target_customer_type):
        industry_description = f"{industry} for {target_customer_type}"
    else:
        industry_description = industry
    
    # Check if multiple industries (comma-separated)
    if "," in industry:
        industries_list = [i.strip() for i in industry.split(",")]
        
        # Map each industry to SIC codes (with target customer type if provided)
        all_codes = []
        all_mappings = []
        
        industry_mapper = get_industry_mapper()
        for ind in industries_list:
            try:
                # Combine individual industry with target customer type
                if target_customer_type and not is_empty_value(target_customer_type):
                    ind_description = f"{ind} for {target_customer_type}"
                else:
                    ind_description = ind
                
                sic_codes, mapping = industry_mapper.get_sic_codes_for_query(ind_description, None)
                # sic_codes is a formatted string, mapping.codes is the actual list
                all_codes.extend(mapping.codes)
                all_mappings.append(f"{ind_description}: {', '.join(mapping.codes)}")
            except Exception as e:
                logger.warning(f"Error mapping industry '{ind}': {e}")
        
        # Store combined SIC codes with detailed rationale
        # Build comprehensive rationale from individual mappings
        rationales = []
        for ind in industries_list:
            try:
                # Use same description format as above
                if target_customer_type and not is_empty_value(target_customer_type):
                    ind_description = f"{ind} for {target_customer_type}"
                else:
                    ind_description = ind
                
                _, mapping = industry_mapper.get_sic_codes_for_query(ind_description, None)
                if mapping.rationale:
                    rationales.append(f"{ind_description}: {mapping.rationale}")
            except Exception:
                pass  # Skip if mapping failed
        
        combined_rationale = "Multiple industries mapped:\n" + "\n\n".join(rationales) if rationales else f"Multiple industries mapped: {'; '.join(all_mappings)}"
        
        state["sic_context"] = {
            "industry_input": industry_description,
            "codes": list(set(all_codes)),  # Remove duplicates
            "rationale": combined_rationale
        }
    else:
        # Single industry
        # Check for exclusion context in conversation
        exclusion_context = None
        conversation_history = state.get("conversation_history", [])
        exclusion_keywords = ["exclude", "filter out", "don't need", "don't want", "not", "without", "avoid", "remove"]
        
        from utils.common.config import get_workflow_settings
        settings = get_workflow_settings()
        exclusion_check_turns = settings.get("exclusion_check_turns", 5)
        for turn in conversation_history[-exclusion_check_turns:]:
            if turn.role == "user":
                msg_lower = turn.content.lower()
                for keyword in exclusion_keywords:
                    if keyword in msg_lower:
                        exclusion_context = turn.content
                        break
                if exclusion_context:
                    break
        
        try:
            logger.info(f"Mapping industry to SIC codes: '{industry_description}'")
            industry_mapper = get_industry_mapper()
            sic_codes, mapping = industry_mapper.get_sic_codes_for_query(industry_description, exclusion_context)
            
            # Check if we got codes (mapping.codes is the list, sic_codes is formatted string)
            if not mapping.codes or len(mapping.codes) == 0:
                logger.warning(f"No SIC codes found for industry '{industry_description}'")
                state["sql_error"] = f"No SIC codes found for industry: {industry_description}"
                state["sql_valid"] = False
                return state
            
            logger.info(f"Successfully mapped '{industry_description}' to {len(mapping.codes)} SIC codes: {mapping.codes}")
            
            state["sic_context"] = {
                "industry_input": industry_description,
                "codes": mapping.codes,
                "rationale": mapping.rationale or "LLM provided these SIC codes based on domain knowledge."
            }
        
        except IndustryNotFoundError as e:
            logger.error(f"Industry not found: {e}")
            state["sql_error"] = str(e)
            state["sql_valid"] = False
            # Don't raise - let workflow continue to show error to user
        except Exception as e:
            logger.error(f"Error mapping industry '{industry_description}': {e}", exc_info=True)
            state["sql_error"] = f"Error mapping industry to SIC codes: {str(e)}"
            state["sql_valid"] = False
            # Don't raise - let workflow continue to show error to user
    
    return state


def map_title_node(state: WorkflowState) -> WorkflowState:
    """
    Map title to tier.
    Preservation rule: Only re-maps if title was mentioned in update request AND value changed, 
    otherwise preserves existing title_sql_condition (same pattern as all other filters).
    """
    extracted_info = state.get("extracted_info", {})
    title = extracted_info.get("title")
    mentioned_fields = state.get("mentioned_fields", [])
    is_update_request = state.get("sql_query") is not None
    
    # If this is an update request and title was NOT mentioned, preserve existing condition
    if is_update_request and "title" not in mentioned_fields:
        existing_condition = state.get("title_sql_condition")
        if existing_condition:
            logger.info(f"Title not mentioned in update - preserving existing title_sql_condition: {existing_condition}")
            return state
    
    if not title or is_empty_value(title):
        # If title is None/empty but we have existing title_sql_condition, preserve it
        existing_condition = state.get("title_sql_condition")
        if existing_condition:
            pass  # Preserve existing condition
        return state
    
    # If this is an update request and title was mentioned, check if value actually changed
    # by comparing with previous extraction history
    if is_update_request and "title" in mentioned_fields:
        extraction_history = state.get("extraction_history", [])
        if extraction_history:
            # Get the last extraction before this one (if exists)
            previous_extractions = [e for e in extraction_history[:-1] if e.get("extracted", {}).get("title")]
            if previous_extractions:
                previous_title = previous_extractions[-1].get("extracted", {}).get("title")
                if previous_title and previous_title.lower() == title.lower():
                    existing_condition = state.get("title_sql_condition")
                    if existing_condition:
                        logger.info(f"Title value unchanged ('{title}') - preserving existing title_sql_condition: {existing_condition}")
                        return state
    
    # Check if multiple titles (comma-separated)
    if "," in title:
        titles_list = [t.strip() for t in title.split(",")]
        
        # Map each title to tier and combine with OR
        title_tier_mapper = get_title_tier_mapper()
        tier_conditions = []
        
        for t in titles_list:
            condition = title_tier_mapper.generate_title_sql_condition(t)
            if condition:
                tier_conditions.append(condition)
        
        if tier_conditions:
            # Remove duplicates and combine with OR
            unique_conditions = list(set(tier_conditions))
            if len(unique_conditions) == 1:
                title_sql_condition = unique_conditions[0]
            else:
                title_sql_condition = f"({' OR '.join(unique_conditions)})"
            
            state["title_sql_condition"] = title_sql_condition
    else:
        # Single title
        title_tier_mapper = get_title_tier_mapper()
        title_sql_condition = title_tier_mapper.generate_title_sql_condition(title)
        
        if title_sql_condition:
            state["title_sql_condition"] = title_sql_condition
    
    return state

