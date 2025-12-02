"""
Update handling node.
"""

from workflows.state import WorkflowState


def handle_update_node(state: WorkflowState) -> WorkflowState:
    """
    Handle update requests by clearing old SQL and preparing for regeneration.
    This node ensures that after an update, SQL will be regenerated with new parameters.
    """
    # Clear old SQL query so it gets regenerated
    state["sql_query"] = None
    state["sql_valid"] = None
    state["sql_error"] = None
    
    return state

