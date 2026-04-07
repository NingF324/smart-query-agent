"""配置文件 - 从环境变量加载配置"""
import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DB_URI = os.getenv("DB_URI", "postgresql://postgres:password@127.0.0.1:55432/smart_query?client_encoding=utf8")


CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT", "10"))
SCHEMA_MAX_TABLES = int(os.getenv("SCHEMA_MAX_TABLES", "20"))
SCHEMA_MIN_SCORE = int(os.getenv("SCHEMA_MIN_SCORE", "1"))
DB_SERVICE_CACHE_SIZE = int(os.getenv("DB_SERVICE_CACHE_SIZE", "64"))
LLM_REQUEST_TIMEOUT = float(os.getenv("LLM_REQUEST_TIMEOUT", "30"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
LLM_RETRY_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", "0.8"))
