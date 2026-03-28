"""
SQL 执行节点 - 执行 SQL 并处理超时和错误
"""
import logging
from typing import Dict, Any
from agent.state import AgentState
from services.db_service import DatabaseService

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sql_execute_node(state: AgentState) -> Dict[str, Any]:
    """
    SQL 执行节点 - 执行 SQL 并返回结果

    Args:
        state: 当前状态

    Returns:
        Dict[str, Any]: 更新后的状态
    """
    generated_sql = state.get("generated_sql", "")
    question = state["question"]

    logger.info(f"[SQL Execute] Executing SQL: {generated_sql[:100]}...")

    if not generated_sql:
        logger.warning("[SQL Execute] No SQL to execute")

        return {
            "query_result": [],
            "validation_result": {
                "valid": False,
                "error": "No SQL generated"
            },
            "error_type": "no_sql",
            "messages": state["messages"]
        }

    try:
        # 初始化数据库服务
        db_service = DatabaseService()

        # 执行查询（自动带超时控制）
        result = db_service.execute_query(generated_sql)

        logger.info(f"[SQL Execute] Query executed successfully, returned {len(result)} rows")

        return {
            "query_result": result,
            "validation_result": {
                "valid": True
            },
            "error_type": None,
            "messages": state["messages"]
        }

    except ValueError as e:
        # SQL 不安全的错误
        logger.warning(f"[SQL Execute] Safety error: {e}")

        return {
            "query_result": [],
            "validation_result": {
                "valid": False,
                "error": str(e)
            },
            "error_type": "permission_error",  # 不可修复
            "messages": state["messages"]
        }

    except TimeoutError as e:
        # 超时错误
        logger.warning(f"[SQL Execute] Query timeout: {e}")

        return {
            "query_result": [],
            "validation_result": {
                "valid": False,
                "error": f"Query timeout: {e}"
            },
            "error_type": "execution_error",  # 可重试
            "messages": state["messages"]
        }

    except Exception as e:
        # 其他执行错误
        logger.warning(f"[SQL Execute] Query execution error: {e}")

        return {
            "query_result": [],
            "validation_result": {
                "valid": False,
                "error": str(e)
            },
            "error_type": "execution_error",  # 可重试
            "messages": state["messages"]
        }


def format_results(query_result: list) -> str:
    """
    格式化查询结果

    Args:
        query_result: 查询结果列表

    Returns:
        str: 格式化后的文本
    """
    if not query_result:
        return "查询成功，但没有返回结果"

    result_count = len(query_result)
    result_text = f"查询成功，返回 {result_count} 条记录：\n\n"

    # 只显示前 10 条
    display_count = min(result_count, 10)
    for i, row in enumerate(query_result[:display_count], 1):
        result_text += f"{i}. {row}\n"

    if result_count > 10:
        result_text += f"\n... 还有 {result_count - 10} 条记录未显示"

    return result_text


def is_empty_result(query_result: list) -> bool:
    """
    判断结果是否为空

    Args:
        query_result: 查询结果列表

    Returns:
        bool: 是否为空
    """
    return not query_result or len(query_result) == 0
