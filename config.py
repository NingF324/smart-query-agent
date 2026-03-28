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
