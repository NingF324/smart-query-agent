"""
LangGraph Workflow Definition
"""
import logging
from typing import Literal
from langchain_core.runnables.graph import StateGraph, END, START
from agent.state import AgentState, create_initial_state

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define workflow node names
NODE_INTENT_PARSE = "intent_parse"
NODE_SCHEMA_RETRIEVE = "schema_retrieve"
NODE_SQL_GENERATE = "sql_generate"
NODE_SQL_VALIDATE = "sql_validate"
NODE_SQL_EXECUTE = "sql_execute"
NODE_RESULT_INTERPRET = "result_interpret"


def build_graph():
    """
    Build the intelligent query agent workflow using LangGraph

    Returns:
        CompiledGraph: Compiled workflow graph
    """
    logger.info("[Graph] Building agent workflow...")

    try:
        # Import node functions
        from agent.nodes import (
            intent_parse_node,
            schema_retrieve_node,
            sql_generate_node,
            sql_validate_node,
            sql_execute_node,
            result_interpret_node
        )

        # Create state graph
        workflow = StateGraph(AgentState)

        # Add all nodes
        workflow.add_node(NODE_INTENT_PARSE, intent_parse_node)
        workflow.add_node(NODE_SCHEMA_RETRIEVE, schema_retrieve_node)
        workflow.add_node(NODE_SQL_GENERATE, sql_generate_node)
        workflow.add_node(NODE_SQL_VALIDATE, sql_validate_node)
        workflow.add_node(NODE_SQL_EXECUTE, sql_execute_node)
        workflow.add_node(NODE_RESULT_INTERPRET, result_interpret_node)

        # Set entry point
        workflow.set_entry_point(NODE_INTENT_PARSE)

        # Define workflow edges (linear flow)
        workflow.add_edge(NODE_INTENT_PARSE, NODE_SCHEMA_RETRIEVE)
        workflow.add_edge(NODE_SCHEMA_RETRIEVE, NODE_SQL_GENERATE)
        workflow.add_edge(NODE_SQL_GENERATE, NODE_SQL_VALIDATE)
        workflow.add_edge(NODE_SQL_VALIDATE, NODE_SQL_EXECUTE)
        workflow.add_edge(NODE_SQL_EXECUTE, NODE_RESULT_INTERPRET)

        # Add conditional edges: retry SQL generation if validation fails
        workflow.add_conditional_edges(
            NODE_SQL_VALIDATE,
            {
                "valid": NODE_SQL_EXECUTE,
                "invalid": NODE_RESULT_INTERPRET
            },
            should_retry_sql
        )

        # Compile graph
        compiled_graph = workflow.compile()

        logger.info("[Graph] Workflow compiled successfully")
        return compiled_graph

    except Exception as e:
        logger.error(f"[Graph] Failed to build workflow: {e}")
        raise


def should_retry_sql(state: AgentState) -> Literal["sql_generate", "result_interpret", END]:
    """
    Determine if SQL generation should be retried

    Args:
        state: Current state

    Returns:
        str: Next node name
    """
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    validation_result = state.get("validation_result", {})
    error_type = state.get("error_type")

    logger.info(f"[Route] Retry check: count={retry_count}, max={max_retries}, error_type={error_type}")

    # If max retries reached, end
    if retry_count >= max_retries:
        logger.warning(f"[Route] Max retries ({max_retries}) reached, ending")
        return END

    # If error type is unfixable, end directly
    if error_type in ["syntax_error", "permission_error", "unknown_error"]:
        logger.warning(f"[Route] Unfixable error: {error_type}, ending")
        return END

    # If SQL validation failed, check if can retry
    is_valid = validation_result.get("valid", False)
    if not is_valid:
        # If it's an execution error, retry SQL generation
        if error_type == "execution_error":
            logger.info("[Route] Execution error, retrying SQL generation")
            # Increment retry count
            state["retry_count"] = retry_count + 1
            return "sql_generate"

    # Default: proceed to result interpretation
    logger.info("[Route] Proceeding to result interpretation")
    return "result_interpret"


def get_graph_info():
    """
    Get workflow information

    Returns:
        dict: Workflow configuration information
    """
    return {
        "nodes": [
            NODE_INTENT_PARSE,
            NODE_SCHEMA_RETRIEVE,
            NODE_SQL_GENERATE,
            NODE_SQL_VALIDATE,
            NODE_SQL_EXECUTE,
            NODE_RESULT_INTERPRET
        ],
        "edges": [
            (NODE_INTENT_PARSE, NODE_SCHEMA_RETRIEVE),
            (NODE_SCHEMA_RETRIEVE, NODE_SQL_GENERATE),
            (NODE_SQL_GENERATE, NODE_SQL_VALIDATE),
            (NODE_SQL_VALIDATE, NODE_SQL_EXECUTE),
            (NODE_SQL_EXECUTE, NODE_RESULT_INTERPRET)
        ],
        "entry_point": NODE_INTENT_PARSE,
        "max_retries": 3,
        "conditional_edges": {
            NODE_SQL_VALIDATE: should_retry_sql.__name__
        }
    }


def print_graph_flow():
    """
    Print workflow flow information
    """
    info = get_graph_info()

    print("\n" + "="*60)
    print("Agent Workflow Flow")
    print("="*60)

    print("\nNodes:")
    for node in info["nodes"]:
        print(f"  - {node}")

    print("\nEdges:")
    for edge in info["edges"]:
        print(f"  - {edge[0]} -> {edge[1]}")

    print(f"\nEntry Point: {info['entry_point']}")
    print(f"Max Retries: {info['max_retries']}")

    print("\nConditional Routing:")
    print(f"  From {NODE_SQL_VALIDATE}:")
    print(f"    - valid -> {NODE_SQL_EXECUTE}")
    print(f"    - invalid -> {should_retry_sql.__name__}")

    print("\n" + "="*60)


if __name__ == "__main__":
    print_graph_flow()
