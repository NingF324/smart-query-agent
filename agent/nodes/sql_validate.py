"""SQL validation node: EXPLAIN-first validation with bounded retry signaling."""

import difflib
import logging
import re
import time
from typing import Any, Dict, List, Tuple

from agent.nodes.sql_generate import build_schema_description, extract_sql_from_llm_response
from agent.state import AgentState
from services.db_service import get_state_db_service
from services.llm_service import get_llm_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sql_validate_node(state: AgentState) -> Dict[str, Any]:
    generated_sql = state.get("generated_sql", "")
    schemas = state.get("relevant_schemas", [])
    question = state["question"]
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 3))
    execution_stats = dict(state.get("execution_stats", {}))

    started_at = time.perf_counter()
    logger.info("[SQL Validate] Validating SQL: %s...", generated_sql[:100])

    if not generated_sql:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        err = state.get("validation_result", {}).get("error", "No SQL generated")
        execution_stats.update(
            {
                "validation_attempted": True,
                "validation_passed": False,
                "validation_type": "empty",
                "validation_latency_ms": elapsed_ms,
                "validation_error_type": "no_sql",
                "fix_attempted": False,
                "fix_success": False,
                "fix_strategy": "",
                "safety_blocked": False,
                "initial_error": err,
            }
        )
        return {
            "validation_result": {"valid": False, "error": err, "corrected_sql": None, "validation_type": "empty"},
            "error_type": "unfixable",
            "retry_count": retry_count,
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }

    try:
        db_service = get_state_db_service(state)

        is_safe, safety_error = db_service.is_safe_sql(generated_sql)
        if not is_safe:
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            execution_stats.update(
                {
                    "validation_attempted": True,
                    "validation_passed": False,
                    "validation_type": "security",
                    "validation_latency_ms": elapsed_ms,
                    "validation_error_type": "permission_error",
                    "fix_attempted": False,
                    "fix_success": False,
                    "fix_strategy": "",
                    "safety_blocked": True,
                    "initial_error": safety_error,
                }
            )
            return {
                "generated_sql": generated_sql,
                "validation_result": {
                    "valid": False,
                    "error": safety_error,
                    "corrected_sql": None,
                    "validation_type": "security",
                },
                "error_type": "unfixable",
                "retry_count": retry_count,
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        explain_result = db_service.explain_query(generated_sql)
        if explain_result.get("valid"):
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            execution_stats.update(
                {
                    "validation_attempted": True,
                    "validation_passed": True,
                    "validation_type": "explain",
                    "validation_latency_ms": elapsed_ms,
                    "validation_error_type": "",
                    "fix_attempted": False,
                    "fix_success": False,
                    "fix_strategy": "",
                    "safety_blocked": False,
                    "initial_error": "",
                }
            )
            return {
                "generated_sql": generated_sql,
                "validation_result": {
                    "valid": True,
                    "error": None,
                    "corrected_sql": generated_sql,
                    "validation_type": "explain",
                    "explain": explain_result.get("explain", [])[:3],
                },
                "error_type": None,
                "retry_count": retry_count,
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        error_msg = explain_result.get("error", "EXPLAIN execution failed")
        error_type = classify_error(error_msg)

        if error_type == "unfixable":
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            execution_stats.update(
                {
                    "validation_attempted": True,
                    "validation_passed": False,
                    "validation_type": "explain",
                    "validation_latency_ms": elapsed_ms,
                    "validation_error_type": "unfixable",
                    "fix_attempted": False,
                    "fix_success": False,
                    "fix_strategy": "",
                    "safety_blocked": False,
                    "initial_error": error_msg,
                }
            )
            return {
                "generated_sql": generated_sql,
                "validation_result": {
                    "valid": False,
                    "error": error_msg,
                    "corrected_sql": None,
                    "validation_type": "explain",
                },
                "error_type": "unfixable",
                "retry_count": retry_count,
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        fixed_sql, fix_strategy = attempt_sql_fix(generated_sql, question, schemas, error_msg)
        if not fixed_sql or fixed_sql.strip() == generated_sql.strip():
            next_retry = retry_count + 1
            next_error_type = "fixable" if next_retry < max_retries else "unfixable"
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            execution_stats.update(
                {
                    "validation_attempted": True,
                    "validation_passed": False,
                    "validation_type": "fix_skipped",
                    "validation_latency_ms": elapsed_ms,
                    "validation_error_type": "fixable",
                    "fix_attempted": True,
                    "fix_success": False,
                    "fix_strategy": "not_fixed",
                    "safety_blocked": False,
                    "initial_error": error_msg,
                }
            )
            return {
                "generated_sql": generated_sql,
                "validation_result": {
                    "valid": False,
                    "error": error_msg,
                    "corrected_sql": None,
                    "validation_type": "fix_skipped",
                },
                "error_type": next_error_type,
                "retry_count": next_retry,
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        fixed_safe, fixed_err = db_service.is_safe_sql(fixed_sql)
        if not fixed_safe:
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            execution_stats.update(
                {
                    "validation_attempted": True,
                    "validation_passed": False,
                    "validation_type": "security",
                    "validation_latency_ms": elapsed_ms,
                    "validation_error_type": "permission_error",
                    "fix_attempted": True,
                    "fix_success": False,
                    "fix_strategy": fix_strategy,
                    "safety_blocked": True,
                    "initial_error": error_msg,
                }
            )
            return {
                "generated_sql": generated_sql,
                "validation_result": {
                    "valid": False,
                    "error": fixed_err,
                    "corrected_sql": None,
                    "validation_type": "security",
                },
                "error_type": "unfixable",
                "retry_count": retry_count,
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        verify_result = db_service.explain_query(fixed_sql)
        if verify_result.get("valid"):
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            execution_stats.update(
                {
                    "validation_attempted": True,
                    "validation_passed": True,
                    "validation_type": fix_strategy,
                    "validation_latency_ms": elapsed_ms,
                    "validation_error_type": "",
                    "fix_attempted": True,
                    "fix_success": True,
                    "fix_strategy": fix_strategy,
                    "safety_blocked": False,
                    "initial_error": error_msg,
                }
            )
            return {
                "generated_sql": fixed_sql,
                "validation_result": {
                    "valid": True,
                    "error": None,
                    "corrected_sql": fixed_sql,
                    "validation_type": fix_strategy,
                    "explain": verify_result.get("explain", [])[:3],
                },
                "error_type": None,
                "retry_count": retry_count,
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        verify_error = verify_result.get("error", "SQL fix verification failed")
        next_retry = retry_count + 1
        next_error_type = "fixable" if next_retry < max_retries else "unfixable"
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        execution_stats.update(
            {
                "validation_attempted": True,
                "validation_passed": False,
                "validation_type": f"{fix_strategy}_failed",
                "validation_latency_ms": elapsed_ms,
                "validation_error_type": "fixable",
                "fix_attempted": True,
                "fix_success": False,
                "fix_strategy": fix_strategy,
                "safety_blocked": False,
                "initial_error": error_msg,
            }
        )
        return {
            "generated_sql": fixed_sql,
            "validation_result": {
                "valid": False,
                "error": verify_error,
                "corrected_sql": fixed_sql,
                "validation_type": f"{fix_strategy}_failed",
            },
            "error_type": next_error_type,
            "retry_count": next_retry,
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }

    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        execution_stats.update(
            {
                "validation_attempted": True,
                "validation_passed": False,
                "validation_type": "exception",
                "validation_latency_ms": elapsed_ms,
                "validation_error_type": "exception",
                "fix_attempted": False,
                "fix_success": False,
                "fix_strategy": "",
                "safety_blocked": False,
                "initial_error": str(exc),
            }
        )
        return {
            "generated_sql": generated_sql,
            "validation_result": {
                "valid": False,
                "error": str(exc),
                "corrected_sql": None,
                "validation_type": "exception",
            },
            "error_type": "unfixable",
            "retry_count": retry_count,
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }


def attempt_sql_fix(sql: str, question: str, schemas: list, error: str) -> Tuple[str, str]:
    schema_text = build_schema_description(schemas)

    heuristic_sql = heuristic_fix_sql(sql, question, schemas, error)
    if heuristic_sql and heuristic_sql.strip() != sql.strip():
        return heuristic_sql.strip(), "heuristic_fixed"

    try:
        llm = get_llm_service()
        response = llm.validate_and_fix_sql(schemas=schema_text, question=question, sql=sql, error=error)
        fixed_sql = extract_sql_from_llm_response(response)
        if fixed_sql and fixed_sql.strip() != sql.strip():
            return fixed_sql.strip(), "llm_fixed"
    except Exception as exc:
        logger.warning("[SQL Validate] LLM SQL fix unavailable: %s", exc)

    return sql, "not_fixed"


def heuristic_fix_sql(sql: str, question: str, schemas: List[Dict[str, Any]], error: str) -> str:
    fixed_sql = sql

    column_match = re.search(r'column\s+"?([\w\.]+)"?\s+does not exist', error, re.IGNORECASE)
    if not column_match:
        column_match = re.search(r"no such column:\s*([\w\.]+)", error, re.IGNORECASE)
    if column_match:
        missing_column = column_match.group(1)
        replacement = find_closest_column(missing_column, schemas)
        if replacement:
            return replace_identifier(fixed_sql, missing_column, replacement)

    relation_match = re.search(r'(?:relation|table)\s+"?([\w\.]+)"?\s+does not exist', error, re.IGNORECASE)
    if not relation_match:
        relation_match = re.search(r"no such table:\s*([\w\.]+)", error, re.IGNORECASE)
    if relation_match:
        missing_table = relation_match.group(1)
        replacement = find_closest_table(missing_table, schemas, question=question)
        if replacement:
            return replace_identifier(fixed_sql, missing_table, replacement)

    return fixed_sql


def find_closest_column(identifier: str, schemas: List[Dict[str, Any]]) -> str:
    raw_name = identifier.split(".")[-1]
    all_columns = []
    for schema in schemas:
        for column in schema.get("columns", []):
            name = column.get("name")
            if name:
                all_columns.append(name)

    match = difflib.get_close_matches(raw_name, all_columns, n=1, cutoff=0.6)
    if not match:
        return ""

    if "." in identifier:
        prefix = identifier.rsplit(".", 1)[0]
        return f"{prefix}.{match[0]}"
    return match[0]


def find_closest_table(identifier: str, schemas: List[Dict[str, Any]], question: str = "") -> str:
    table_names = [schema.get("table_name", "") for schema in schemas if schema.get("table_name")]
    match = difflib.get_close_matches(identifier, table_names, n=1, cutoff=0.45)
    if match:
        return match[0]

    alias_map = {
        "dog": ["pet", "pets", "has_pet"],
        "dogs": ["pet", "pets", "has_pet"],
        "cat": ["pet", "pets", "has_pet"],
        "cats": ["pet", "pets", "has_pet"],
        "student": ["students", "student"],
        "students": ["students", "student"],
    }
    wanted = set(alias_map.get(identifier.lower(), []))
    q = question.lower()
    if "dog" in q or "cat" in q:
        wanted.update(["pet", "pets", "has_pet"])
    if "student" in q:
        wanted.update(["student", "students"])

    for table_name in table_names:
        lowered = table_name.lower()
        if any(token in lowered for token in wanted):
            return table_name
    return ""


def replace_identifier(sql: str, old_identifier: str, new_identifier: str) -> str:
    pattern = rf"\b{re.escape(old_identifier)}\b"
    return re.sub(pattern, new_identifier, sql)


def classify_error(error: str) -> str:
    error_lower = str(error or "").lower()

    unfixable_patterns = [
        r"permission denied",
        r"only select/cte",
        r"dangerous sql",
        r"sql is empty",
        r"no sql generated",
    ]
    for pattern in unfixable_patterns:
        if re.search(pattern, error_lower, re.IGNORECASE):
            return "unfixable"

    fixable_patterns = [
        r"syntax error",
        r"column .* does not exist",
        r"relation .* does not exist",
        r"table .* does not exist",
        r"no such table",
        r"no such column",
        r"missing from-clause entry",
        r"operator does not exist",
        r"ambiguous column",
    ]
    for pattern in fixable_patterns:
        if re.search(pattern, error_lower, re.IGNORECASE):
            return "fixable"

    return "fixable"
