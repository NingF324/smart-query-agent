"""
Schema 检索节点 - 根据意图检索相关的数据库表结构
"""
import logging
from typing import Dict, Any, List
from agent.state import AgentState
from services.knowledge_base import KnowledgeBase
from services.db_service import DatabaseService

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def schema_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """
    Schema 检索节点 - 从知识库检索相关的表结构

    Args:
        state: 当前状态

    Returns:
        Dict[str, Any]: 更新后的状态
    """
    question = state["question"]
    intent = state.get("intent", {})

    logger.info(f"[Schema Retrieve] Retrieving schemas for question: {question}")

    try:
        # 初始化知识库和数据库服务
        # TODO: 从单例获取服务
        kb = KnowledgeBase()
        db_service = DatabaseService()

        # 构建搜索查询
        search_query = question

        # 如果意图中包含实体，添加到搜索查询
        entities = intent.get("entities", [])
        if entities:
            search_query += " " + " ".join(entities)

        logger.info(f"[Schema Retrieve] Search query: {search_query}")

        # 语义搜索相关的 DDL
        search_results = kb.search_ddl(search_query, n_results=5)

        logger.info(f"[Schema Retrieve] Found {len(search_results)} related schemas")

        # 从搜索结果中提取表名
        retrieved_tables = []
        for result in search_results:
            table_name = result["metadata"].get("table_name", "")
            if table_name and table_name not in retrieved_tables:
                retrieved_tables.append(table_name)

        # 如果没有检索到表，从数据库获取所有表
        if not retrieved_tables:
            logger.warning("[Schema Retrieve] No tables found in KB, getting all tables from DB")
            retrieved_tables = db_service.get_table_names()

        # 获取表的完整信息
        relevant_schemas = []
        for table_name in retrieved_tables[:10]:  # 最多检索10张表
            try:
                table_info = db_service.get_table_info(table_name)
                ddl = db_service.get_table_schema(table_name)

                relevant_schemas.append({
                    "table_name": table_name,
                    "ddl": ddl,
                    "columns": table_info["columns"],
                    "row_count": table_info["row_count"],
                    "primary_keys": table_info["primary_keys"],
                    "foreign_keys": table_info["foreign_keys"]
                })

                logger.info(f"[Schema Retrieve] Added table: {table_name} ({table_info['row_count']} rows)")

            except Exception as e:
                logger.warning(f"[Schema Retrieve] Failed to get info for {table_name}: {e}")
                continue

        logger.info(f"[Schema Retrieve] Retrieved {len(relevant_schemas)} schemas")

        return {
            "relevant_schemas": relevant_schemas,
            "messages": state["messages"]
        }

    except Exception as e:
        logger.error(f"[Schema Retrieve] Error: {e}")
        # 发生错误时，返回空列表但不中断流程
        return {
            "relevant_schemas": [],
            "messages": state["messages"]
        }


def build_schema_description(schemas: List[Dict[str, Any]]) -> str:
    """
    构建用于 LLM 的 Schema 描述

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
        description += f"Rows: {schema['row_count']}\n"
        description += "Columns:\n"

        for col in schema["columns"]:
            col_type = str(col["type"])
            nullable = "NULL" if col["nullable"] else "NOT NULL"
            description += f"  {col['name']}: {col_type} {nullable}\n"

        if schema["primary_keys"]:
            description += f"Primary Keys: {', '.join(schema['primary_keys'])}\n"

        if schema["foreign_keys"]:
            description += "Foreign Keys:\n"
            for fk in schema["foreign_keys"]:
                description += f"  {', '.join(fk['columns'])} -> {fk['ref_table']}.{', '.join(fk['ref_columns'])}\n"

        description += "\n"

    return description
