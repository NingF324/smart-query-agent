"""Intent parsing node: resolve user intent and extract schema hints."""

import logging
import re
from typing import Any, Dict, List

from agent.state import AgentState
from services.conversation_service import extract_limit, extract_time_range, resolve_question_with_history

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


ENTITY_ALIASES = {
    "orders": ["订单", "订购", "orders"],
    "products": ["产品", "商品", "product", "products"],
    "users": ["用户", "客户", "user", "users", "customer", "customers"],
    "reviews": ["评价", "评分", "review", "reviews", "rating", "ratings"],
    "sales": ["销量", "销售", "销售额", "revenue", "sales"],
    "pets": ["宠物", "pet", "pets", "dog", "dogs", "cat", "cats"],
    "students": ["学生", "student", "students"],
    "faculty": ["教师", "faculty", "professor", "professors"],
}

SCHEMA_HINT_KEYWORDS = [
    "join",
    "group",
    "count",
    "sum",
    "avg",
    "where",
    "order",
    "by",
    "top",
    "limit",
    "youngest",
    "oldest",
    "latest",
    "earliest",
    "weight",
    "age",
    "birth",
    "date",
]


def intent_parse_node(state: AgentState) -> Dict[str, Any]:
    """Analyze intent, entities, and context for downstream schema/SQL generation."""
    question = state["question"]
    chat_history = state.get("chat_history", [])

    logger.info("[Intent Parse] Analyzing question: %s", question)

    resolution = resolve_question_with_history(question, chat_history)
    resolved_question = resolution["resolved_question"]

    intent = {
        "query_type": detect_query_type(resolved_question),
        "entities": extract_entities(resolved_question),
        "time_range": extract_time_range(resolved_question),
        "limit": extract_limit(resolved_question) or 100,
        "schema_hints": build_schema_hints(resolved_question),
        "is_follow_up": resolution["is_follow_up"],
        "reference_question": resolution.get("reference_question", ""),
    }

    logger.info("[Intent Parse] Resolved question: %s", resolved_question)
    logger.info("[Intent Parse] Result: %s", intent)

    return {
        "intent": intent,
        "resolved_question": resolved_question,
        "is_follow_up": resolution["is_follow_up"],
        "messages": state["messages"],
    }


def detect_query_type(question: str) -> str:
    """Detect coarse query type."""
    q = question.lower()
    if any(keyword in q for keyword in ["复购率", "repurchase"]):
        return "repurchase_rate"
    if any(keyword in q for keyword in ["总数", "数量", "多少", "how many"]):
        return "count"
    if re.search(r"\bcount\b", q):
        return "count"
    if any(keyword in q for keyword in ["排名", "最高", "最低", "top", "rank", "youngest", "oldest"]):
        return "ranking"
    if any(keyword in q for keyword in ["分布", "占比", "百分比", "distribution", "share"]):
        return "distribution"
    if any(keyword in q for keyword in ["趋势", "变化", "增长", "下降", "trend", "over time"]):
        return "trend"
    return "unknown"


def extract_entities(question: str) -> List[str]:
    """Extract normalized entities from bilingual keyword aliases."""
    q = question.lower()
    entities: List[str] = []
    for canonical, aliases in ENTITY_ALIASES.items():
        matched = False
        for alias in aliases:
            alias_lower = alias.lower()
            if re.search(r"[\u4e00-\u9fff]", alias_lower):
                if alias_lower in q:
                    matched = True
                    break
            else:
                if re.search(rf"\b{re.escape(alias_lower)}\b", q):
                    matched = True
                    break
        if matched and canonical not in entities:
            entities.append(canonical)
    return entities


def build_schema_hints(question: str) -> List[str]:
    """Build lightweight schema hints for schema retrieval ranking."""
    q = question.lower()
    hints: List[str] = []

    for token in SCHEMA_HINT_KEYWORDS:
        if token in q and token not in hints:
            hints.append(token)

    if re.search(r"\byoung(est)?\b", q):
        for token in ["age", "birth", "birth_date", "dob", "min"]:
            if token not in hints:
                hints.append(token)

    if re.search(r"\bold(est)?\b", q):
        for token in ["age", "birth", "birth_date", "dob", "max"]:
            if token not in hints:
                hints.append(token)

    if "dog" in q or "cat" in q:
        for token in ["pet", "pets"]:
            if token not in hints:
                hints.append(token)

    return hints
