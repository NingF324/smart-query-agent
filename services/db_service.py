"""Database service: query execution, safety checks, schema introspection, and shared cache."""

import logging
import os
import re
import threading
from collections import OrderedDict
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import QueuePool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseService:
    """Database service supporting PostgreSQL and SQLite."""

    DANGEROUS_PATTERNS = [
        r"--",
        r"/\*.*?\*/",
        r"xp_cmdshell",
        r"exec\s*\(",
        r"eval\s*\(",
        r"\bdrop\b",
        r"\bdelete\b",
        r"\btruncate\b",
        r"\balter\b",
        r"\binsert\b",
        r"\bupdate\b",
        r"\bgrant\b",
        r"\brevoke\b",
    ]

    def __init__(self, db_uri: str, pool_size: int = 5, max_overflow: int = 10, query_timeout: int = 10):
        self.db_uri = db_uri
        self.query_timeout = query_timeout
        self._lock = threading.Lock()

        self.engine = create_engine(
            db_uri,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            echo=False,
        )

        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        logger.info("Database service initialized: %s", db_uri)

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = self.engine.connect()
            yield conn
        finally:
            if conn is not None:
                conn.close()

    def is_safe_sql(self, sql: str) -> Tuple[bool, Optional[str]]:
        if not sql or not sql.strip():
            return False, "SQL is empty"

        normalized_sql = sql.strip()
        sql_lower = normalized_sql.lower()

        if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
            return False, "Only SELECT/CTE queries are allowed"

        # Allow one trailing semicolon, but reject multi-statement SQL.
        if ";" in normalized_sql:
            stripped = normalized_sql.rstrip()
            if stripped.endswith(";"):
                body = stripped[:-1]
                if ";" in body:
                    return False, "Detected dangerous SQL pattern: multi-statement is not allowed"
            else:
                return False, "Detected dangerous SQL pattern: multi-statement is not allowed"

        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_lower, re.IGNORECASE | re.DOTALL):
                return False, f"Detected dangerous SQL pattern: {pattern}"

        return True, None

    def execute_query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        is_safe, error_msg = self.is_safe_sql(sql)
        if not is_safe:
            logger.warning("Unsafe SQL blocked: %s", error_msg)
            raise ValueError(f"SQL unsafe: {error_msg}")

        timeout = timeout or self.query_timeout

        try:
            with self.engine.connect() as conn:
                if "postgresql" in self.db_uri:
                    conn.execute(text(f"SET statement_timeout TO {timeout * 1000}"))
                elif "sqlite" in self.db_uri:
                    conn.execute(text(f"PRAGMA busy_timeout = {timeout * 1000}"))

                result = conn.execute(text(sql), params or {})
                return [dict(row._mapping) for row in result]

        except OperationalError as exc:
            msg = str(exc).lower()
            if "timeout" in msg or "statement timeout" in msg:
                raise TimeoutError(f"Query timeout: {timeout}s") from exc
            raise

    def explain_query(self, sql: str) -> Dict[str, Any]:
        try:
            with self.engine.connect() as conn:
                if "sqlite" in self.db_uri:
                    explain_sql = f"EXPLAIN QUERY PLAN {sql}"
                else:
                    explain_sql = f"EXPLAIN {sql}"

                result = conn.execute(text(explain_sql))
                plan = [str(row[0]) for row in result]
                return {"sql": sql, "explain": plan, "valid": True}
        except Exception as exc:
            return {"sql": sql, "explain": [], "valid": False, "error": str(exc)}

    def get_table_names(self) -> List[str]:
        return inspect(self.engine).get_table_names()

    def get_table_schema(self, table_name: str) -> str:
        columns = inspect(self.engine).get_columns(table_name)
        defs = []
        for col in columns:
            col_type = str(col["type"])
            nullable = "" if col["nullable"] else " NOT NULL"
            default = f" DEFAULT {col['default']}" if col.get("default") else ""
            defs.append(f"    {col['name']} {col_type}{nullable}{default}")

        ddl = f"CREATE TABLE {table_name} (\n"
        ddl += ",\n".join(defs)
        ddl += "\n);"
        return ddl

    def get_row_count(self, table_name: str) -> int:
        try:
            with self.engine.connect() as conn:
                return int(conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar())
        except Exception:
            return 0

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        inspector = inspect(self.engine)
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append(
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                    "default": col["default"],
                    "autoincrement": col.get("autoincrement", False),
                }
            )

        primary_keys = inspector.get_pk_constraint(table_name).get("constrained_columns", [])
        foreign_keys = []
        for fk in inspector.get_foreign_keys(table_name):
            foreign_keys.append(
                {
                    "columns": fk["constrained_columns"],
                    "ref_table": fk["referred_table"],
                    "ref_columns": fk["referred_columns"],
                }
            )

        return {
            "table_name": table_name,
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "row_count": self.get_row_count(table_name),
        }

    def test_connection(self) -> bool:
        try:
            with self.engine.connect() as conn:
                return conn.execute(text("SELECT 1")).scalar() == 1
        except Exception:
            return False

    def health_check(self) -> Dict[str, Any]:
        try:
            connected = self.test_connection()
            tables = self.get_table_names() if connected else []
            return {
                "connected": connected,
                "tables": tables,
                "table_count": len(tables),
                "status": "healthy" if connected else "unhealthy",
            }
        except Exception as exc:
            return {
                "connected": False,
                "tables": [],
                "table_count": 0,
                "status": "error",
                "error": str(exc),
            }


_db_service_instance: Optional[DatabaseService] = None
_db_service_instance_lock = threading.Lock()
_db_service_cache: "OrderedDict[str, DatabaseService]" = OrderedDict()
_db_service_cache_lock = threading.Lock()
DB_SERVICE_CACHE_SIZE = int(os.getenv("DB_SERVICE_CACHE_SIZE", "64"))


def get_state_db_service(state) -> DatabaseService:
    """Get/create DatabaseService by db_uri with thread-safe LRU cache."""
    db_uri = state.get("db_uri") if hasattr(state, "get") else None
    if not db_uri:
        return get_db_service()

    with _db_service_cache_lock:
        existing = _db_service_cache.pop(db_uri, None)
        if existing is not None:
            _db_service_cache[db_uri] = existing
            return existing

        service = DatabaseService(db_uri)
        _db_service_cache[db_uri] = service

        while len(_db_service_cache) > DB_SERVICE_CACHE_SIZE:
            evicted_uri, evicted_service = _db_service_cache.popitem(last=False)
            try:
                evicted_service.engine.dispose()
            except Exception:
                pass
            logger.info("[DB Cache] Evicted cached DatabaseService for URI: %s", evicted_uri)

        return service


def get_db_service(db_uri: Optional[str] = None) -> DatabaseService:
    """Get/create singleton DatabaseService with thread-safe initialization."""
    global _db_service_instance

    if _db_service_instance is not None:
        return _db_service_instance

    with _db_service_instance_lock:
        if _db_service_instance is None:
            if not db_uri:
                from config import DB_URI

                db_uri = DB_URI
            _db_service_instance = DatabaseService(db_uri)

    return _db_service_instance
