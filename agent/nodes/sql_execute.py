"""
SQL 执行节点 - 执行 SQL 并处理超时和错误
"""
import logging
import time
from typing import Dict, Any
from agent.state import AgentState
from services.db_service import get_state_db_service


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
    execution_stats = dict(state.get("execution_stats", {}))

    logger.info(f"[SQL Execute] Executing SQL: {generated_sql[:100]}...")
    started_at = time.perf_counter()


    if not generated_sql:
        logger.warning("[SQL Execute] No SQL to execute")
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        execution_stats.update({
            "execution_attempted": False,
            "execution_success": False,
            "execution_error": "No SQL generated",
            "execution_latency_ms": elapsed_ms,
            "execution_error_type": "no_sql",
        })
        return {
            "query_result": [],
            "validation_result": {
                "valid": False,
                "error": "No SQL generated"
            },
            "error_type": "no_sql",
            "execution_stats": execution_stats,
            "messages": state["messages"]
        }


    try:
        # 初始化数据库服务
        db_service = get_state_db_service(state)


        # 执行查询（自动带超时控制）
        result = db_service.execute_query(generated_sql)

        logger.info(f"[SQL Execute] Query executed successfully, returned {len(result)} rows")
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)

        execution_stats.update({
            "execution_attempted": True,
            "execution_success": True,
            "execution_error": "",
            "execution_latency_ms": elapsed_ms,
            "execution_error_type": "",
        })
        return {
            "query_result": result,
            "validation_result": {
                "valid": True
            },
            "error_type": None,
            "execution_stats": execution_stats,
            "messages": state["messages"]
        }


    except ValueError as e:
        # SQL 不安全的错误
        logger.warning(f"[SQL Execute] Safety error: {e}")

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        execution_stats.update({
            "execution_attempted": True,
            "execution_success": False,
            "execution_error": str(e),
            "execution_latency_ms": elapsed_ms,
            "execution_error_type": "permission_error",
        })
        return {
            "query_result": [],
            "validation_result": {
                "valid": False,
                "error": str(e)
            },
            "error_type": "permission_error",  # 不可修复
            "execution_stats": execution_stats,
            "messages": state["messages"]
        }


    except TimeoutError as e:
        # 超时错误
        logger.warning(f"[SQL Execute] Query timeout: {e}")

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        execution_stats.update({
            "execution_attempted": True,
            "execution_success": False,
            "execution_error": f"Query timeout: {e}",
            "execution_latency_ms": elapsed_ms,
            "execution_error_type": "timeout",
        })
        return {
            "query_result": [],
            "validation_result": {
                "valid": False,
                "error": f"Query timeout: {e}"
            },
            "error_type": "execution_error",  # 可重试
            "execution_stats": execution_stats,
            "messages": state["messages"]
        }


    except Exception as e:
        # 其他执行错误
        logger.warning(f"[SQL Execute] Query execution error: {e}")

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        execution_stats.update({
            "execution_attempted": True,
            "execution_success": False,
            "execution_error": str(e),
            "execution_latency_ms": elapsed_ms,
            "execution_error_type": "execution_error",
        })
        return {
            "query_result": [],
            "validation_result": {
                "valid": False,
                "error": str(e)
            },
            "error_type": "execution_error",  # 可重试
            "execution_stats": execution_stats,
            "messages": state["messages"]
        }





