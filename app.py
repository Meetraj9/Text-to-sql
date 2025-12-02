"""
Streamlit application for text-to-SQL pipeline using LangGraph workflow.
"""

import streamlit as st
import pandas as pd

from workflows import create_text_to_sql_workflow, create_initial_state
from workflows.state import WorkflowState
from utils.text_to_sql.industry_mapper import IndustryNotFoundError
from utils.text_to_sql.value_utils import get_empty_extracted_info
from utils.common.logger import setup_logger
from utils.common.db import execute_query, test_connection
from utils.common.config import get_workflow_settings
from langgraph.checkpoint.memory import MemorySaver

# Initialize logger
logger = setup_logger("app", log_level="INFO")


def initialize_session_state():
    """Initialize session state variables."""
    if "workflow_state" not in st.session_state:
        st.session_state.workflow_state = None
    if "workflow_compiled" not in st.session_state:
        st.session_state.workflow_compiled = None
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = "default"
    if "conversation" not in st.session_state:
        st.session_state.conversation = []


def reset_session_state():
    """Reset all session state variables to initial state - starts a completely new query."""
    logger.info("=" * 80)
    logger.info("🔄 RESETTING SESSION - Starting completely new query")
    logger.info("=" * 80)
    
    # Clear workflow state to force new workflow run
    st.session_state.workflow_state = None
    st.session_state.workflow_compiled = None
    st.session_state.thread_id = "default"
    st.session_state.conversation = []
    st.session_state.extracted_info = get_empty_extracted_info()
    st.session_state.sql_query = None
    st.session_state.sql_valid = None
    st.session_state.sql_error = None
    st.session_state.current_question = None
    st.session_state.sic_context = None
    
    logger.info("Session state reset complete - ready for completely new query")
    logger.info("=" * 80)


def get_workflow():
    """Get or initialize compiled workflow (cached in session state)."""
    if st.session_state.workflow_compiled is None:
        logger.info("Initializing LangGraph workflow")
        try:
            checkpoint_memory = MemorySaver()
            workflow = create_text_to_sql_workflow()
            st.session_state.workflow_compiled = workflow.compile(checkpointer=checkpoint_memory)
            logger.info("Workflow compiled successfully")
        except Exception as e:
            logger.error(f"Error initializing workflow: {e}", exc_info=True)
            st.error(f"Configuration error: {e}")
            st.info("Please make sure LLM_API_KEY is set in your .env file")
            st.stop()
    
    return st.session_state.workflow_compiled


def workflow_state_to_ui_state(workflow_state: WorkflowState) -> None:
    """Convert workflow state to UI session state for display."""
    # IMPORTANT: Also preserve the full workflow_state for next run
    # This ensures state persists between runs
    st.session_state.workflow_state = workflow_state
    
    # Update conversation display - include both conversation history and current question
    conversation_history = workflow_state.get("conversation_history", [])
    conversation_list = [
        (turn.role, turn.content) for turn in conversation_history
    ]
    
    # Add current question if it exists and hasn't been added yet
    current_question = workflow_state.get("current_question")
    if current_question:
        # Check if question is already in conversation
        if not any(msg == current_question for role, msg in conversation_list if role == "assistant"):
            conversation_list.append(("assistant", current_question))
    
    st.session_state.conversation = conversation_list
    
    # Update extracted info
    st.session_state.extracted_info = workflow_state.get("extracted_info", get_empty_extracted_info())
    
    # Update SQL query
    st.session_state.sql_query = workflow_state.get("sql_query")
    st.session_state.sql_valid = workflow_state.get("sql_valid")
    st.session_state.sql_error = workflow_state.get("sql_error")
    
    # Update current question
    st.session_state.current_question = workflow_state.get("current_question")
    
    # Update SIC context
    st.session_state.sic_context = workflow_state.get("sic_context")
    
    logger.debug(f"Workflow state preserved - SQL exists: {workflow_state.get('sql_query') is not None}")
    logger.debug(f"Workflow state preserved - extracted_info: {workflow_state.get('extracted_info')}")


def run_workflow(user_input: str) -> WorkflowState:
    """
    Run the workflow with user input.
    
    Args:
        user_input: User's input text
        
    Returns:
        Final workflow state
    """
    workflow = get_workflow()
    thread_id = st.session_state.thread_id
    
    # Configure for execution
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    try:
        # Check if we have existing workflow state
        has_existing_state = st.session_state.workflow_state is not None
        is_resuming_from_interrupt = has_existing_state and st.session_state.workflow_state.get("needs_human_input", False)
        has_sql_query = has_existing_state and st.session_state.workflow_state.get("sql_query") is not None
        
        # IMPORTANT: If SQL query exists, ANY new input is an update request (unless resuming from interrupt)
        is_update_request = has_sql_query and not is_resuming_from_interrupt
        
        logger.info("=" * 80)
        logger.info(f"Workflow state check:")
        logger.info(f"  - Has existing state: {has_existing_state}")
        logger.info(f"  - Resuming from interrupt: {is_resuming_from_interrupt}")
        logger.info(f"  - Has SQL query: {has_sql_query}")
        logger.info(f"  - Is update request: {is_update_request}")
        if has_existing_state:
            logger.info(f"  - Existing SQL query: {st.session_state.workflow_state.get('sql_query') is not None}")
            logger.info(f"  - Existing extracted_info: {st.session_state.workflow_state.get('extracted_info')}")
        logger.info("=" * 80)
        
        if is_resuming_from_interrupt:
            # Resume from interrupt - update state with new user input
            logger.info("RESUMING workflow from interrupt")
            logger.info(f"Previous state - needs_human_input: {st.session_state.workflow_state.get('needs_human_input')}")
            logger.info(f"Previous state - current_question: {st.session_state.workflow_state.get('current_question')}")
            
            current_state = st.session_state.workflow_state
            current_state["messages"].append({"role": "user", "content": user_input})
            current_state["needs_human_input"] = False  # Clear interrupt flag
            
            logger.info(f"User response to question: {user_input}")
            logger.info("Clearing needs_human_input flag - continuing workflow")
            
            # Continue workflow from where it left off
            result = workflow.invoke(
                current_state,
                config=config
            )
        elif is_update_request:
            # Update request - preserve existing state and add new user input
            logger.info("PROCESSING UPDATE REQUEST")
            logger.info(f"Existing SQL query exists - this is an update, not a new query")
            existing_state = st.session_state.workflow_state
            logger.info(f"Existing SQL: {existing_state.get('sql_query', '')[:100]}...")
            logger.info(f"Existing extracted_info: {existing_state.get('extracted_info')}")
            
            # Use deep copy to preserve all nested structures
            import copy
            current_state = copy.deepcopy(existing_state)
        
            # Add new user message
            current_state["messages"].append({"role": "user", "content": user_input})
            # Clear interrupt flags and set update mode
            current_state["needs_human_input"] = False
            current_state["current_question"] = None
            current_state["workflow_state"] = "updating"
            current_state["missing_fields"] = []  # Clear missing fields for update
            
            logger.info(f"Preserving existing extracted_info: {current_state.get('extracted_info')}")
            logger.info(f"Adding new user message: {user_input}")
            logger.info(f"State preserved - SQL exists: {current_state.get('sql_query') is not None}")
            
            # Run workflow with preserved state
            result = workflow.invoke(
                current_state,
                config=config
            )
        else:
            # New workflow run
            logger.info("STARTING new workflow run")
            logger.info(f"User input: {user_input}")
            initial_state = create_initial_state(user_input)
            result = workflow.invoke(
                initial_state,
                config=config
            )
        
        # Check if workflow is waiting for human input (interrupt)
        if result.get("needs_human_input"):
            logger.info("=" * 80)
            logger.info("⚠️  WORKFLOW PAUSED - Waiting for human input")
            logger.info(f"Question generated: {result.get('current_question')}")
            logger.info(f"Missing fields: {result.get('missing_fields')}")
            logger.info(f"Current extracted info: {result.get('extracted_info')}")
            logger.info("=" * 80)
            # Workflow will pause here, state is saved in checkpoint
        else:
            logger.info("=" * 80)
            logger.info("✅ WORKFLOW COMPLETED")
            logger.info(f"SQL query generated: {result.get('sql_query') is not None}")
            logger.info(f"SQL valid: {result.get('sql_valid')}")
            if result.get('sql_query'):
                logger.info(f"SQL: {result.get('sql_query')[:100]}...")
            logger.info(f"Final extracted info: {result.get('extracted_info')}")
            logger.info("=" * 80)
        
        # CRITICAL: Save workflow state for next run
        # This ensures state persists between user inputs
        st.session_state.workflow_state = result
        workflow_state_to_ui_state(result)
        
        logger.info(f"Workflow state saved - will be available for next run")
        logger.info(f"  - SQL exists: {result.get('sql_query') is not None}")
        logger.info(f"  - Extracted info keys: {list(result.get('extracted_info', {}).keys())}")
        
        return result
        
    except IndustryNotFoundError as e:
        logger.error(f"Industry not found: {e}")
        # Update state with error
        if st.session_state.workflow_state:
            st.session_state.workflow_state["sql_error"] = str(e)
            st.session_state.workflow_state["sql_valid"] = False
            workflow_state_to_ui_state(st.session_state.workflow_state)
        st.error(str(e))
        return st.session_state.workflow_state
    except Exception as e:
        logger.error(f"Error running workflow: {e}", exc_info=True)
        st.error(f"Error: {str(e)}")
        return st.session_state.workflow_state if st.session_state.workflow_state else None


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Text-to-SQL ICP Builder",
        page_icon="🔍",
        layout="wide"
    )
    
    # Test database connection on startup
    if "db_connection_tested" not in st.session_state:
        logger.info("Testing database connection on startup...")
        success, message, install_command = test_connection()
        if not success:
            logger.error(f"Database connection test failed: {message}")
            
            # Build error message with install command if available
            error_message = f"❌ **Database Connection Failed**\n\n{message}\n\n"
            
            if install_command:
                error_message += f"**Missing Database Driver**\n\n"
                error_message += f"Install the required driver by running:\n\n"
                error_message += f"```bash\n{install_command}\n```\n\n"
                error_message += f"Then restart the application.\n\n"
            
            error_message += "**Troubleshooting:**\n"
            error_message += "- Check your database configuration in `.env` file\n"
            error_message += "- Ensure the database is running\n"
            error_message += "- Verify network connectivity to the database\n"
            
            st.error(error_message)
            st.stop()
        else:
            logger.info(f"Database connection test passed: {message}")
            st.session_state.db_connection_tested = True
    
    st.title("🔍 Text-to-SQL ICP Builder")
    st.markdown("Build your Ideal Customer Profile and generate SQL queries")
    
    initialize_session_state()
    
    # Sidebar for conversation history
    with st.sidebar:
        st.header("💬 Conversation History")
        if st.session_state.conversation:
            for role, message in st.session_state.conversation:
                if role == "user":
                    st.markdown(f"**You:** {message}")
                else:
                    st.markdown(f"**Copilot:** {message}")
        else:
            st.info("No conversation yet")
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("💬 Conversation")
        
        # Welcome message
        if not st.session_state.conversation:
            st.info("👋 Welcome! Let's build your first audience together. What products or services do you offer?")
        
        # Display conversation
        for role, message in st.session_state.conversation:
            if role == "user":
                st.markdown(f"**You:** {message}")
            else:
                st.markdown(f"**Copilot:** {message}")
        
        # Show current question if it exists and hasn't been added to conversation yet
        if st.session_state.get("current_question"):
            question = st.session_state.current_question
            # Check if this question is already in conversation
            if not any(msg == question for role, msg in st.session_state.conversation if role == "assistant"):
                st.info(f"**Copilot:** {question}")
            st.markdown("---")
        
        # User input using form to properly clear input
        if st.session_state.get("current_question"):
            placeholder_text = "Type your answer here..."
        elif st.session_state.get("sql_query"):
            placeholder_text = "Modify filters (e.g., 'add New York', 'remove employee size', 'change to California only')..."
        else:
            placeholder_text = "What products or services do you offer?"
        
        with st.form("user_input_form", clear_on_submit=True):
            user_input = st.text_input(
                "Your response:",
                key="user_input",
                placeholder=placeholder_text
            )
            submit_button = st.form_submit_button("Send", type="primary")
        
        # Handle user input
        if submit_button and user_input:
            input_text = user_input.strip()
            logger.info(f"User input received: {input_text}")
            
            # Run workflow
            result = run_workflow(input_text)
                
            if result:
                st.rerun()
        
        # Reset button
        if st.button("🔄 Start New Query"):
            logger.info("User reset the session - starting new query")
            reset_session_state()
            st.rerun()
    
    with col2:
        st.header("📊 Generated SQL Query")
        
        if st.session_state.get("sql_query"):
            # Display validation status
            if st.session_state.get("sql_valid"):
                st.success("✅ SQL Query is Valid")
                
                # Execute query and get results
                try:
                    settings = get_workflow_settings()
                    max_results = settings.get("sql_query_max_results", 5)
                    results, total_count = execute_query(st.session_state.sql_query, max_rows=max_results)
                    
                    # Display results summary right after validation
                    if results:
                        # Generate summary statement
                        extracted_info = st.session_state.get("extracted_info", {})
                        summary_parts = []
                        
                        geography = extracted_info.get("geography")
                        if geography:
                            summary_parts.append(f"**{geography}**")
                        
                        industry = extracted_info.get("industry")
                        if industry:
                            summary_parts.append(f"**{industry}**")
                        
                        title = extracted_info.get("title")
                        if title:
                            summary_parts.append(f"**{title}**")
                        
                        employee_size = extracted_info.get("employee_size")
                        if employee_size:
                            summary_parts.append(f"**{employee_size} employees**")
                        
                        sales_volume = extracted_info.get("sales_volume")
                        if sales_volume:
                            summary_parts.append(f"**sales < {sales_volume}**")
                        
                        if summary_parts:
                            summary_text = f"Found **{total_count:,}** companies matching: {', '.join(summary_parts)}"
                        else:
                            summary_text = f"Found **{total_count:,}** companies"
                        
                        st.markdown(f"📊 {summary_text}")
                    else:
                        st.warning("📊 No results found for this query.")
                        
                except Exception as e:
                    logger.error(f"Error executing query: {e}", exc_info=True)
                    st.error(f"Error executing query: {str(e)}")
                    results = None
                    total_count = 0
            else:
                st.error(f"❌ SQL Query is Invalid: {st.session_state.get('sql_error', 'Unknown error')}")
                results = None
                total_count = 0
            
            # Display SQL query
            st.code(st.session_state.sql_query, language="sql")
            
            # Display results table if valid and results exist
            if st.session_state.get("sql_valid") and results:
                st.subheader("📋 Query Results")
                
                # Convert to DataFrame for better display
                df = pd.DataFrame(results)
                # Exclude created_at column from display
                if 'created_at' in df.columns:
                    df = df.drop(columns=['created_at'])
                st.dataframe(df, width='stretch')
                
                # Show count information
                if total_count > len(results):
                    st.info(f"📊 Showing {len(results)} of {total_count:,} total rows")
                else:
                    st.success(f"📊 Total rows: {total_count:,}")
                                
            sic_context = st.session_state.get("sic_context")
            if sic_context and sic_context.get("codes"):
                st.subheader("🧠 SIC Code Selection")
                st.markdown(f"**User industry input:** {sic_context.get('industry_input', 'N/A')}")
                st.markdown(f"**SIC codes used:** {', '.join(sic_context['codes'])}")
                rationale = sic_context.get("rationale")
                if rationale:
                    st.markdown(f"**Reasoning:** {rationale}")
                else:
                    st.info("LLM supplied these SIC codes based on its internal taxonomy knowledge.")
            
            # Copy button
            st.button("📋 Copy SQL", on_click=lambda: st.write("SQL copied to clipboard!"))
        else:
            st.info("SQL query will appear here after you provide all required information.")


if __name__ == "__main__":
    main()
