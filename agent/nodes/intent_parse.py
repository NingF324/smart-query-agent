"""
意图解析节点 - 理解用户查询意图，提取关键信息
"""
import logging
from typing import Any, Dict, List

from agent.state import AgentState
from services.conversation_service import extract_limit, extract_time_range, resolve_question_with_history


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


ENTITY_KEYWORDS = ["订单", "产品", "用户", "评价", "销量", "销售额", "品类", "城市", "客单价", "复购率", "评分"]



def intent_parse_node(state: AgentState) -> Dict[str, Any]:
    """理解用户问题并提取意图。"""
    question = state["question"]
    chat_history = state.get("chat_history", [])

    logger.info(f"[Intent Parse] Analyzing question: {question}")

    resolution = resolve_question_with_history(question, chat_history)
    resolved_question = resolution["resolved_question"]

    intent = {
        "query_type": detect_query_type(resolved_question),
        "entities": extract_entities(resolved_question),
        "time_range": extract_time_range(resolved_question),
        "limit": extract_limit(resolved_question) or 100,
        "is_follow_up": resolution["is_follow_up"],
        "reference_question": resolution.get("reference_question", ""),
    }

    logger.info(f"[Intent Parse] Resolved question: {resolved_question}")
    logger.info(f"[Intent Parse] Result: {intent}")

    return {
        "intent": intent,
        "resolved_question": resolved_question,
        "is_follow_up": resolution["is_follow_up"],
        "messages": state["messages"],
    }



def detect_query_type(question: str) -> str:
    """分析查询类型。"""
    if any(keyword in question for keyword in ["总数", "数量", "多少"]):
        return "count"
    if any(keyword in question for keyword in ["排行", "最高", "最低", "前", "Top", "top"]):
        return "ranking"
    if any(keyword in question for keyword in ["分布", "占比", "百分比"]):
        return "distribution"
    if any(keyword in question for keyword in ["趋势", "变化", "增长", "下降"]):
        return "trend"
    return "unknown"



def extract_entities(question: str) -> List[str]:
    """提取实体关键词。"""
    entities: List[str] = []
    for keyword in ENTITY_KEYWORDS:
        if keyword in question and keyword not in entities:
            entities.append(keyword)
    return entities



def extract_entities_from_llm(question: str) -> Dict[str, Any]:
    """使用 LLM 提取实体（高级功能占位）。"""
    return {
        "tables": [],
        "fields": [],
        "conditions": [],
    }



def validate_intent(intent: Dict[str, Any]) -> bool:
    """验证意图是否有效。"""
    if not intent.get("query_type"):
        logger.warning(f"[Intent Parse] Missing query_type in intent: {intent}")
        return False

    return True
