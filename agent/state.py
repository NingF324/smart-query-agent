"""
Agent State 定义 - LangGraph 状态管理
"""
from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.pydantic import BaseModel


class AgentState(TypedDict):
    """Agent 状态类型定义"""

    # 用户输入
    question: str  # 用户问题
    messages: List[Dict[str, Any]]  # 消息历史
    chat_history: List[Dict[str, Any]]  # 多轮对话历史

    # 中间结果
    intent: Dict[str, Any]  # 意图解析结果
    relevant_schemas: List[Dict[str, Any]]  # 相关表结构
    generated_sql: str  # 生成的 SQL
    validation_result: Dict[str, Any]  # SQL 校验结果
    query_result: List[Dict[str, Any]]  # 查询结果
    final_answer: str  # 最终答案

    # 控制信息
    retry_count: int  # 重试次数
    max_retries: int  # 最大重试次数
    error_type: Optional[str]  # 错误类型


def create_initial_state(question: str, chat_history: Optional[List[Dict[str, Any]]] = None) -> AgentState:
    """
    创建初始状态

    Args:
        question: 用户问题
        chat_history: 历史对话（可选）

    Returns:
        AgentState: 初始状态
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
    # 时间字段映射
    "本月": "EXTRACT(MONTH FROM order_date) = EXTRACT(MONTH FROM CURRENT_DATE)",
    "上月": "order_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND order_date < DATE_TRUNC('month', CURRENT_DATE)",
    "今年": "EXTRACT(YEAR FROM order_date) = EXTRACT(YEAR FROM CURRENT_DATE)",
    "最近30天": "order_date >= CURRENT_DATE - INTERVAL '30 days'",
    "最近7天": "order_date >= CURRENT_DATE - INTERVAL '7 days'",

    # 业务术语映射
    "销售额": "SUM(quantity * unit_price)",
    "订单数": "COUNT(*)",
    "客单价": "AVG(total_amount)",
    "复购率": "复购用户数 / 总用户数",

    # 表名映射
    "订单": "orders",
    "订单明细": "order_items",
    "产品": "products",
    "用户": "users",
    "评价": "reviews",

    # 字段名映射
    "商品名称": "product_name",
    "品类": "category",
    "单价": "unit_price",
    "数量": "quantity",
    "评分": "rating"
}


def get_field_mapping(field_name: str) -> Optional[str]:
    """
    获取字段映射

    Args:
        field_name: 字段名（中文或英文）

    Returns:
        Optional[str]: 映射后的表达式或字段名
    """
    return FIELD_MAPPINGS.get(field_name, None)
