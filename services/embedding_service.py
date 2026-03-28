"""
Embedding 服务模块 - 支持多种 Embedding 方案
优先使用 API，失败时降级到本地模型
"""
import os
import logging
from typing import Optional, List
import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding 服务封装 - 支持 API 和本地模型"""

    def __init__(self,
                 api_key: Optional[str] = None,
                 base_url: str = "https://api.deepseek.com",
                 local_model: str = "BAAI/bge-small-zh-v1.5"):
        """
        初始化 Embedding 服务

        优先级：
        1. DeepSeek Embedding API（推荐）
        2. bge-small-zh 本地模型（降级）

        Args:
            api_key: DeepSeek API Key
            base_url: DeepSeek API 基础 URL
            local_model: 本地降级模型名称
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url
        self.embeddings = None
        self.mode = None

        try:
            # 方案1：尝试使用 DeepSeek Embedding API
            # DeepSeek 兼容 OpenAI Embedding 接口
            from langchain_openai import OpenAIEmbeddings

            if self.api_key:
                self.embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    api_key=self.api_key,
                    base_url=base_url
                )
                self.mode = "api"
                logger.info("✅ Embedding: 使用 DeepSeek API (text-embedding-3-small)")
            else:
                logger.warning("⚠️ DEEPSEEK_API_KEY 未设置，尝试使用本地模型")
                raise ValueError("No API key")

        except Exception as e:
            # 方案2：降级到本地 bge-small-zh 模型
            logger.warning(f"⚠️ Embedding API 连接失败: {e}")
            logger.info("🔄 降级到本地模型...")

            try:
                from langchain_community.embeddings import HuggingFaceEmbeddings

                self.embeddings = HuggingFaceEmbeddings(
                    model_name=local_model,
                    model_kwargs={'device': 'cpu'},  # CPU 推理
                    encode_kwargs={'normalize_embeddings': True}
                )
                self.mode = "local"
                logger.info(f"✅ Embedding: 使用本地模型 {local_model}")

            except ImportError as ie:
                logger.error(f"❌ 导入 HuggingFaceEmbeddings 失败: {ie}")
                logger.error("请安装依赖: pip install sentence-transformers")
                raise
            except Exception as le:
                logger.error(f"❌ 本地模型加载失败: {le}")
                logger.error(f"请确保已下载模型: {local_model}")
                raise

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        文本列表 → 向量列表

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 嵌入向量列表
        """
        if not texts:
            return []

        try:
            logger.debug(f"🔤 Embedding {len(texts)} 个文本 (模式: {self.mode})")
            vectors = self.embeddings.embed_documents(texts)
            logger.debug(f"✅ Embedding 完成，向量维度: {len(vectors[0])}")
            return vectors

        except Exception as e:
            logger.error(f"❌ Embedding 失败: {e}")
            raise

    def embed_query(self, text: str) -> List[float]:
        """
        单个文本 → 向量

        Args:
            text: 输入文本

        Returns:
            List[float]: 嵌入向量
        """
        try:
            vector = self.embeddings.embed_query(text)
            return vector

        except Exception as e:
            logger.error(f"❌ Embedding 失败: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """
        获取嵌入向量的维度

        Returns:
            int: 向量维度
        """
        try:
            # 使用测试文本获取维度
            test_vector = self.embed_query("测试")
            return len(test_vector)

        except Exception as e:
            logger.error(f"❌ 获取向量维度失败: {e}")
            # 根据模式返回默认维度
            if self.mode == "api":
                return 1536  # OpenAI text-embedding-3-small 维度
            else:
                return 384  # bge-small-zh 维度

    def batch_embed(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        批量嵌入 - 适用于大量文本

        Args:
            texts: 文本列表
            batch_size: 每批处理的文本数量

        Returns:
            List[List[float]]: 所有文本的嵌入向量
        """
        if not texts:
            return []

        all_vectors = []
        total = len(texts)

        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            vectors = self.embed(batch)
            all_vectors.extend(vectors)

            logger.debug(f"🔄 处理进度: {min(i + batch_size, total)}/{total}")

        return all_vectors

    def compute_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """
        计算两个向量的余弦相似度

        Args:
            vector1: 向量1
            vector2: 向量2

        Returns:
            float: 相似度分数 (0-1)
        """
        try:
            v1 = np.array(vector1)
            v2 = np.array(vector2)

            # 计算余弦相似度
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)

            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0

            similarity = dot_product / (norm_v1 * norm_v2)
            return float(similarity)

        except Exception as e:
            logger.error(f"❌ 计算相似度失败: {e}")
            return 0.0

    def health_check(self) -> bool:
        """
        健康检查 - 测试 Embedding 服务是否可用

        Returns:
            bool: 服务是否可用
        """
        try:
            # 测试嵌入功能
            test_text = "这是一个测试文本"
            vector = self.embed_query(test_text)

            is_healthy = len(vector) > 0

            if is_healthy:
                logger.info(f"✅ Embedding 健康检查通过 - 向量维度: {len(vector)}")
            else:
                logger.warning("⚠️ Embedding 返回空向量")

            return is_healthy

        except Exception as e:
            logger.error(f"❌ Embedding 健康检查失败: {e}")
            return False


# 创建全局单例
_embedding_service_instance: Optional[EmbeddingService] = None


def get_embedding_service(api_key: Optional[str] = None,
                           base_url: Optional[str] = None,
                           local_model: Optional[str] = None) -> EmbeddingService:
    """
    获取 Embedding 服务单例

    Args:
        api_key: API Key（仅首次创建时使用）
        base_url: Base URL（仅首次创建时使用）
        local_model: 本地模型名称（仅首次创建时使用）

    Returns:
        EmbeddingService: Embedding 服务实例
    """
    global _embedding_service_instance

    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService(
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com",
            local_model=local_model or "BAAI/bge-small-zh-v1.5"
        )

    return _embedding_service_instance
