"""LLM service wrapper for DeepSeek-compatible OpenAI API."""

import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMService:
    """Unified LLM access layer with timeout/retry and basic observability."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com",
        model_v3: str = "deepseek-chat",
        model_r1: str = "deepseek-reasoner",
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = base_url
        self.model_v3 = model_v3
        self.model_r1 = model_r1
        self.request_timeout = float(os.getenv("LLM_REQUEST_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
        self.retry_base_delay = float(os.getenv("LLM_RETRY_BASE_DELAY", "0.8"))

        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY is missing; LLM calls will fail.")

        self._client = None
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key, base_url=base_url)
            logger.info("LLM service initialized (v3=%s, r1=%s)", model_v3, model_r1)
        except ImportError:
            logger.error("openai package is missing. Install with: pip install openai")
        except Exception as exc:
            logger.error("LLM service init failed: %s", exc)

    def _should_retry(self, exc: Exception) -> bool:
        return isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError))

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = self.retry_base_delay * (2**attempt) + random.uniform(0, 0.15)
        time.sleep(delay)

    def _chat(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> str:
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is missing")
        if self._client is None:
            raise RuntimeError("OpenAI client is not initialized")

        request_id = str(uuid.uuid4())[:8]
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            start = time.perf_counter()
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.request_timeout,
                )
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.info(
                    "[LLM] request_id=%s model=%s attempt=%d elapsed_ms=%s",
                    request_id,
                    model,
                    attempt,
                    elapsed_ms,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.warning(
                    "[LLM] request_id=%s model=%s attempt=%d elapsed_ms=%s error=%s",
                    request_id,
                    model,
                    attempt,
                    elapsed_ms,
                    exc,
                )
                last_exc = exc
                if attempt < self.max_retries and self._should_retry(exc):
                    self._sleep_before_retry(attempt)
                    continue
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError("LLM call failed without explicit exception")

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        use_reasoner: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        model = self.model_r1 if use_reasoner else self.model_v3
        return self._chat(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            temperature=temperature if temperature is not None else 0,
            max_tokens=max_tokens or (8192 if use_reasoner else 4096),
        )

    def generate_with_messages(self, messages: list, use_reasoner: bool = False, **kwargs) -> str:
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is missing")
        if self._client is None:
            raise RuntimeError("OpenAI client is not initialized")

        model = self.model_r1 if use_reasoner else self.model_v3
        openai_messages = []
        for msg in messages:
            role = getattr(msg, "type", None) or getattr(msg, "role", "user")
            content = getattr(msg, "content", str(msg))
            openai_messages.append({"role": role, "content": content})

        request_id = str(uuid.uuid4())[:8]
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            start = time.perf_counter()
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                    temperature=0,
                    max_tokens=8192 if use_reasoner else 4096,
                    timeout=self.request_timeout,
                )
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.info(
                    "[LLM] request_id=%s model=%s attempt=%d elapsed_ms=%s messages_mode=true",
                    request_id,
                    model,
                    attempt,
                    elapsed_ms,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.warning(
                    "[LLM] request_id=%s model=%s attempt=%d elapsed_ms=%s messages_mode=true error=%s",
                    request_id,
                    model,
                    attempt,
                    elapsed_ms,
                    exc,
                )
                last_exc = exc
                if attempt < self.max_retries and self._should_retry(exc):
                    self._sleep_before_retry(attempt)
                    continue
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError("LLM messages call failed without explicit exception")

    def generate_sql(
        self,
        schemas: str,
        question: str,
        intent: Optional[Dict[str, Any]] = None,
        examples: str = "",
        retry_hint: str = "",
        dialect: str = "postgresql",
    ) -> str:
        dialect_name = "SQLite" if dialect == "sqlite" else "PostgreSQL"
        system_prompt = (
            f"You are an expert {dialect_name} SQL generator. "
            "Generate exactly one read-only SQL statement. "
            "Rules: only SELECT/CTE; no INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE; "
            "return SQL text only without markdown."
        )

        user_message = f"""Database Schema:
{schemas}

Relevant SQL Examples:
{examples or 'None'}

Question:
{question}

Intent:
{intent or {}}

{retry_hint}

Output one SQL query only."""

        return self.generate(system_prompt=system_prompt, user_message=user_message, use_reasoner=False)

    def validate_and_fix_sql(self, schemas: str, question: str, sql: str, error: str) -> str:
        system_prompt = (
            "You are an SQL fixer. Repair the SQL while preserving user intent. "
            "Output SQL only, no markdown."
        )
        user_message = f"""Schema:
{schemas}

Question:
{question}

SQL:
{sql}

Error:
{error}

Return fixed SQL only."""
        return self.generate(system_prompt=system_prompt, user_message=user_message, use_reasoner=True)

    def interpret_result(self, question: str, sql: str, result: List[Dict[str, Any]]) -> str:
        system_prompt = "You are a data analyst assistant. Explain SQL results in concise Chinese."
        limited_result = result[:20] if len(result) > 20 else result
        user_message = f"""Question:
{question}

SQL:
{sql}

Result:
{limited_result}

Total rows: {len(result)}"""
        return self.generate(system_prompt=system_prompt, user_message=user_message, use_reasoner=False)

    def health_check(self) -> bool:
        if not self.api_key:
            logger.warning("LLM health check failed: missing API key")
            return False
        try:
            response = self.generate(
                system_prompt="You are a test assistant.",
                user_message="Reply with OK",
                use_reasoner=False,
            )
            ok = "ok" in response.lower()
            if ok:
                logger.info("LLM health check passed")
            else:
                logger.warning("LLM unexpected health response: %s", response)
            return ok
        except Exception as exc:
            logger.error("LLM health check failed: %s", exc)
            return False


_llm_service_instance: Optional[LLMService] = None


def get_llm_service(api_key: Optional[str] = None, base_url: Optional[str] = None) -> LLMService:
    """Get singleton LLM service instance."""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService(api_key=api_key, base_url=base_url or "https://api.deepseek.com")
    return _llm_service_instance
