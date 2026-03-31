"""
Schema 检索节点 - 根据意图检索相关的数据库表结构
"""
import logging
from typing import Dict, Any
from agent.state import AgentState
from services.knowledge_base import KnowledgeBase
from services.db_service import get_state_db_service


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
    resolved_question = state.get("resolved_question") or question
    intent = state.get("intent", {})

    logger.info(f"[Schema Retrieve] Retrieving schemas for question: {resolved_question}")


    try:
        # 初始化数据库服务
        db_service = get_state_db_service(state)

        retrieved_tables = []

        # 尝试从知识库语义检索（可能因 onnxruntime 不可用而失败）
        try:
            kb = KnowledgeBase()
            search_query = resolved_question
            entities = intent.get("entities", [])
            if entities:
                search_query += " " + " ".join(entities)

            logger.info(f"[Schema Retrieve] Search query: {search_query}")
            search_results = kb.search_ddl(search_query, n_results=5)
            logger.info(f"[Schema Retrieve] Found {len(search_results)} related schemas from KB")

            for result in search_results:
                table_name = result["metadata"].get("table_name", "")
                if table_name and table_name not in retrieved_tables:
                    retrieved_tables.append(table_name)
        except Exception as kb_err:
            logger.warning(f"[Schema Retrieve] KB search failed ({kb_err}), falling back to DB direct")

        # 降级：从数据库直接获取所有表
        if not retrieved_tables:
            logger.info("[Schema Retrieve] Getting all tables from database directly")
            retrieved_tables = db_service.get_table_names()

        # 获取表的完整信息
        relevant_schemas = []
        for table_name in retrieved_tables[:10]:  # 最多检索10张表
            # Strip db_id prefix (e.g., "concert_singer.singer" -> "singer")
            actual_table = table_name.split('.')[-1] if '.' in table_name else table_name
            try:
                table_info = db_service.get_table_info(actual_table)
                ddl = db_service.get_table_schema(actual_table)

                relevant_schemas.append({
                    "table_name": actual_table,
                    "ddl": ddl,
                    "columns": table_info["columns"],
                    "row_count": table_info["row_count"],
                    "primary_keys": table_info["primary_keys"],
                    "foreign_keys": table_info["foreign_keys"]
                })

                logger.info(f"[Schema Retrieve] Added table: {actual_table} ({table_info['row_count']} rows)")

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




