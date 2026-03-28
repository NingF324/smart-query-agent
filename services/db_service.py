"""
数据库服务模块 - 封装数据库连接、查询和安全校验
支持 PostgreSQL 和 SQLite
"""
import os
import logging
import re
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import threading
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.pool import QueuePool

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseService:
    """数据库服务 - 支持 PostgreSQL 和 SQLite"""

    # SQL 注入防护正则表达式
    DANGEROUS_PATTERNS = [
        r'--',                    # SQL 注释
        r'/\*.*?\*/',            # 多行注释
        r';\s*(\w+)',            # 多语句执行
        r'xp_cmdshell',           # SQL Server 命令执行
        r'exec\s*\(',            # 执行语句
        r'eval\s*\(',            # 评估语句
        r'drop\s+',              # 删除操作
        r'delete\s+',            # 删除操作
        r'truncate\s+',          # 清空表
        r'alter\s+',             # 修改表
        r'insert\s+',            # 插入操作（除了 INSERT INTO SELECT）
        r'update\s+.+?set',      # 更新操作
        r'grant\s+',             # 权限授予
        r'revoke\s+',            # 权限撤销
    ]

    def __init__(self,
                 db_uri: str,
                 pool_size: int = 5,
                 max_overflow: int = 10,
                 query_timeout: int = 10):
        """
        初始化数据库服务

        Args:
            db_uri: 数据库连接 URI
            pool_size: 连接池大小
            max_overflow: 连接池最大溢出数
            query_timeout: 查询超时时间（秒）
        """
        self.db_uri = db_uri
        self.query_timeout = query_timeout
        self._lock = threading.Lock()

        try:
            # 创建数据库引擎
            self.engine = create_engine(
                db_uri,
                poolclass=QueuePool,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_pre_ping=True,  # 连接健康检查
                echo=False  # 不输出 SQL 日志
            )

            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info(f"✅ 数据库服务初始化成功 - {db_uri}")

        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = None
        try:
            conn = self.engine.connect()
            yield conn
        finally:
            if conn:
                conn.close()

    def is_safe_sql(self, sql: str) -> tuple[bool, Optional[str]]:
        """
        检查 SQL 是否安全（防止 SQL 注入）

        Args:
            sql: SQL 语句

        Returns:
            tuple[bool, Optional[str]]: (是否安全, 错误信息)
        """
        if not sql or not sql.strip():
            return False, "SQL 语句为空"

        sql_lower = sql.lower().strip()

        # 只允许 SELECT 查询
        if not sql_lower.startswith('select'):
            return False, "只允许 SELECT 查询"

        # 检查危险模式
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_lower, re.IGNORECASE):
                return False, f"检测到危险 SQL 模式: {pattern}"

        return True, None

    def execute_query(self,
                       sql: str,
                       params: Optional[Dict[str, Any]] = None,
                       timeout: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        执行 SQL 查询（带超时控制）

        Args:
            sql: SQL 语句
            params: 查询参数
            timeout: 超时时间（秒），默认使用实例配置

        Returns:
            List[Dict[str, Any]]: 查询结果列表

        Raises:
            ValueError: SQL 不安全时
            TimeoutError: 查询超时
            SQLAlchemyError: 数据库错误
        """
        # 安全检查
        is_safe, error_msg = self.is_safe_sql(sql)
        if not is_safe:
            logger.warning(f"⚠️ 拒绝执行不安全的 SQL: {error_msg}")
            raise ValueError(f"SQL 不安全: {error_msg}")

        timeout = timeout or self.query_timeout

        try:
            logger.info(f"🔍 执行查询: {sql[:100]}...")

            with self.engine.connect() as conn:
                # 设置超时
                if 'postgresql' in self.db_uri:
                    # PostgreSQL 超时设置
                    conn.execute(text(f"SET statement_timeout TO {timeout * 1000}"))

                # 执行查询
                result = conn.execute(text(sql), params or {})

                # 转换为字典列表
                rows = []
                for row in result:
                    rows.append(dict(row._mapping))

                logger.info(f"✅ 查询执行成功 - 返回 {len(rows)} 行")
                return rows

        except OperationalError as e:
            if 'timeout' in str(e).lower() or 'statement timeout' in str(e).lower():
                logger.error(f"❌ 查询超时 ({timeout}秒)")
                raise TimeoutError(f"查询超时: {timeout}秒")
            raise

        except Exception as e:
            logger.error(f"❌ 查询执行失败: {e}")
            raise

    def explain_query(self, sql: str) -> Dict[str, Any]:
        """
        分析 SQL 执行计划（用于性能优化和验证）

        Args:
            sql: SQL 语句

        Returns:
            Dict[str, Any]: 执行计划信息
        """
        try:
            with self.engine.connect() as conn:
                # 检测数据库类型
                if 'postgresql' in self.db_uri:
                    explain_sql = f"EXPLAIN ANALYZE {sql}"
                    result = conn.execute(text(explain_sql))
                else:
                    explain_sql = f"EXPLAIN QUERY PLAN {sql}"
                    result = conn.execute(text(explain_sql))

                # 收集执行计划
                plan = []
                for row in result:
                    plan.append(str(row[0]))

                return {
                    "sql": sql,
                    "explain": plan,
                    "valid": True
                }

        except Exception as e:
            logger.warning(f"⚠️ EXPLAIN 失败: {e}")
            return {
                "sql": sql,
                "explain": [],
                "valid": False,
                "error": str(e)
            }

    def get_table_names(self) -> List[str]:
        """
        获取所有表名

        Returns:
            List[str]: 表名列表
        """
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            return tables

        except Exception as e:
            logger.error(f"❌ 获取表名失败: {e}")
            raise

    def get_table_schema(self, table_name: str) -> str:
        """
        获取表的 DDL 语句

        Args:
            table_name: 表名

        Returns:
            str: DDL 语句
        """
        try:
            inspector = inspect(self.engine)
            columns = inspector.get_columns(table_name)

            # 构建 DDL
            column_defs = []
            for col in columns:
                col_type = str(col['type'])
                nullable = '' if col['nullable'] else ' NOT NULL'
                default = f" DEFAULT {col['default']}" if col['default'] else ''
                column_defs.append(f"    {col['name']} {col_type}{nullable}{default}")

            ddl = f"CREATE TABLE {table_name} (\n"
            ddl += ",\n".join(column_defs)
            ddl += "\n);"

            return ddl

        except Exception as e:
            logger.error(f"❌ 获取表结构失败: {e}")
            raise

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        获取表的详细信息

        Args:
            table_name: 表名

        Returns:
            Dict[str, Any]: 表信息
        """
        try:
            inspector = inspect(self.engine)

            # 获取列信息
            columns = []
            for col in inspector.get_columns(table_name):
                columns.append({
                    "name": col['name'],
                    "type": str(col['type']),
                    "nullable": col['nullable'],
                    "default": col['default'],
                    "autoincrement": col['autoincrement']
                })

            # 获取主键
            primary_keys = inspector.get_pk_constraint(table_name).get('constrained_columns', [])

            # 获取外键
            foreign_keys = []
            for fk in inspector.get_foreign_keys(table_name):
                foreign_keys.append({
                    "columns": fk['constrained_columns'],
                    "ref_table": fk['referred_table'],
                    "ref_columns": fk['referred_columns']
                })

            return {
                "table_name": table_name,
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
                "row_count": self.get_row_count(table_name)
            }

        except Exception as e:
            logger.error(f"❌ 获取表信息失败: {e}")
            raise

    def get_row_count(self, table_name: str) -> int:
        """
        获取表的行数

        Args:
            table_name: 表名

        Returns:
            int: 行数
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                return count

        except Exception as e:
            logger.warning(f"⚠️ 获取行数失败: {e}")
            return 0

    def test_connection(self) -> bool:
        """
        测试数据库连接

        Returns:
            bool: 连接是否正常
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.scalar() == 1

        except Exception as e:
            logger.error(f"❌ 数据库连接测试失败: {e}")
            return False

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态
        """
        try:
            is_connected = self.test_connection()
            tables = self.get_table_names() if is_connected else []

            return {
                "connected": is_connected,
                "tables": tables,
                "table_count": len(tables),
                "status": "healthy" if is_connected else "unhealthy"
            }

        except Exception as e:
            return {
                "connected": False,
                "tables": [],
                "table_count": 0,
                "status": "error",
                "error": str(e)
            }


# 创建全局单例
_db_service_instance: Optional[DatabaseService] = None


def get_db_service(db_uri: Optional[str] = None) -> DatabaseService:
    """
    获取数据库服务单例

    Args:
        db_uri: 数据库 URI（仅首次创建时使用）

    Returns:
        DatabaseService: 数据库服务实例
    """
    global _db_service_instance

    if _db_service_instance is None:
        if not db_uri:
            from config import DB_URI
            db_uri = DB_URI

        _db_service_instance = DatabaseService(db_uri)


    return _db_service_instance
