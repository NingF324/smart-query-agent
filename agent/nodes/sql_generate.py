"""
SQL 生成节点 - 根据意图和 Schema 生成 SQL
"""
import logging
import re
from typing import Dict, Any
from agent.state import AgentState, get_field_mapping

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sql_generate_node(state: AgentState) -> Dict[str, Any]:
    """
    SQL 生成节点 - 基于 Schema 和意图生成 SQL

    Args:
        state: 当前状态

    Returns:
        Dict[str, Any]: 更新后的状态
    """
    question = state["question"]
    intent = state.get("intent", {})
    schemas = state.get("relevant_schemas", [])
    chat_history = state.get("chat_history", [])

    logger.info(f"[SQL Generate] Generating SQL for question: {question}")

    try:
        # 构建 Schema 描述
        schema_text = build_schema_description(schemas)

        # 获取时间范围映射
        time_range = intent.get("time_range")
        if time_range:
            time_mapping = get_field_mapping(time_range)
            intent["time_expression"] = time_mapping

        # TODO: 使用 LLM 生成 SQL
        # 当前使用简单的规则生成作为演示
        sql = generate_sql_with_rules(question, intent, schemas)

        logger.info(f"[SQL Generate] Generated SQL: {sql}")

        return {
            "generated_sql": sql,
            "messages": state["messages"]
        }

    except Exception as e:
        logger.error(f"[SQL Generate] Error: {e}")
        # 生成失败时，返回空 SQL
        return {
            "generated_sql": "",
            "messages": state["messages"]
        }


def build_schema_description(schemas: list) -> str:
    """
    构建 Schema 描述用于 LLM

    Args:
        schemas: Schema 列表

    Returns:
        str: Schema 描述文本
    """
    if not schemas:
        return "No schemas available"

    description = "Database Schema:\n\n"

    for schema in schemas:
        description += f"Table: {schema['table_name']}\n"
        description += f"DDL: {schema['ddl']}\n"
        description += f"Columns: {len(schema['columns'])}\n"
        description += f"Rows: {schema['row_count']}\n\n"

    return description


def generate_sql_with_rules(question: str, intent: dict, schemas: list) -> str:
    """
    使用规则生成 SQL（作为演示）

    Args:
        question: 用户问题
        intent: 意图
        schemas: Schema 列表

    Returns:
        str: 生成的 SQL
    """
    query_type = intent.get("query_type", "unknown")
    entities = intent.get("entities", [])
    limit = intent.get("limit", 100)

    # 简单规则生成
    if query_type == "count":
        if "订单" in entities or "orders" in entities:
            return f"SELECT COUNT(*) as count FROM orders"

        if "用户" in entities or "users" in entities:
            return f"SELECT COUNT(*) as count FROM users"

        if "产品" in entities or "products" in entities:
            return f"SELECT COUNT(*) as count FROM products"

    elif query_type == "ranking":
        if "销售额" in entities or "sales" in entities:
            return f"""
SELECT p.category, SUM(oi.quantity * oi.unit_price) as total_sales
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
GROUP BY p.category
ORDER BY total_sales DESC
LIMIT {limit}
            """.strip()

        if "评分" in entities or "rating" in entities:
            return f"""
SELECT p.product_name, AVG(r.rating) as avg_rating
FROM reviews r
JOIN products p ON r.product_id = p.product_id
GROUP BY p.product_id, p.product_name
HAVING COUNT(*) >= 5
ORDER BY avg_rating DESC
LIMIT {limit}
            """.strip()

    elif query_type == "distribution":
        if "用户" in entities or "users" in entities:
            return f"""
SELECT city, COUNT(*) as user_count
FROM users
GROUP BY city
ORDER BY user_count DESC
LIMIT {limit}
            """.strip()

        if "产品" in entities or "products" in entities:
            return f"""
SELECT category, COUNT(*) as product_count
FROM products
GROUP BY category
ORDER BY product_count DESC
LIMIT {limit}
            """.strip()

    # 默认查询
    return "SELECT * FROM users LIMIT 10"


def extract_sql_from_llm_response(response: str) -> str:
    """
    从 LLM 响应中提取 SQL

    Args:
        response: LLM 响应文本

    Returns:
        str: 提取的 SQL
    """
    # 尝试提取 ```sql 代码块
    sql_match = re.search(r"```sql\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
    if sql_match:
        return sql_match[0].strip()

    # 尝试提取单个 SQL 语句
    sql_match = re.search(r"(SELECT.*?);?$", response, re.DOTALL | re.IGNORECASE)
    if sql_match:
        return sql_match[0].strip()

    # 如果没有匹配，返回原始响应
    return response.strip()
