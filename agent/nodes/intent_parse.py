"""
意图解析节点 - 理解用户查询意图，提取关键信息
"""
import logging
from typing import Dict, Any
from agent.state import AgentState, get_field_mapping

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def intent_parse_node(state: AgentState) -> Dict[str, Any]:
    """
    意图解析节点 - 理解用户问题并提取意图

    Args:
        state: 当前状态

    Returns:
        Dict[str, Any]: 更新后的状态
    """
    question = state["question"]
    chat_history = state.get("chat_history", [])

    logger.info(f"[Intent Parse] Analyzing question: {question}")

    # TODO: 集成 LLM 进行意图分析
    # 当前使用简单的规则匹配实现

    intent = {
        "query_type": "unknown",  # 查询类型：count, ranking, aggregation, etc.
        "entities": [],  # 提取的实体：表名、字段名等
        "time_range": None,  # 时间范围：本月、上月、今年等
        "limit": 100  # 结果限制数量
    }

    # 分析查询类型
    if any(keyword in question for keyword in ["总数", "数量", "多少"]):
        intent["query_type"] = "count"

    elif any(keyword in question for keyword in ["排行", "最高", "最低", "前", "Top"]):
        intent["query_type"] = "ranking"

    elif any(keyword in question for keyword in ["分布", "占比", "百分比"]):
        intent["query_type"] = "distribution"

    elif any(keyword in question for keyword in ["趋势", "变化", "增长", "下降"]):
        intent["query_type"] = "trend"

    # 提取时间范围
    if "本月" in question:
        intent["time_range"] = "本月"
    elif "上月" in question:
        intent["time_range"] = "上月"
    elif "今年" in question:
        intent["time_range"] = "今年"
    elif "最近30天" in question or "近30天" in question:
        intent["time_range"] = "最近30天"
    elif "最近7天" in question or "近7天" in question:
        intent["time_range"] = "最近7天"

    # 提取限制数量
    if "前10" in question:
        intent["limit"] = 10
    elif "前5" in question:
        intent["limit"] = 5
    elif "前20" in question:
        intent["limit"] = 20

    # 提取实体（表名）
    tables_keywords = ["订单", "产品", "用户", "评价", "销量", "销售额", "品类"]
    detected_tables = [kw for kw in tables_keywords if kw in question]

    if detected_tables:
        intent["entities"].extend(detected_tables)

    logger.info(f"[Intent Parse] Result: {intent}")

    return {
        "intent": intent,
        "messages": state["messages"]
    }


def extract_entities_from_llm(question: str) -> Dict[str, Any]:
    """
    使用 LLM 提取实体（高级功能）

    Args:
        question: 用户问题

    Returns:
        Dict[str, Any]: 提取的实体
    """
    # TODO: 使用 LLM 服务提取实体
    # 目前返回空字典
    return {
        "tables": [],
        "fields": [],
        "conditions": []
    }


def validate_intent(intent: Dict[str, Any]) -> bool:
    """
    验证意图是否有效

    Args:
        intent: 意图字典

    Returns:
        bool: 是否有效
    """
    # 检查是否有查询类型
    if not intent.get("query_type"):
        logger.warning(f"[Intent Parse] Missing query_type in intent: {intent}")
        return False

    return True
