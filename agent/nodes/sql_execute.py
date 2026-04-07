"""SQL execution node: execute SQL and classify runtime errors."""

import logging
import time
from typing import Any, Dict

from agent.state import AgentState
from services.db_service import get_state_db_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sql_execute_node(state: AgentState) -> Dict[str, Any]:
    generated_sql = state.get("generated_sql", "")
    execution_stats = dict(state.get("execution_stats", {}))
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 3))

    logger.info("[SQL Execute] Executing SQL: %s...", generated_sql[:100])
    started_at = time.perf_counter()

    if not generated_sql:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        execution_stats.update(
            {
                "execution_attempted": False,
                "execution_success": False,
                "execution_error": "No SQL generated",
                "execution_latency_ms": elapsed_ms,
                "execution_error_type": "no_sql",
            }
        )
        return {
            "query_result": [],
            "validation_result": {"valid": False, "error": "No SQL generated"},
            "error_type": "no_sql",
            "retry_count": retry_count,
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }

    try:
        db_service = get_state_db_service(state)
        result = db_service.execute_query(generated_sql)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)

        execution_stats.update(
            {
                "execution_attempted": True,
                "execution_success": True,
                "execution_error": "",
                "execution_latency_ms": elapsed_ms,
                "execution_error_type": "",
            }
        )
        return {
            "query_result": result,
            "validation_result": {"valid": True},
            "error_type": None,
            "retry_count": retry_count,
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }

    except ValueError as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        execution_stats.update(
            {
                "execution_attempted": True,
                "execution_success": False,
                "execution_error": str(exc),
                "execution_latency_ms": elapsed_ms,
                "execution_error_type": "permission_error",
            }
        )
        return {
            "query_result": [],
            "validation_result": {"valid": False, "error": str(exc)},
            "error_type": "permission_error",
            "retry_count": retry_count,
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }

    except TimeoutError as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        next_retry = retry_count + 1
        next_error_type = "execution_error" if next_retry < max_retries else "unfixable"
        execution_stats.update(
            {
                "execution_attempted": True,
                "execution_success": False,
                "execution_error": f"Query timeout: {exc}",
                "execution_latency_ms": elapsed_ms,
                "execution_error_type": "timeout",
            }
        )
        return {
            "query_result": [],
            "validation_result": {"valid": False, "error": f"Query timeout: {exc}"},
            "error_type": next_error_type,
            "retry_count": next_retry,
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }

    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        next_retry = retry_count + 1
        next_error_type = "execution_error" if next_retry < max_retries else "unfixable"
        execution_stats.update(
            {
                "execution_attempted": True,
                "execution_success": False,
                "execution_error": str(exc),
                "execution_latency_ms": elapsed_ms,
                "execution_error_type": "execution_error",
            }
        )
        return {
            "query_result": [],
            "validation_result": {"valid": False, "error": str(exc)},
            "error_type": next_error_type,
            "retry_count": next_retry,
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }
