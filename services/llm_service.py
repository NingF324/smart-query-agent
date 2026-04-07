"""
LLM 服务模块 - 统一管理 DeepSeek API 调用
支持 V3（生成）和 R1（推理）两种模型
优先使用 openai 库直接调用（轻量、无 torch 依赖）
"""
import os
import logging
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv

load_dotenv()


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMService:
    """LLM 服务封装 - 基于 openai 库直接调用 DeepSeek API"""

    def __init__(self,
                 api_key: Optional[str] = None,
                 base_url: str = "https://api.deepseek.com",
                 model_v3: str = "deepseek-chat",
                 model_r1: str = "deepseek-reasoner"):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url
        self.model_v3 = model_v3
        self.model_r1 = model_r1

        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY 未设置，LLM 服务将无法正常工作")

        self._client = None

        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=base_url,
            )
            logger.info(f"LLM 服务初始化成功 - V3: {model_v3}, R1: {model_r1}")
        except ImportError:
            logger.error("openai 库未安装，请执行: pip install openai")
        except Exception as e:
            logger.error(f"LLM 服务初始化失败: {e}")

    def _chat(self,
              system_prompt: str,
              user_message: str,
              model: str,
              temperature: float = 0,
              max_tokens: int = 4096) -> str:
        """调用 OpenAI 兼容 API。"""
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，无法调用 LLM")
        if self._client is None:
            raise RuntimeError("OpenAI 客户端未初始化")

        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # DeepSeek R1 reasoning_content 在 message.reasoning_content 中
        msg = response.choices[0].message
        return msg.content or ""

    def generate(self,
                 system_prompt: str,
                 user_message: str,
                 use_reasoner: bool = False,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 **kwargs) -> str:
        """调用 LLM 生成文本。"""
        model = self.model_r1 if use_reasoner else self.model_v3
        return self._chat(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            temperature=temperature if temperature is not None else 0,
            max_tokens=max_tokens or (8192 if use_reasoner else 4096),
        )

    def generate_with_messages(self,
                               messages: list,
                               use_reasoner: bool = False,
                               **kwargs) -> str:
        """使用自定义消息列表调用 LLM。"""
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置，无法调用 LLM")
        if self._client is None:
            raise RuntimeError("OpenAI 客户端未初始化")

        model = self.model_r1 if use_reasoner else self.model_v3
        openai_messages = []
        for msg in messages:
            role = getattr(msg, "type", None) or getattr(msg, "role", "user")
            content = getattr(msg, "content", str(msg))
            openai_messages.append({"role": role, "content": content})

        response = self._client.chat.completions.create(
            model=model,
            messages=openai_messages,
            temperature=0,
            max_tokens=8192 if use_reasoner else 4096,
        )
        return response.choices[0].message.content or ""

    def generate_sql(self,
                     schemas: str,
                     question: str,
                     intent: Optional[Dict[str, Any]] = None,
                     examples: str = "",
                     retry_hint: str = "",
                     dialect: str = "postgresql") -> str:
        """专用 SQL 生成接口。"""
        if dialect == "sqlite":
            system_prompt = """你是一个 SQLite SQL 专家。请根据用户问题、数据库结构和意图分析生成正确的 SQL。

## 核心规则

### 1. LIMIT 使用规则（非常重要！）
- 只在问题明确要求以下情况时使用 LIMIT：
  - "前N个"、"第N个"、"最多N个"、"最少N个"
  - "最大的N个"、"最小的N个"
  - "top N"、"first N"、"N items"
- 其他情况一律不加 LIMIT
- 不要为了"安全"或"限制结果数量"而主动添加 LIMIT

### 2. JOIN 类型选择规则
- 默认使用 INNER JOIN（简写为 JOIN）
- 只在以下情况使用 LEFT JOIN：
  - 问题明确要求"包括没有匹配的"、"显示所有...即使没有..."
  - 需要显示计数为 0 的结果
- 计数类查询（COUNT、SUM 等）通常使用 INNER JOIN
- GROUP BY + JOIN 通常使用 INNER JOIN，除非需要显示 0 计数

### 3. 值匹配精确性规则
- WHERE 条件中的值必须与数据库中的实际值完全一致
- 不要进行任何大小写转换：'France' 不要改成 'French'
- 不要使用同义词替换：'USA' 不要改成 'United States'
- 直接使用问题中出现的值，不要"智能"转换

### 4. 列别名规则
- 不要给列添加 AS 别名
- 错误示例：SELECT name AS person_name
- 正确示例：SELECT name

### 5. 外键关系理解规则
- 仔细区分 ID 字段和值字段
- 例如：CountryId（外键ID）vs CountryName（值字段）
- JOIN 时必须使用正确的外键关系
- 不要混淆表中的ID字段和实际值字段

## 其他规则

6. 只生成 SELECT 查询，禁止生成 INSERT/UPDATE/DELETE/DROP
7. 使用 SQLite 标准语法，注意：日期函数用 strftime、字符串用单引号、布尔用 0/1
8. 表名和字段名必须与 Schema 完全一致
9. 只输出 SQL，不加任何解释或 markdown 标记
10. 不要使用 PostgreSQL 特有语法（如 EXTRACT、DATE_TRUNC、::DECIMAL 等）
11. SELECT 列表：只选择问题要求的列，不要额外添加问题未提及的列
12. 不要添加 ORDER BY，除非用户问题明确要求排序或需要配合 LIMIT 取极值
13. 关于 DISTINCT：仅在问题明确要求"不同"、"不重复"、"唯一"时才使用 DISTINCT
14. 当问题中包含"包含"、"以...开头"、"以...结尾"、"类似"等词时，使用 LIKE 模糊匹配
15. 当问题涉及多个枚举值（如"A和B"、"A或B"）时，使用 IN 子句而非多个 OR
16. 不要使用 CAST 或类型转换函数，SQLite 会自动处理类型
17. 当问题涉及多个表的数据时，必须使用 JOIN 关联所有相关表，不要只查单表"""
        else:
            system_prompt = """你是一个 PostgreSQL SQL 专家。请根据用户问题、数据库结构和意图分析生成正确的 SQL。

## 规则
1. 只生成 SELECT 查询，禁止生成 INSERT/UPDATE/DELETE/DROP
2. 使用标准 SQL 语法，兼容 PostgreSQL
3. 表名和字段名必须与 Schema 完全一致
4. 关于 LIMIT：如果问题要求"第N个"、"最多"、"最少"、"最大的N个"等数量限制则加 LIMIT；否则不要加
5. 只输出 SQL，不加任何解释或 markdown 标记
6. 处理时间字段时使用 PostgreSQL 语法，如：order_date >= '2025-01-01'
7. SELECT 列表：只选择问题要求的列，不要额外添加问题未提及的列（如不要额外添加 COUNT(*) 列）
8. 不要给列添加 AS 别名（如 SELECT name AS 姓名 → 改为 SELECT name）
9. 不要添加 ORDER BY，除非用户问题明确要求排序（如"按...排序"、"从大到小"）或需要配合 LIMIT 取极值
10. 关于 DISTINCT：仅在问题明确要求"不同"、"不重复"、"唯一"时才使用 DISTINCT，其他情况不要加
11. 默认使用 INNER JOIN（写 JOIN 即可），不要使用 LEFT JOIN，除非必须保留左表所有行
12. WHERE 条件中的值必须与数据库中的实际值完全一致，不要将 'France' 改为 'French' 等同义词
13. 当问题中包含"包含"、"以...开头"、"以...结尾"、"类似"等词时，使用 LIKE 模糊匹配
14. 当问题涉及多个枚举值（如"A和B"、"A或B"）时，使用 IN 子句而非多个 OR
15. 不要使用 CAST 或类型转换函数，PostgreSQL 会自动处理类型
16. 当问题涉及多个表的数据时，必须使用 JOIN 关联所有相关表，不要只查单表"""

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
            use_reasoner=False,
        )

    def validate_and_fix_sql(self,
                             schemas: str,
                             question: str,
                             sql: str,
                             error: str) -> str:
        """SQL 校验和修复接口。"""
        system_prompt = """你是一个 SQL 修复专家。请根据以下信息修复 SQL 中的错误。

## 修复规则

### 核心原则
1. 只修复 SQL，不要改变原始查询意图

### 具体修复规则
2. 如果错误是字段名拼写错误，根据 Schema 修正
3. 如果错误是 JOIN 条件缺失，添加正确的 JOIN（优先使用 INNER JOIN）
4. 如果错误是语法错误，修正 SQL 语法
5. 如果错误是表名不存在，检查 Schema 中的表名

### 输出规则
6. 只输出修复后的 SQL，不要任何解释
7. 修复后不要添加 AS 别名
8. 修复后保留原始 SQL 的 LIMIT（如果有）
9. 修复后不要添加 ORDER BY 或 DISTINCT（除非原始 SQL 有且用户要求）
10. 不要使用 CAST 或类型转换函数
11. SELECT 列表：只选择问题要求的列，不要额外添加未提及的列
12. WHERE 条件中的值必须与数据库实际值一致，不要使用同义词替换

### JOIN 修复规则
13. 默认使用 INNER JOIN（简写 JOIN）
14. 只在需要保留左表所有行时使用 LEFT JOIN
15. 修复外键关系时，仔细区分 ID 字段和值字段
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
            use_reasoner=True,
        )

    def interpret_result(self,
                         question: str,
                         sql: str,
                         result: List[Dict[str, Any]]) -> str:
        """结果解释接口。"""
        system_prompt = """你是一个数据分析师助手。请将 SQL 查询结果用自然语言向用户解释。

## 解释规则
1. 用简洁的中文解释结果
2. 对于数值结果，突出关键数据
3. 如果结果为空，说明可能的原因
4. 不要重复用户的问题
"""

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
            use_reasoner=False,
        )

    def health_check(self) -> bool:
        """健康检查。"""
        if not self.api_key:
            logger.warning("LLM 健康检查失败：API Key 未设置")
            return False
        try:
            response = self.generate(
                system_prompt="你是一个测试助手。",
                user_message="请回复 OK",
                use_reasoner=False,
            )
            ok = "OK" in response or "ok" in response
            if ok:
                logger.info("LLM 健康检查通过")
            else:
                logger.warning(f"LLM 响应异常: {response}")
            return ok
        except Exception as e:
            logger.error(f"LLM 健康检查失败: {e}")
            return False


# 创建全局单例（可选）
_llm_service_instance: Optional[LLMService] = None


def get_llm_service(api_key: Optional[str] = None,
                    base_url: Optional[str] = None) -> LLMService:
    """获取 LLM 服务单例。"""
    global _llm_service_instance

    if _llm_service_instance is None:
        _llm_service_instance = LLMService(
            api_key=api_key,
            base_url=base_url or "https://api.deepseek.com"
        )

    return _llm_service_instance
