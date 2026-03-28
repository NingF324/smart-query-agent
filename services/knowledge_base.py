"""
知识库服务模块 - 基于 ChromaDB 的向量数据库
用于存储和检索数据库 Schema 信息和 SQL 示例
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeBase:
    """ChromaDB 知识库服务"""

    def __init__(self,
                 collection_name: str = "smart_query_kb",
                 host: Optional[str] = None,
                 port: Optional[int] = None):
        """
        初始化知识库

        Args:
            collection_name: 集合名称
            host: ChromaDB 服务端地址
            port: ChromaDB 服务端端口
        """
        self.collection_name = collection_name
        self.host = host or os.getenv("CHROMA_HOST", "localhost")
        self.port = port or int(os.getenv("CHROMA_PORT", "8000"))

        try:
            import chromadb
            from chromadb.config import Settings

            # 连接到 ChromaDB 服务端
            self.client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
                settings=Settings(allow_reset=True)
            )

            # 获取或创建集合
            try:
                self.collection = self.client.get_collection(name=collection_name)
                logger.info(f"✅ 知识库已加载集合: {collection_name}")
            except Exception:
                self.collection = self.client.create_collection(name=collection_name)
                logger.info(f"✅ 知识库已创建集合: {collection_name}")

            # 获取当前数据量
            count = self.collection.count()
            logger.info(f"📊 知识库当前数据量: {count} 条")

        except ImportError as e:
            logger.error(f"❌ 导入 chromadb 失败: {e}")
            logger.error("请安装依赖: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"❌ 知识库初始化失败: {e}")
            raise

    def add_ddl(self,
                 table_name: str,
                 ddl: str,
                 columns: List[Dict[str, Any]],
                 description: str = ""):
        """
        添加表 DDL 到知识库

        Args:
            table_name: 表名
            ddl: DDL 语句
            columns: 列信息列表
            description: 表描述
        """
        try:
            # 构建文档内容
            column_info = "\n".join([
                f"- {col['name']}: {col['type']}"
                for col in columns
            ])

            document = f"""表名: {table_name}
描述: {description or '无'}
DDL:
{ddl}

列信息:
{column_info}
"""

            # 元数据
            metadata = {
                "type": "ddl",
                "table_name": table_name,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "column_count": len(columns)
            }

            # 添加到集合
            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[f"ddl_{table_name}"]
            )

            logger.info(f"✅ 已添加 DDL: {table_name}")

        except Exception as e:
            logger.error(f"❌ 添加 DDL 失败: {e}")
            raise

    def add_sql_example(self,
                         question: str,
                         sql: str,
                         table_name: str = "",
                         description: str = ""):
        """
        添加 SQL 示例到知识库

        Args:
            question: 用户问题
            sql: SQL 语句
            table_name: 涉及的表名
            description: 描述
        """
        try:
            # 文档内容
            document = f"""问题: {question}
SQL:
{sql}

描述: {description or '无'}
涉及的表: {table_name or '无'}
"""

            # 元数据
            metadata = {
                "type": "sql_example",
                "question": question,
                "table_name": table_name,
                "description": description,
                "created_at": datetime.now().isoformat()
            }

            # 使用问题作为 ID（去除特殊字符）
            id_suffix = question.lower().replace(" ", "_")[:50]
            doc_id = f"sql_{id_suffix}"

            # 添加到集合
            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[doc_id]
            )

            logger.info(f"✅ 已添加 SQL 示例: {question[:50]}...")

        except Exception as e:
            logger.error(f"❌ 添加 SQL 示例失败: {e}")
            raise

    def add_business_term(self,
                          term: str,
                          definition: str,
                          related_table: str = ""):
        """
        添加业务术语到知识库

        Args:
            term: 术语名称
            definition: 术语定义
            related_table: 相关表名
        """
        try:
            # 文档内容
            document = f"""术语: {term}
定义: {definition}
相关表: {related_table or '无'}
"""

            # 元数据
            metadata = {
                "type": "business_term",
                "term": term,
                "related_table": related_table,
                "created_at": datetime.now().isoformat()
            }

            # 添加到集合
            doc_id = f"term_{term.lower().replace(' ', '_')}"
            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[doc_id]
            )

            logger.info(f"✅ 已添加业务术语: {term}")

        except Exception as e:
            logger.error(f"❌ 添加业务术语失败: {e}")
            raise

    def search(self,
               query: str,
               n_results: int = 5,
               where: Optional[Dict[str, Any]] = None,
               where_document: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        语义搜索

        Args:
            query: 查询文本
            n_results: 返回结果数量
            where: 元数据过滤条件
            where_document: 文档内容过滤条件

        Returns:
            List[Dict[str, Any]]: 搜索结果列表
        """
        try:
            logger.debug(f"🔍 搜索: {query[:50]}... (n={n_results})")

            # 构建查询参数
            query_params = {
                "query_texts": [query],
                "n_results": n_results
            }

            if where:
                query_params["where"] = where

            if where_document:
                query_params["where_document"] = where_document

            # 执行查询
            results = self.collection.query(**query_params)

            # 格式化结果
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    formatted_results.append({
                        "document": doc,
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else 0,
                        "id": results['ids'][0][i] if results['ids'] else ""
                    })

            logger.debug(f"✅ 搜索完成，返回 {len(formatted_results)} 条结果")
            return formatted_results

        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}")
            raise

    def search_ddl(self,
                    query: str,
                    n_results: int = 5) -> List[Dict[str, Any]]:
        """
        搜索 DDL（只返回 DDL 类型）

        Args:
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            List[Dict[str, Any]]: DDL 搜索结果
        """
        return self.search(
            query=query,
            n_results=n_results,
            where={"type": "ddl"}
        )

    def search_sql_examples(self,
                           query: str,
                           n_results: int = 3) -> List[Dict[str, Any]]:
        """
        搜索 SQL 示例

        Args:
            query: 查询文本
            n_results: 返回结果数量

        Returns:
            List[Dict[str, Any]]: SQL 示例搜索结果
        """
        return self.search(
            query=query,
            n_results=n_results,
            where={"type": "sql_example"}
        )

    def get_all_ddl(self) -> List[Dict[str, Any]]:
        """
        获取所有 DDL

        Returns:
            List[Dict[str, Any]]: 所有 DDL
        """
        try:
            results = self.collection.get(where={"type": "ddl"})

            formatted_results = []
            if results['documents']:
                for i, doc in enumerate(results['documents']):
                    formatted_results.append({
                        "document": doc,
                        "metadata": results['metadatas'][i] if results['metadatas'] else {},
                        "id": results['ids'][i] if results['ids'] else ""
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"❌ 获取 DDL 失败: {e}")
            raise

    def get_all_sql_examples(self) -> List[Dict[str, Any]]:
        """
        获取所有 SQL 示例

        Returns:
            List[Dict[str, Any]]: 所有 SQL 示例
        """
        try:
            results = self.collection.get(where={"type": "sql_example"})

            formatted_results = []
            if results['documents']:
                for i, doc in enumerate(results['documents']):
                    formatted_results.append({
                        "document": doc,
                        "metadata": results['metadatas'][i] if results['metadatas'] else {},
                        "id": results['ids'][i] if results['ids'] else ""
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"❌ 获取 SQL 示例失败: {e}")
            raise

    def delete_by_id(self, doc_id: str):
        """
        根据文档 ID 删除

        Args:
            doc_id: 文档 ID
        """
        try:
            self.collection.delete(ids=[doc_id])
            logger.info(f"✅ 已删除文档: {doc_id}")

        except Exception as e:
            logger.error(f"❌ 删除文档失败: {e}")
            raise

    def clear_collection(self):
        """清空集合"""
        try:
            count = self.collection.count()
            if count > 0:
                # Get all IDs and delete them
                results = self.collection.get()
                if results and results.get('ids'):
                    self.collection.delete(ids=results['ids'])
                    logger.info(f"✅ 已清空集合，删除 {count} 条记录")
                else:
                    logger.info("✅ 集合为空，无需清空")
            else:
                logger.info("✅ 集合为空，无需清空")

        except Exception as e:
            logger.error(f"❌ 清空集合失败: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        获取知识库统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            total_count = self.collection.count()

            # 获取各类型数量
            ddl_results = self.collection.get(where={"type": "ddl"})
            sql_results = self.collection.get(where={"type": "sql_example"})
            term_results = self.collection.get(where={"type": "business_term"})

            return {
                "total": total_count,
                "ddl_count": len(ddl_results['documents']) if ddl_results['documents'] else 0,
                "sql_example_count": len(sql_results['documents']) if sql_results['documents'] else 0,
                "business_term_count": len(term_results['documents']) if term_results['documents'] else 0,
                "collection_name": self.collection_name,
                "host": self.host,
                "port": self.port
            }

        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {
                "total": 0,
                "error": str(e)
            }

    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            bool: 知识库是否可用
        """
        try:
            # 尝试获取集合信息
            count = self.collection.count()
            logger.info(f"✅ 知识库健康检查通过 - 数据量: {count}")
            return True

        except Exception as e:
            logger.error(f"❌ 知识库健康检查失败: {e}")
            return False


# 创建全局单例
_knowledge_base_instance: Optional[KnowledgeBase] = None


def get_knowledge_base(host: Optional[str] = None,
                       port: Optional[int] = None) -> KnowledgeBase:
    """
    获取知识库单例

    Args:
        host: ChromaDB 服务端地址（仅首次创建时使用）
        port: ChromaDB 服务端端口（仅首次创建时使用）

    Returns:
        KnowledgeBase: 知识库实例
    """
    global _knowledge_base_instance

    if _knowledge_base_instance is None:
        _knowledge_base_instance = KnowledgeBase(
            host=host,
            port=port
        )

    return _knowledge_base_instance
