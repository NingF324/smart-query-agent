"""
SQL 校验节点 - 使用 EXPLAIN 和 LLM 修复 SQL 错误
"""
import logging
import re
from typing import Dict, Any
from agent.state import AgentState
from services.db_service import get_db_service


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sql_validate_node(state: AgentState) -> Dict[str, Any]:
    """
    SQL 校验节点 - 使用 EXPLAIN 校验 SQL，失败时用 LLM 修复

    Args:
        state: 当前状态

    Returns:
        Dict[str, Any]: 更新后的状态
    """
    generated_sql = state.get("generated_sql", "")
    schemas = state.get("relevant_schemas", [])
    question = state["question"]

    logger.info(f"[SQL Validate] Validating SQL: {generated_sql[:100]}...")

    if not generated_sql:
        logger.warning("[SQL Validate] No SQL to validate")
        return {
            "validation_result": {
                "valid": False,
                "error": "No SQL generated"
            },
            "error_type": "no_sql_generated",
            "messages": state["messages"]
        }

    try:
        # 初始化数据库服务
        db_service = get_db_service()


        # 第一步：安全检查
        is_safe, safety_error = db_service.is_safe_sql(generated_sql)
        if not is_safe:
            logger.warning(f"[SQL Validate] SQL failed safety check: {safety_error}")

            # 尝试用 LLM 修复
            fixed_sql = attempt_sql_fix(generated_sql, question, schemas, safety_error)

            return {
                "generated_sql": fixed_sql,
                "validation_result": {
                    "valid": False,
                    "error": safety_error,
                    "safety_failed": True
                },
                "error_type": classify_error(safety_error),
                "messages": state["messages"]
            }

        # 第二步：EXPLAIN 验证
        explain_result = db_service.explain_query(generated_sql)

        if not explain_result["valid"]:
            logger.warning(f"[SQL Validate] EXPLAIN failed: {explain_result.get('error', 'Unknown error')}")

            # 尝试用 LLM 修复
            error_msg = explain_result.get("error", "EXPLAIN execution failed")
            fixed_sql = attempt_sql_fix(generated_sql, question, schemas, error_msg)

            return {
                "generated_sql": fixed_sql,
                "validation_result": {
                    "valid": False,
                    "error": error_msg,
                    "explain_failed": True
                },
                "error_type": classify_error(error_msg),
                "messages": state["messages"]
            }

        # EXPLAIN 成功
        logger.info("[SQL Validate] SQL validation passed")
        return {
            "validation_result": {
                "valid": True,
                "explain": explain_result.get("explain", [])[:3]  # 只保存前3行
            },
            "error_type": None,
            "messages": state["messages"]
        }

    except Exception as e:
        logger.error(f"[SQL Validate] Validation error: {e}")
        return {
            "validation_result": {
                "valid": False,
                "error": str(e)
            },
            "error_type": "unknown_error",
            "messages": state["messages"]
        }


def attempt_sql_fix(sql: str, question: str, schemas: list, error: str) -> str:
    """
    尝试用 LLM 修复 SQL（简单实现）

    Args:
        sql: 失败的 SQL
        question: 原始问题
        schemas: Schema 列表
        error: 错误信息

    Returns:
        str: 修复后的 SQL
    """
    # TODO: 使用 LLM 服务修复 SQL
    # 当前返回原始 SQL（表示未修复）
    logger.warning(f"[SQL Validate] LLM fix not implemented, returning original SQL")
    return sql


def classify_error(error: str) -> str:
    """
    分类错误类型

    Args:
        error: 错误信息

    Returns:
        str: 错误类型
    """
    error_lower = error.lower()

    if "syntax" in error_lower or "parse" in error_lower:
        return "syntax_error"

    if "permission" in error_lower or "denied" in error_lower:
        return "permission_error"

    if "column" in error_lower or "field" in error_lower or "does not exist" in error_lower:
        return "execution_error"  # 可修复

    if "table" in error_lower and "not exist" in error_lower:
        return "execution_error"  # 可修复

    return "unknown_error"
