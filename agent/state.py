"""
Agent State definition - LangGraph state management
"""
from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict):
    """Agent state type definition"""

    question: str
    resolved_question: str
    is_follow_up: bool
    messages: List[Dict[str, Any]]
    chat_history: List[Dict[str, Any]]

    intent: Dict[str, Any]
    relevant_schemas: List[Dict[str, Any]]
    generated_sql: str
    validation_result: Dict[str, Any]
    query_result: List[Dict[str, Any]]
    final_answer: str

    retry_count: int
    max_retries: int
    error_type: Optional[str]


def create_initial_state(question: str, chat_history: Optional[List[Dict[str, Any]]] = None) -> AgentState:
    """Create initial state."""
    return AgentState({
        "question": question,
        "resolved_question": question,
        "is_follow_up": False,
        "messages": [],
        "chat_history": chat_history or [],
        "intent": {},
        "relevant_schemas": [],
        "generated_sql": "",
        "validation_result": {},
        "query_result": [],
        "final_answer": "",
        "retry_count": 0,
        "max_retries": 3,
        "error_type": None,
    })


FIELD_MAPPINGS = {
    "本月": "EXTRACT(MONTH FROM order_date) = EXTRACT(MONTH FROM CURRENT_DATE)",
    "上月": "order_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND order_date < DATE_TRUNC('month', CURRENT_DATE)",
    "今年": "EXTRACT(YEAR FROM order_date) = EXTRACT(YEAR FROM CURRENT_DATE)",
    "最近30天": "order_date >= CURRENT_DATE - INTERVAL '30 days'",
    "最近7天": "order_date >= CURRENT_DATE - INTERVAL '7 days')",
    "销售额": "SUM(quantity * unit_price)",
    "订单数": "COUNT(*)",
    "客单价": "AVG(total_amount)",
    "复购率": "复购用户数 / 总用户数",
    "订单": "orders",
    "订单明细": "order_items",
    "产品": "products",
    "用户": "users",
    "评价": "reviews",
    "商品名称": "product_name",
    "品类": "category",
    "单价": "unit_price",
    "数量": "quantity",
    "评分": "rating",
}


def get_field_mapping(field_name: str) -> Optional[str]:
    """Get field mapping."""
    return FIELD_MAPPINGS.get(field_name, None)
