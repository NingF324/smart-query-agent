"""
错误响应节点 - 对不可修复错误或重试失败生成最终答复
"""
import logging
from typing import Any, Dict

from agent.state import AgentState


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def error_response_node(state: AgentState) -> Dict[str, Any]:
    """生成面向用户的错误答复。"""
    question = state["question"]
    generated_sql = state.get("generated_sql", "")
    validation_result = state.get("validation_result", {})
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    error_type = state.get("error_type") or "unknown"
    error_msg = validation_result.get("error", "未知错误")

    logger.warning(
        "[Error Response] question=%s, error_type=%s, retry_count=%s",
        question,
        error_type,
        retry_count,
    )

    if error_type == "unfixable":
        reason = "系统识别到当前 SQL 存在不可修复的问题"
    elif error_type == "execution_error" and retry_count >= max_retries:
        reason = "查询执行多次失败，已停止继续重试"
    elif retry_count >= max_retries:
        reason = f"系统已达到最大重试次数（{max_retries} 次）"
    else:
        reason = "当前查询暂时无法完成"

    answer_lines = [
        f"抱歉，未能完成您的问题：{question}",
        "",
        f"原因：{reason}",
        f"错误信息：{error_msg}",
    ]

    if generated_sql:
        sql_preview = generated_sql[:160] + ("..." if len(generated_sql) > 160 else "")
        answer_lines.extend([
            "",
            "最后一次尝试的 SQL：",
            f"```sql\n{sql_preview}\n```",
        ])

    answer_lines.extend([
        "",
        "建议：",
        "- 尝试换一种更明确的问法",
        "- 指定更准确的表、字段或时间范围",
        "- 如果问题持续存在，请检查数据库表结构与权限配置",
    ])

    return {
        "final_answer": "\n".join(answer_lines),
        "messages": state["messages"],
    }
