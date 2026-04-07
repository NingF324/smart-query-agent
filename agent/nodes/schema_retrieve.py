"""
Schema retrieval node: retrieve relevant table schemas for SQL generation.
"""
import logging
import re
from typing import Any, Dict, Iterable, List, Tuple

from agent.state import AgentState
from config import SCHEMA_MAX_TABLES, SCHEMA_MIN_SCORE
from services.db_service import get_state_db_service
from services.knowledge_base import get_knowledge_base


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def schema_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """Retrieve candidate schemas using KB results and intent-based scoring fallback."""
    question = state["question"]
    resolved_question = state.get("resolved_question") or question
    intent = state.get("intent", {})

    logger.info(f"[Schema Retrieve] Retrieving schemas for question: {resolved_question}")

    try:
        db_service = get_state_db_service(state)
        all_tables = db_service.get_table_names()

        keywords = build_schema_keywords(resolved_question, intent)
        kb_tables = search_tables_from_kb(resolved_question, intent)
        selected_tables = choose_tables(
            all_tables=all_tables,
            kb_tables=kb_tables,
            keywords=keywords,
            max_tables=SCHEMA_MAX_TABLES,
            min_score=SCHEMA_MIN_SCORE,
        )

        relevant_schemas: List[Dict[str, Any]] = []
        for table_name in selected_tables:
            actual_table = normalize_table_name(table_name)
            try:
                table_info = db_service.get_table_info(actual_table)
                ddl = db_service.get_table_schema(actual_table)
                relevant_schemas.append(
                    {
                        "table_name": actual_table,
                        "ddl": ddl,
                        "columns": table_info["columns"],
                        "row_count": table_info["row_count"],
                        "primary_keys": table_info["primary_keys"],
                        "foreign_keys": table_info["foreign_keys"],
                    }
                )
                logger.info(
                    "[Schema Retrieve] Added table: %s (%s rows)",
                    actual_table,
                    table_info["row_count"],
                )
            except Exception as exc:
                logger.warning("[Schema Retrieve] Failed to get info for %s: %s", table_name, exc)

        logger.info(
            "[Schema Retrieve] Retrieved %s schemas from %s selected tables",
            len(relevant_schemas),
            len(selected_tables),
        )
        return {"relevant_schemas": relevant_schemas, "messages": state["messages"]}

    except Exception as exc:
        logger.error(f"[Schema Retrieve] Error: {exc}")
        return {"relevant_schemas": [], "messages": state["messages"]}


def search_tables_from_kb(resolved_question: str, intent: Dict[str, Any]) -> List[str]:
    """Search candidate tables from knowledge base DDL entries."""
    try:
        kb = get_knowledge_base()
        search_query = resolved_question
        entities = intent.get("entities", [])
        if entities:
            search_query += " " + " ".join(str(e) for e in entities)

        logger.info(f"[Schema Retrieve] KB search query: {search_query}")
        search_results = kb.search_ddl(search_query, n_results=8)
        kb_tables: List[str] = []
        for result in search_results:
            table_name = str(result.get("metadata", {}).get("table_name", "")).strip()
            if table_name and table_name not in kb_tables:
                kb_tables.append(table_name)

        logger.info("[Schema Retrieve] KB candidates: %s", kb_tables)
        return kb_tables
    except Exception as exc:
        logger.warning("[Schema Retrieve] KB search failed (%s), fallback to DB ranking", exc)
        return []


def choose_tables(
    all_tables: List[str],
    kb_tables: List[str],
    keywords: List[str],
    max_tables: int,
    min_score: int,
) -> List[str]:
    """Choose final tables: KB candidates first, then score-ranked DB tables."""
    selected: List[str] = []
    seen_normalized: set[str] = set()

    def add_table(table_name: str) -> None:
        normalized = normalize_table_name(table_name)
        if not normalized or normalized in seen_normalized:
            return
        selected.append(table_name)
        seen_normalized.add(normalized)

    # Keep KB ordering, but only if table exists in current DB (by normalized name).
    normalized_index = {normalize_table_name(name): name for name in all_tables}
    for kb_name in kb_tables:
        normalized = normalize_table_name(kb_name)
        if normalized in normalized_index:
            add_table(normalized_index[normalized])

    # Add score-ranked tables to fill coverage gaps.
    scored = rank_tables(all_tables, keywords)
    for table_name, score in scored:
        if len(selected) >= max_tables:
            break
        if score >= min_score:
            add_table(table_name)

    # Safety fallback: never return empty candidate set when DB has tables.
    if not selected:
        for table_name, _score in scored[:max_tables]:
            add_table(table_name)

    return selected[:max_tables]


def rank_tables(all_tables: List[str], keywords: List[str]) -> List[Tuple[str, int]]:
    """Rank tables by name overlap with extracted keywords."""
    scored: List[Tuple[str, int]] = []
    for table_name in all_tables:
        score = score_table_name(table_name, keywords)
        scored.append((table_name, score))

    # Higher score first, then stable lexical order for deterministic results.
    scored.sort(key=lambda item: (-item[1], normalize_table_name(item[0])))
    return scored


def score_table_name(table_name: str, keywords: List[str]) -> int:
    """Score a table against current keywords; higher means more relevant."""
    name = normalize_table_name(table_name)
    score = 0

    # Generic boosts for common analytical tables.
    if name in {"orders", "order_items", "users", "products", "reviews"}:
        score += 1

    for keyword in keywords:
        key = keyword.lower().strip()
        if not key:
            continue
        if key == name:
            score += 6
        elif key in name or name in key:
            score += 3
        else:
            key_parts = set(split_tokens(key))
            name_parts = set(split_tokens(name))
            if key_parts and name_parts and key_parts.intersection(name_parts):
                score += 2

    return score


def build_schema_keywords(resolved_question: str, intent: Dict[str, Any]) -> List[str]:
    """Build retrieval keywords from question + intent metadata."""
    keywords: List[str] = []

    entities = intent.get("entities", [])
    for entity in entities:
        token = str(entity).strip().lower()
        if token and token not in keywords:
            keywords.append(token)

    for hint in intent.get("schema_hints", []):
        token = str(hint).strip().lower()
        if token and token not in keywords:
            keywords.append(token)

    query_type = str(intent.get("query_type", "")).strip().lower()
    if query_type and query_type != "unknown" and query_type not in keywords:
        keywords.append(query_type)

    for token in split_tokens(resolved_question.lower()):
        if len(token) >= 2 and token not in keywords:
            keywords.append(token)

    return keywords


def normalize_table_name(table_name: str) -> str:
    """Normalize table name by removing db prefix and lowercasing."""
    value = str(table_name).strip()
    if "." in value:
        value = value.split(".")[-1]
    return value.lower()


def split_tokens(text: str) -> Iterable[str]:
    """Split text into alnum tokens."""
    return [token for token in re.split(r"[^a-zA-Z0-9_]+", str(text)) if token]
