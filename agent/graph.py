"""
LangGraph Workflow Definition
"""
import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agent.state import AgentState


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


NODE_INTENT_PARSE = "intent_parse"
NODE_SCHEMA_RETRIEVE = "schema_retrieve"
NODE_SQL_GENERATE = "sql_generate"
NODE_SQL_VALIDATE = "sql_validate"
NODE_SQL_EXECUTE = "sql_execute"
NODE_RESULT_INTERPRET = "result_interpret"
NODE_ERROR_RESPONSE = "error_response"


class GraphInfo(TypedDict):
    nodes: list[str]
    edges: list[tuple[str, str]]
    entry_point: str
    max_retries: int
    conditional_routes: dict[str, dict[str, str]]


def build_graph():
    """Build the intelligent query agent workflow using LangGraph."""
    logger.info("[Graph] Building agent workflow...")

    try:
        from agent.nodes import (
            error_response_node,
            intent_parse_node,
            result_interpret_node,
            schema_retrieve_node,
            sql_execute_node,
            sql_generate_node,
            sql_validate_node,
        )

        workflow = StateGraph(AgentState)

        workflow.add_node(NODE_INTENT_PARSE, intent_parse_node)
        workflow.add_node(NODE_SCHEMA_RETRIEVE, schema_retrieve_node)
        workflow.add_node(NODE_SQL_GENERATE, sql_generate_node)
        workflow.add_node(NODE_SQL_VALIDATE, sql_validate_node)
        workflow.add_node(NODE_SQL_EXECUTE, sql_execute_node)
        workflow.add_node(NODE_RESULT_INTERPRET, result_interpret_node)
        workflow.add_node(NODE_ERROR_RESPONSE, error_response_node)

        workflow.add_edge(START, NODE_INTENT_PARSE)
        workflow.add_edge(NODE_INTENT_PARSE, NODE_SCHEMA_RETRIEVE)
        workflow.add_edge(NODE_SCHEMA_RETRIEVE, NODE_SQL_GENERATE)
        workflow.add_edge(NODE_SQL_GENERATE, NODE_SQL_VALIDATE)
        workflow.add_conditional_edges(
            NODE_SQL_VALIDATE,
            should_retry_sql,
            {
                NODE_SQL_EXECUTE: NODE_SQL_EXECUTE,
                NODE_SQL_GENERATE: NODE_SQL_GENERATE,
                NODE_ERROR_RESPONSE: NODE_ERROR_RESPONSE,
            },
        )
        workflow.add_conditional_edges(
            NODE_SQL_EXECUTE,
            should_retry_execution,
            {
                NODE_RESULT_INTERPRET: NODE_RESULT_INTERPRET,
                NODE_SQL_GENERATE: NODE_SQL_GENERATE,
                NODE_ERROR_RESPONSE: NODE_ERROR_RESPONSE,
            },
        )
        workflow.add_edge(NODE_RESULT_INTERPRET, END)
        workflow.add_edge(NODE_ERROR_RESPONSE, END)

        compiled_graph = workflow.compile()
        logger.info("[Graph] Workflow compiled successfully")
        return compiled_graph

    except Exception as e:
        logger.error(f"[Graph] Failed to build workflow: {e}")
        raise


def should_retry_sql(state: AgentState) -> str:
    """Determine the next step after SQL validation."""
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    validation_result = state.get("validation_result", {})
    error_type = state.get("error_type")
    is_valid = validation_result.get("valid", False)

    logger.info(
        f"[Route][Validate] count={retry_count}, max={max_retries}, error_type={error_type}, valid={is_valid}"
    )

    if is_valid:
        return NODE_SQL_EXECUTE

    if error_type == "fixable" and retry_count < max_retries:
        state["retry_count"] = retry_count + 1
        logger.info("[Route][Validate] Fixable error detected, retrying SQL generation")
        return NODE_SQL_GENERATE

    logger.info("[Route][Validate] Validation failed, entering error response")
    return NODE_ERROR_RESPONSE


def should_retry_execution(state: AgentState) -> str:
    """Determine the next step after SQL execution."""
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    validation_result = state.get("validation_result", {})
    error_type = state.get("error_type")
    is_valid = validation_result.get("valid", False)

    logger.info(
        f"[Route][Execute] count={retry_count}, max={max_retries}, error_type={error_type}, valid={is_valid}"
    )

    if is_valid:
        return NODE_RESULT_INTERPRET

    if error_type == "execution_error" and retry_count < max_retries:
        state["retry_count"] = retry_count + 1
        logger.info("[Route][Execute] Execution error detected, retrying SQL generation")
        return NODE_SQL_GENERATE

    logger.info("[Route][Execute] Execution failed, entering error response")
    return NODE_ERROR_RESPONSE


def get_graph_info() -> GraphInfo:
    """Get workflow information."""
    return {
        "nodes": [
            NODE_INTENT_PARSE,
            NODE_SCHEMA_RETRIEVE,
            NODE_SQL_GENERATE,
            NODE_SQL_VALIDATE,
            NODE_SQL_EXECUTE,
            NODE_RESULT_INTERPRET,
            NODE_ERROR_RESPONSE,
        ],
        "edges": [
            ("START", NODE_INTENT_PARSE),
            (NODE_INTENT_PARSE, NODE_SCHEMA_RETRIEVE),
            (NODE_SCHEMA_RETRIEVE, NODE_SQL_GENERATE),
            (NODE_SQL_GENERATE, NODE_SQL_VALIDATE),
            (NODE_RESULT_INTERPRET, "END"),
            (NODE_ERROR_RESPONSE, "END"),
        ],
        "entry_point": NODE_INTENT_PARSE,
        "max_retries": 3,
        "conditional_routes": {
            NODE_SQL_VALIDATE: {
                "valid": NODE_SQL_EXECUTE,
                "fixable_with_retry": NODE_SQL_GENERATE,
                "other": NODE_ERROR_RESPONSE,
            },
            NODE_SQL_EXECUTE: {
                "valid": NODE_RESULT_INTERPRET,
                "execution_error_with_retry": NODE_SQL_GENERATE,
                "other": NODE_ERROR_RESPONSE,
            },
        },
    }


def print_graph_flow():
    """Print workflow flow information."""
    info = get_graph_info()

    print("\n" + "=" * 60)
    print("Agent Workflow Flow")
    print("=" * 60)

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
    print(f"    - fixable_with_retry -> {NODE_SQL_GENERATE}")
    print(f"    - other -> {NODE_ERROR_RESPONSE}")
    print(f"  From {NODE_SQL_EXECUTE}:")
    print(f"    - valid -> {NODE_RESULT_INTERPRET}")
    print(f"    - execution_error_with_retry -> {NODE_SQL_GENERATE}")
    print(f"    - other -> {NODE_ERROR_RESPONSE}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_graph_flow()
