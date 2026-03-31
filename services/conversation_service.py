"""对话上下文与多轮追问辅助函数。"""
import re
from typing import Any, Dict, List, Optional


TIME_RANGE_ALIASES = {
    "本月": "本月",
    "这个月": "本月",
    "上个月": "上月",
    "上月": "上月",
    "今年": "今年",
    "最近30天": "最近30天",
    "近30天": "最近30天",
    "最近7天": "最近7天",
    "近7天": "最近7天",
}

DIMENSION_KEYWORDS = ["城市", "品类", "产品", "用户", "省份", "月份", "日期"]
FOLLOW_UP_PREFIXES = (
    "那",
    "那么",
    "那就",
    "再",
    "继续",
    "然后",
    "只看",
    "只要",
    "改成",
    "改为",
    "换成",
    "按",
)
SUBJECT_KEYWORDS = [
    "订单",
    "用户",
    "产品",
    "评价",
    "销售额",
    "销量",
    "品类",
    "城市",
    "客单价",
    "复购率",
    "评分",
    "趋势",
    "分布",
    "排行",
]


def get_recent_chat_history(chat_history: List[Dict[str, Any]], max_turns: int = 5) -> List[Dict[str, Any]]:
    """获取最近若干轮对话的精简历史。"""
    cleaned_history: List[Dict[str, Any]] = []
    for message in chat_history:
        role = message.get("role")
        content = str(message.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue

        item: Dict[str, Any] = {"role": role, "content": content}
        if message.get("sql"):
            item["sql"] = message["sql"]
        if message.get("resolved_question"):
            item["resolved_question"] = message["resolved_question"]
        cleaned_history.append(item)

    return cleaned_history[-max_turns * 2:]



def build_history_context_text(chat_history: List[Dict[str, Any]], max_messages: int = 4) -> str:
    """将历史对话转成适合提示词的文本。"""
    history_lines = []
    for message in get_recent_chat_history(chat_history, max_turns=max_messages)[-max_messages:]:
        role = message.get("role", "user")
        content = str(message.get("content", "")).strip()
        if not content:
            continue

        line = f"{role}: {content}"
        sql = str(message.get("sql", "")).strip()
        if sql:
            line += f"\n  SQL: {sql[:120]}"
        history_lines.append(line)

    return "\n".join(history_lines)



def extract_last_user_question(chat_history: List[Dict[str, Any]]) -> str:
    """提取最近一条用户问题。"""
    for message in reversed(chat_history):
        if message.get("role") == "user":
            content = str(message.get("content", "")).strip()
            if content:
                return content
    return ""



def extract_time_range(text: str) -> Optional[str]:
    """从文本中提取标准化时间范围。"""
    normalized = normalize_text(text)
    for alias, canonical in TIME_RANGE_ALIASES.items():
        if alias in normalized:
            return canonical
    return None



def extract_limit(text: str) -> Optional[int]:
    """从文本中提取 top/limit。"""
    match = re.search(r"(?:前|top\s*|TOP\s*)(\d+)", text)
    if match:
        return int(match.group(1))

    match = re.search(r"只看前?(\d+)", text)
    if match:
        return int(match.group(1))

    return None



def extract_dimension(text: str) -> str:
    """提取按某维度统计的目标字段。"""
    normalized = normalize_text(text)
    for keyword in DIMENSION_KEYWORDS:
        patterns = [f"按{keyword}", f"{keyword}统计", f"{keyword}排行", f"{keyword}分布"]
        if any(pattern in normalized for pattern in patterns):
            return keyword
    return ""



def is_follow_up_question(question: str) -> bool:
    """判断是否是追问。"""
    normalized = normalize_text(question)
    if not normalized:
        return False

    if normalized.startswith(FOLLOW_UP_PREFIXES):
        return True

    if normalized.endswith("呢") or normalized.endswith("呢?") or normalized.endswith("呢？"):
        return True

    follow_up_markers = ["只看", "换成", "改成", "按", "继续", "再看", "还有", "那", "呢"]
    if len(normalized) <= 12 and any(marker in normalized for marker in follow_up_markers):
        return True

    return False



def resolve_question_with_history(question: str, chat_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """结合历史记录解析追问，输出当前轮的完整问题。"""
    base_question = extract_last_user_question(chat_history)
    normalized_question = normalize_text(question)

    if not base_question or not is_follow_up_question(normalized_question):
        return {
            "resolved_question": question,
            "is_follow_up": False,
            "reference_question": base_question,
        }

    resolved_question = base_question

    time_range = extract_time_range(question)
    if time_range:
        resolved_question = replace_time_range(resolved_question, time_range)

    limit = extract_limit(question)
    if limit is not None:
        resolved_question = replace_limit(resolved_question, limit)

    dimension = extract_dimension(question)
    if dimension:
        resolved_question = replace_dimension(resolved_question, dimension)

    if resolved_question == base_question and not has_subject_keywords(question):
        resolved_question = f"{trim_tail(base_question)}，补充要求：{trim_tail(question)}"

    return {
        "resolved_question": resolved_question,
        "is_follow_up": True,
        "reference_question": base_question,
    }



def has_subject_keywords(text: str) -> bool:
    """判断当前句子是否包含明确主体。"""
    normalized = normalize_text(text)
    return any(keyword in normalized for keyword in SUBJECT_KEYWORDS)



def replace_time_range(base_question: str, time_range: str) -> str:
    """替换问题中的时间范围。"""
    updated = base_question
    for alias in TIME_RANGE_ALIASES:
        if alias in updated:
            updated = updated.replace(alias, time_range)
            break
    else:
        updated = f"{time_range}{trim_tail(updated)}"

    return updated



def replace_limit(base_question: str, limit: int) -> str:
    """替换问题中的条数限制。"""
    updated = re.sub(r"前\d+", f"前{limit}", base_question, flags=re.IGNORECASE)
    updated = re.sub(r"Top\s*\d+", f"Top {limit}", updated, flags=re.IGNORECASE)

    if updated == base_question:
        updated = f"{trim_tail(base_question)}，只看前{limit}个"

    return updated



def replace_dimension(base_question: str, dimension: str) -> str:
    """替换问题中的统计维度。"""
    for keyword in DIMENSION_KEYWORDS:
        if keyword in base_question:
            return base_question.replace(keyword, dimension, 1)

    return f"{trim_tail(base_question)}，按{dimension}统计"



def build_assistant_message(question: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """构建可持久化的助手消息。"""
    query_result = result.get("query_result") or []
    return {
        "role": "assistant",
        "content": result.get("final_answer", ""),
        "question": question,
        "resolved_question": result.get("resolved_question", question),
        "sql": result.get("generated_sql") or "",
        "table_data": query_result,
    }



def trim_tail(text: str) -> str:
    """去除末尾语气符号。"""
    return str(text).strip().rstrip("？?。！!，,")



def normalize_text(text: str) -> str:
    """标准化文本。"""
    return re.sub(r"\s+", "", str(text or "")).strip()
