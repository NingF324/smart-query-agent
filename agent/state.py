"""
Agent State definition - LangGraph state management
"""
from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel


class AgentState(TypedDict):
    """Agent state type definition"""

    # User input
    question: str  # User question
    messages: List[Dict[str, Any]]  # Message history
    chat_history: List[Dict[str, Any]]  # Multi-turn conversation history

    # Intermediate results
    intent: Dict[str, Any]  # Intent analysis result
    relevant_schemas: List[Dict[str, Any]]  # Relevant table schemas
    generated_sql: str  # Generated SQL
    validation_result: Dict[str, Any]  # SQL validation result
    query_result: List[Dict[str, Any]]  # Query result
    final_answer: str  # Final answer

    # Control information
    retry_count: int  # Retry count
    max_retries: int  # Maximum retry count
    error_type: Optional[str]  # Error type


def create_initial_state(question: str, chat_history: Optional[List[Dict[str, Any]]] = None) -> AgentState:
    """
    Create initial state

    Args:
        question: User question
        chat_history: Conversation history (optional)

    Returns:
        AgentState: Initial state
    """
    return AgentState({
        "question": question,
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
        "error_type": None
    })


# Field mappings for semantic mapping
FIELD_MAPPINGS = {
    # Time field mappings
    "本月": "EXTRACT(MONTH FROM order_date) = EXTRACT(MONTH FROM CURRENT_DATE)",
    "上月": "order_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND order_date < DATE_TRUNC('month', CURRENT_DATE)",
    "今年": "EXTRACT(YEAR FROM order_date) = EXTRACT(YEAR FROM CURRENT_DATE)",
    "最近30天": "order_date >= CURRENT_DATE - INTERVAL '30 days'",
    "最近7天": "order_date >= CURRENT_DATE - INTERVAL '7 days')",

    # Business term mappings
    "销售额": "SUM(quantity * unit_price)",
    "订单数": "COUNT(*)",
    "客单价": "AVG(total_amount)",
    "复购率": "复购用户数 / 总用户数",

    # Table name mappings
    "订单": "orders",
    "订单明细": "order_items",
    "产品": "products",
    "用户": "users",
    "评价": "reviews",

    # Column name mappings
    "商品名称": "product_name",
    "品类": "category",
    "单价": "unit_price",
    "数量": "quantity",
    "评分": "rating"
}


def get_field_mapping(field_name: str) -> Optional[str]:
    """
    Get field mapping

    Args:
        field_name: Field name (Chinese or English)

    Returns:
        Optional[str]: Mapped expression or field name
    """
    return FIELD_MAPPINGS.get(field_name, None)
