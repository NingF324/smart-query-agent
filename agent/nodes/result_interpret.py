"""
结果解释节点 - 将查询结果转换为自然语言描述
"""
import logging
from typing import Dict, Any
from agent.state import AgentState

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def result_interpret_node(state: AgentState) -> Dict[str, Any]:
    """
    结果解释节点 - 将查询结果转换为自然语言描述

    Args:
        state: 当前状态

    Returns:
        Dict[str, Any]: 更新后的状态
    """
    question = state["question"]
    query_result = state.get("query_result", [])
    generated_sql = state.get("generated_sql", "")
    validation_result = state.get("validation_result", {})

    logger.info(f"[Result Interpret] Interpreting {len(query_result)} query results")

    # 检查是否有有效结果
    if not query_result:
        logger.warning("[Result Interpret] No query results")

        # 检查是否是预期的空结果
        if validation_result.get("valid"):
            final_answer = f"查询执行成功，但没有找到匹配的数据。\n\n您的问题：{question}\n\n建议：\n- 检查查询条件是否合适\n- 尝试使用不同的关键词"
        else:
            error_msg = validation_result.get("error", "未知错误")
            final_answer = f"查询失败：{error_msg}\n\n无法为您提供结果，请检查问题或联系管理员。"

        return {
            "final_answer": final_answer,
            "messages": state["messages"]
        }

    # 生成结果描述
    result_count = len(query_result)
    result_text = format_results_summary(query_result, question)

    # 添加查询详情
    details_text = build_result_details(query_result, generated_sql, result_count)

    final_answer = f"{result_text}\n\n{details_text}"

    logger.info("[Result Interpret] Answer generated successfully")

    return {
        "final_answer": final_answer,
        "messages": state["messages"]
    }


def format_results_summary(results: list, question: str) -> str:
    """
    格式化结果摘要

    Args:
        results: 查询结果列表
        question: 原始问题

    Returns:
        str: 格式化的摘要文本
    """
    if not results:
        return "查询成功，但没有找到匹配的数据。"

    result_count = len(results)
    summary = f"查询成功，找到 **{result_count}** 条记录：\n\n"

    # 显示前 5 条结果的摘要
    display_count = min(result_count, 5)
    for i, row in enumerate(results[:display_count], 1):
        row_text = format_row_summary(row)
        summary += f"{i}. {row_text}\n"

    if result_count > 5:
        summary += f"\n... 还有 {result_count - 5} 条记录未显示\n"

    return summary


def format_row_summary(row: dict) -> str:
    """
    格式化单行结果摘要

    Args:
        row: 数据行字典

    Returns:
        str: 格式化的行文本
    """
    if not row:
        return "空记录"

    # 提取前 3 个值
    values = []
    for key, value in list(row.items())[:3]:
        if isinstance(value, float):
            values.append(f"{value:.2f}")
        elif isinstance(value, int):
            values.append(str(value))
        else:
            str_value = str(value)
            if len(str_value) > 20:
                str_value = str_value[:20] + "..."
            values.append(str_value)

    return " | ".join(values)


def build_result_details(results: list, sql: str, count: int) -> str:
    """
    构建结果详情

    Args:
        results: 查询结果列表
        sql: 执行的 SQL
        count: 结果数量

    Returns:
        str: 详情文本
    """
    details = []

    # 统计信息
    details.append(f"**数据统计**")
    details.append(f"- 总记录数：{count}")

    if count > 0:
        # 提取第一行的键作为字段名
        first_row = results[0]
        details.append(f"- 涉及字段：{len(first_row)} 个")

    # 如果有 SQL，显示部分
    if sql:
        sql_preview = sql[:100]
        if len(sql) > 100:
            sql_preview += "..."
        details.append(f"\n**执行的查询**")
        details.append(f"```sql\n{sql_preview}\n```")

    return "\n".join(details)


def is_successful_result(validation_result: dict) -> bool:
    """
    判断是否是成功的查询结果

    Args:
        validation_result: 验证结果

    Returns:
        bool: 是否成功
    """
    if not validation_result:
        return False

    return validation_result.get("valid", False)


def get_result_summary(results: list) -> dict:
    """
    获取结果摘要信息

    Args:
        results: 查询结果列表

    Returns:
        dict: 摘要信息
    """
    if not results:
        return {
            "count": 0,
            "has_data": False,
            "columns": []
        }

    return {
        "count": len(results),
        "has_data": True,
        "columns": list(results[0].keys()) if results else []
    }
