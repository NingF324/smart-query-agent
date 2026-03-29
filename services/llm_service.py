"""
LLM 服务模块 - 统一管理 DeepSeek API 调用
支持 V3（生成）和 R1（推理）两种模型
"""
import os
import logging
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

load_dotenv()


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMService:
    """LLM 服务封装"""

    def __init__(self,
                 api_key: Optional[str] = None,
                 base_url: str = "https://api.deepseek.com",
                 model_v3: str = "deepseek-chat",
                 model_r1: str = "deepseek-reasoner"):
        """
        初始化 LLM 服务

        Args:
            api_key: DeepSeek API Key，如果为 None 则从环境变量读取
            base_url: DeepSeek API 基础 URL
            model_v3: V3 模型名称（默认：deepseek-chat）
            model_r1: R1 模型名称（默认：deepseek-reasoner）
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url

        if not self.api_key:
            logger.warning("⚠️ DEEPSEEK_API_KEY 未设置，LLM 服务将无法正常工作")

        # 延迟导入 LangChain DeepSeek，避免安装失败导致无法初始化
        try:
            from langchain_deepseek import ChatDeepSeek

            # 初始化 V3 模型（主要用于 SQL 生成）
            self.v3 = ChatDeepSeek(
                model=model_v3,
                api_key=self.api_key,
                base_url=base_url,
                temperature=0,  # SQL 生成需要确定性输出
                max_tokens=4096
            )

            # 初始化 R1 模型（用于复杂推理任务）
            self.r1 = ChatDeepSeek(
                model=model_r1,
                api_key=self.api_key,
                base_url=base_url,
                temperature=0,
                max_tokens=8192
            )

            logger.info(f"✅ LLM 服务初始化成功 - V3: {model_v3}, R1: {model_r1}")

        except ImportError as e:
            logger.error(f"❌ 导入 langchain_deepseek 失败: {e}")
            logger.error("请安装依赖: pip install langchain-deepseek")
            raise
        except Exception as e:
            logger.error(f"❌ LLM 服务初始化失败: {e}")
            raise

    def generate(self,
                 system_prompt: str,
                 user_message: str,
                 use_reasoner: bool = False,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 **kwargs) -> str:
        """
        调用 LLM 生成文本

        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            use_reasoner: 是否使用 R1 推理模型（默认使用 V3）
            temperature: 温度参数（覆盖默认值）
            max_tokens: 最大生成长度（覆盖默认值）
            **kwargs: 其他传递给模型的参数

        Returns:
            str: 生成的文本内容

        Raises:
            Exception: API 调用失败时抛出异常
        """
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，无法调用 LLM")

        try:
            model = self.r1 if use_reasoner else self.v3

            # 构建消息列表
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ]

            # 调用模型
            logger.debug(f"🤖 调用 LLM - 模型: {'R1' if use_reasoner else 'V3'}, "
                        f"系统提示长度: {len(system_prompt)}, "
                        f"用户消息长度: {len(user_message)}")

            response = model.invoke(messages, **kwargs)
            content = response.content

            logger.debug(f"✅ LLM 响应成功 - 生成内容长度: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"❌ LLM 调用失败: {e}")
            raise

    def generate_with_messages(self,
                               messages: List[BaseMessage],
                               use_reasoner: bool = False,
                               **kwargs) -> str:
        """
        使用自定义消息列表调用 LLM

        Args:
            messages: 消息列表（SystemMessage, HumanMessage, etc.）
            use_reasoner: 是否使用 R1 推理模型
            **kwargs: 其他传递给模型的参数

        Returns:
            str: 生成的文本内容
        """
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，无法调用 LLM")

        try:
            model = self.r1 if use_reasoner else self.v3
            response = model.invoke(messages, **kwargs)
            return response.content

        except Exception as e:
            logger.error(f"❌ LLM 调用失败: {e}")
            raise

    def generate_sql(self,
                     schemas: str,
                     question: str,
                     intent: Optional[Dict[str, Any]] = None,
                     examples: str = "",
                     retry_hint: str = "") -> str:
        """
        专用 SQL 生成接口

        Args:
            schemas: 数据库表结构描述
            question: 用户问题
            intent: 意图分析结果（可选）
            examples: 相似 SQL 示例（可选）
            retry_hint: 重试提示信息（当重试时提供错误信息）

        Returns:
            str: 生成的 SQL 语句
        """
        # SQL 生成系统提示词
        system_prompt = """你是一个 PostgreSQL SQL 专家。请根据用户问题、数据库结构和意图分析生成正确的 SQL。

## 规则
1. 只生成 SELECT 查询，禁止生成 INSERT/UPDATE/DELETE/DROP
2. 使用标准 SQL 语法，兼容 PostgreSQL
3. 表名和字段名必须与 Schema 完全一致
4. 大结果集加 LIMIT 100（除非用户明确要求全部）
5. 只输出 SQL，不加任何解释或 markdown 标记
6. 处理时间字段时使用 PostgreSQL 语法，如：order_date >= '2025-01-01'
"""

        # 构建用户消息
        user_message = f"""## 数据库 Schema
{schemas}

## 检索到的相似 SQL 示例
{examples or "无"}

## 用户问题
{question}

## 查询意图
{intent or {}}

{retry_hint}

请生成 SQL 查询语句："""

        return self.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            use_reasoner=False  # SQL 生成使用 V3 模型
        )

    def validate_and_fix_sql(self,
                             schemas: str,
                             question: str,
                             sql: str,
                             error: str) -> str:
        """
        SQL 校验和修复接口

        Args:
            schemas: 数据库表结构描述
            question: 原始用户问题
            sql: 失败的 SQL 语句
            error: 错误信息

        Returns:
            str: 修复后的 SQL 语句
        """
        system_prompt = """你是一个 SQL 修复专家。请根据以下信息修复 SQL 中的错误。

## 修复规则
1. 只修复 SQL，不要改变原始查询意图
2. 如果错误是字段名拼写错误，根据 Schema 修正
3. 如果错误是 JOIN 条件缺失，添加正确的 JOIN
4. 如果错误是语法错误，修正 SQL 语法
5. 如果错误是表名不存在，检查 Schema 中的表名
6. 只输出修复后的 SQL，不要任何解释
"""

        user_message = f"""## 数据库表结构
{schemas}

## 原始问题
{question}

## 执行失败的 SQL
```sql
{sql}
```

## 错误信息
{error}

请直接输出修复后的 SQL："""

        return self.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            use_reasoner=True  # 使用 R1 模型进行推理修复
        )

    def interpret_result(self,
                         question: str,
                         sql: str,
                         result: List[Dict[str, Any]]) -> str:
        """
        结果解释接口 - 将查询结果转换为自然语言描述

        Args:
            question: 用户问题
            sql: 执行的 SQL
            result: 查询结果

        Returns:
            str: 结果的自然语言描述
        """
        system_prompt = """你是一个数据分析师助手。请将 SQL 查询结果用自然语言向用户解释。

## 解释规则
1. 用简洁的中文解释结果
2. 对于数值结果，突出关键数据
3. 如果结果为空，说明可能的原因
4. 不要重复用户的问题
"""

        # 限制结果展示长度（避免 token 过多）
        limited_result = result[:20] if len(result) > 20 else result

        user_message = f"""## 用户问题
{question}

## 执行的 SQL
```sql
{sql}
```

## 查询结果
{limited_result}

（共 {len(result)} 条记录）

请用自然语言解释结果："""

        return self.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            use_reasoner=False
        )

    def health_check(self) -> bool:
        """
        健康检查 - 测试 LLM 服务是否可用

        Returns:
            bool: 服务是否可用
        """
        if not self.api_key:
            logger.warning("⚠️ LLM 健康检查失败：API Key 未设置")
            return False

        try:
            # 发送一个简单的测试请求
            response = self.generate(
                system_prompt="你是一个测试助手。",
                user_message="请回复 'OK'",
                use_reasoner=False
            )
            is_healthy = "OK" in response or "ok" in response

            if is_healthy:
                logger.info("✅ LLM 健康检查通过")
            else:
                logger.warning(f"⚠️ LLM 响应异常: {response}")

            return is_healthy

        except Exception as e:
            logger.error(f"❌ LLM 健康检查失败: {e}")
            return False


# 创建全局单例（可选）
_llm_service_instance: Optional[LLMService] = None


def get_llm_service(api_key: Optional[str] = None,
                    base_url: Optional[str] = None) -> LLMService:
    """
    获取 LLM 服务单例

    Args:
        api_key: API Key（仅首次创建时使用）
        base_url: Base URL（仅首次创建时使用）

    Returns:
        LLMService: LLM 服务实例
    """
    global _llm_service_instance

    if _llm_service_instance is None:
        _llm_service_instance = LLMService(
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com"
        )

    return _llm_service_instance
