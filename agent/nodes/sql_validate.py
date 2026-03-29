"""
SQL 校验节点 - 使用 EXPLAIN 和 LLM 修复 SQL 错误
"""
import difflib
import logging
import re
from typing import Any, Dict, List, Tuple

from agent.state import AgentState
from agent.nodes.sql_generate import build_schema_description, extract_sql_from_llm_response
from config import DEEPSEEK_API_KEY
from services.db_service import get_db_service
from services.llm_service import get_llm_service


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sql_validate_node(state: AgentState) -> Dict[str, Any]:
    """
    SQL 校验节点 - 优先 EXPLAIN 校验，失败后尝试修复并再次验证
    """
    generated_sql = state.get("generated_sql", "")
    schemas = state.get("relevant_schemas", [])
    question = state["question"]
    execution_stats = dict(state.get("execution_stats", {}))

    logger.info(f"[SQL Validate] Validating SQL: {generated_sql[:100]}...")

    if not generated_sql:
        logger.warning("[SQL Validate] No SQL to validate")
        no_sql_error = state.get("validation_result", {}).get("error", "No SQL generated")
        execution_stats.update({
            "validation_attempted": True,
            "validation_passed": False,
            "validation_type": "empty",
            "fix_attempted": False,
            "fix_success": False,
            "fix_strategy": "",
            "safety_blocked": False,
            "initial_error": no_sql_error,
        })
        return {
            "validation_result": {
                "valid": False,
                "error": no_sql_error,
                "corrected_sql": None,
                "validation_type": "empty",
            },
            "error_type": "unfixable",
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }


    try:
        db_service = get_db_service()

        is_safe, safety_error = db_service.is_safe_sql(generated_sql)
        if not is_safe:
            logger.warning(f"[SQL Validate] SQL failed safety check: {safety_error}")
            execution_stats.update({
                "validation_attempted": True,
                "validation_passed": False,
                "validation_type": "security",
                "fix_attempted": False,
                "fix_success": False,
                "fix_strategy": "",
                "safety_blocked": True,
                "initial_error": safety_error,
            })
            return {
                "generated_sql": generated_sql,
                "validation_result": {
                    "valid": False,
                    "error": safety_error,
                    "corrected_sql": None,
                    "validation_type": "security",
                },
                "error_type": "unfixable",
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        explain_result = db_service.explain_query(generated_sql)
        if explain_result["valid"]:
            logger.info("[SQL Validate] SQL validation passed")
            execution_stats.update({
                "validation_attempted": True,
                "validation_passed": True,
                "validation_type": "explain",
                "fix_attempted": False,
                "fix_success": False,
                "fix_strategy": "",
                "safety_blocked": False,
                "initial_error": "",
            })
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
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        error_msg = explain_result.get("error", "EXPLAIN execution failed")
        error_type = classify_error(error_msg)
        logger.warning(f"[SQL Validate] EXPLAIN failed: {error_msg}")

        if error_type == "unfixable":
            execution_stats.update({
                "validation_attempted": True,
                "validation_passed": False,
                "validation_type": "explain",
                "fix_attempted": False,
                "fix_success": False,
                "fix_strategy": "",
                "safety_blocked": False,
                "initial_error": error_msg,
            })
            return {
                "generated_sql": generated_sql,
                "validation_result": {
                    "valid": False,
                    "error": error_msg,
                    "corrected_sql": None,
                    "validation_type": "explain",
                },
                "error_type": error_type,
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        fixed_sql, fix_strategy = attempt_sql_fix(generated_sql, question, schemas, error_msg)
        if not fixed_sql or fixed_sql.strip() == generated_sql.strip():
            logger.warning("[SQL Validate] No effective SQL fix generated")
            execution_stats.update({
                "validation_attempted": True,
                "validation_passed": False,
                "validation_type": "fix_skipped",
                "fix_attempted": True,
                "fix_success": False,
                "fix_strategy": "not_fixed",
                "safety_blocked": False,
                "initial_error": error_msg,
            })
            return {
                "generated_sql": generated_sql,
                "validation_result": {
                    "valid": False,
                    "error": error_msg,
                    "corrected_sql": None,
                    "validation_type": "fix_skipped",
                },
                "error_type": "fixable",
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        fixed_safe, fixed_safety_error = db_service.is_safe_sql(fixed_sql)
        if not fixed_safe:
            logger.warning(f"[SQL Validate] Fixed SQL is unsafe: {fixed_safety_error}")
            execution_stats.update({
                "validation_attempted": True,
                "validation_passed": False,
                "validation_type": "security",
                "fix_attempted": True,
                "fix_success": False,
                "fix_strategy": fix_strategy,
                "safety_blocked": True,
                "initial_error": error_msg,
            })
            return {
                "generated_sql": generated_sql,
                "validation_result": {
                    "valid": False,
                    "error": fixed_safety_error,
                    "corrected_sql": None,
                    "validation_type": "security",
                },
                "error_type": "unfixable",
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        verify_result = db_service.explain_query(fixed_sql)
        if verify_result["valid"]:
            logger.info(f"[SQL Validate] SQL fixed successfully via {fix_strategy}")
            execution_stats.update({
                "validation_attempted": True,
                "validation_passed": True,
                "validation_type": fix_strategy,
                "fix_attempted": True,
                "fix_success": True,
                "fix_strategy": fix_strategy,
                "safety_blocked": False,
                "initial_error": error_msg,
            })
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
                "execution_stats": execution_stats,
                "messages": state["messages"],
            }

        verify_error = verify_result.get("error", "SQL fix verification failed")
        logger.warning(f"[SQL Validate] Fixed SQL still invalid: {verify_error}")
        execution_stats.update({
            "validation_attempted": True,
            "validation_passed": False,
            "validation_type": f"{fix_strategy}_failed",
            "fix_attempted": True,
            "fix_success": False,
            "fix_strategy": fix_strategy,
            "safety_blocked": False,
            "initial_error": error_msg,
        })
        return {
            "generated_sql": fixed_sql,
            "validation_result": {
                "valid": False,
                "error": verify_error,
                "corrected_sql": fixed_sql,
                "validation_type": f"{fix_strategy}_failed",
            },
            "error_type": "fixable",
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }

    except Exception as e:
        logger.error(f"[SQL Validate] Validation error: {e}")
        execution_stats.update({
            "validation_attempted": True,
            "validation_passed": False,
            "validation_type": "exception",
            "fix_attempted": False,
            "fix_success": False,
            "fix_strategy": "",
            "safety_blocked": False,
            "initial_error": str(e),
        })
        return {
            "generated_sql": generated_sql,
            "validation_result": {
                "valid": False,
                "error": str(e),
                "corrected_sql": None,
                "validation_type": "exception",
            },
            "error_type": "unfixable",
            "execution_stats": execution_stats,
            "messages": state["messages"],
        }




def attempt_sql_fix(sql: str, question: str, schemas: list, error: str) -> Tuple[str, str]:
    """尝试使用 LLM 或启发式规则修复 SQL。"""
    schema_text = build_schema_description(schemas)

    try:
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY 未设置")

        llm = get_llm_service()
        response = llm.validate_and_fix_sql(
            schemas=schema_text,
            question=question,
            sql=sql,
            error=error,
        )
        fixed_sql = extract_sql_from_llm_response(response)
        if fixed_sql and fixed_sql.strip() != sql.strip():
            return fixed_sql.strip(), "llm_fixed"
    except Exception as e:
        logger.warning(f"[SQL Validate] LLM SQL fix unavailable: {e}")


    heuristic_sql = heuristic_fix_sql(sql, schemas, error)
    if heuristic_sql and heuristic_sql.strip() != sql.strip():
        return heuristic_sql.strip(), "heuristic_fixed"

    return sql, "not_fixed"


def heuristic_fix_sql(sql: str, schemas: List[Dict[str, Any]], error: str) -> str:
    """在无 LLM 时基于 schema 做简单启发式修复。"""
    fixed_sql = sql

    column_match = re.search(r'column\s+"?([\w\.]+)"?\s+does not exist', error, re.IGNORECASE)
    if column_match:
        missing_column = column_match.group(1)
        replacement = find_closest_column(missing_column, schemas)
        if replacement:
            return replace_identifier(fixed_sql, missing_column, replacement)

    relation_match = re.search(r'relation\s+"?([\w\.]+)"?\s+does not exist', error, re.IGNORECASE)
    if relation_match:
        missing_table = relation_match.group(1)
        replacement = find_closest_table(missing_table, schemas)
        if replacement:
            return replace_identifier(fixed_sql, missing_table, replacement)

    return fixed_sql


def find_closest_column(identifier: str, schemas: List[Dict[str, Any]]) -> str:
    """根据 schema 查找最接近的列名。"""
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


def find_closest_table(identifier: str, schemas: List[Dict[str, Any]]) -> str:
    """根据 schema 查找最接近的表名。"""
    table_names = [schema.get("table_name", "") for schema in schemas if schema.get("table_name")]
    match = difflib.get_close_matches(identifier, table_names, n=1, cutoff=0.6)
    return match[0] if match else ""


def replace_identifier(sql: str, old_identifier: str, new_identifier: str) -> str:
    """替换 SQL 中的标识符。"""
    pattern = rf'\b{re.escape(old_identifier)}\b'
    return re.sub(pattern, new_identifier, sql)


def classify_error(error: str) -> str:
    """分类错误类型：fixable / unfixable。"""
    error_lower = error.lower()

    unfixable_patterns = [
        r"permission denied",
        r"syntax error",
        r"relation .* does not exist",
        r"table .* does not exist",
        r"只允许 select 查询",
        r"检测到危险 sql 模式",
        r"sql 语句为空",
        r"no sql generated",
    ]
    for pattern in unfixable_patterns:
        if re.search(pattern, error_lower, re.IGNORECASE):
            return "unfixable"

    fixable_patterns = [
        r"column .* does not exist",
        r"relation .* does not exist",
        r"table .* does not exist",
        r"missing from-clause entry",
        r"operator does not exist",
        r"ambiguous column",

    ]
    for pattern in fixable_patterns:
        if re.search(pattern, error_lower, re.IGNORECASE):
            return "fixable"

    return "fixable"
