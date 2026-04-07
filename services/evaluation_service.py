"""Week7 评测与指标统计服务。"""
import copy
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence


Runner = Callable[[str, Optional[List[Dict[str, Any]]]], Dict[str, Any]]
SqlValidator = Callable[[str], Dict[str, Any]]


@dataclass
class EvaluationCase:
    """单条评测样例。"""

    case_id: str
    question: str
    expected_sql: str = ""
    expected_result_sql: str = ""
    expected_result: List[Dict[str, Any]] = field(default_factory=list)
    chat_history: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "EvaluationCase":
        return cls(
            case_id=str(payload.get("case_id") or payload.get("id") or ""),
            question=str(payload.get("question") or ""),
            expected_sql=str(payload.get("expected_sql") or ""),
            expected_result_sql=str(payload.get("expected_result_sql") or ""),
            expected_result=list(payload.get("expected_result") or []),
            chat_history=list(payload.get("chat_history") or []),
            tags=[str(tag) for tag in payload.get("tags") or []],
            metadata=dict(payload.get("metadata") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SafetySqlCase:
    """SQL 安全测试样例。"""

    case_id: str
    sql: str
    expected_reason: str = ""
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SafetySqlCase":
        return cls(
            case_id=str(payload.get("case_id") or payload.get("id") or ""),
            sql=str(payload.get("sql") or ""),
            expected_reason=str(payload.get("expected_reason") or ""),
            tags=[str(tag) for tag in payload.get("tags") or []],
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_SQL_SPACE_RE = re.compile(r"\s+")
_SAFETY_HINTS = (
    "危险 sql 模式",
    "只允许 select 查询",
    "sql 不安全",
    "禁止使用分号或多语句",
)


def normalize_sql(sql: str) -> str:
    """标准化 SQL，用于 EM 对比。"""
    if not sql:
        return ""

    normalized = sql.strip().rstrip(";")
    normalized = _SQL_SPACE_RE.sub(" ", normalized)
    normalized = re.sub(r"\s*,\s*", ", ", normalized)
    normalized = re.sub(r"\s*([=<>]+)\s*", r"\1", normalized)
    normalized = re.sub(r"\(\s+", "(", normalized)
    normalized = re.sub(r"\s+\)", ")", normalized)
    return normalized.lower()



def normalize_value(value: Any) -> Any:
    """标准化单个值，避免类型差异导致 EX 误判。"""
    if isinstance(value, Decimal):
        return round(float(value), 6)
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): normalize_value(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    return value


def normalize_result_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """标准化结果集并按内容排序。"""
    normalized_rows: List[Dict[str, Any]] = []
    for row in rows or []:
        normalized_row = {
            str(key): normalize_value(value)
            for key, value in sorted(dict(row).items(), key=lambda item: str(item[0]))
        }
        normalized_rows.append(normalized_row)

    return sorted(
        normalized_rows,
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True),
    )


def compare_result_rows(actual_rows: Sequence[Dict[str, Any]], expected_rows: Sequence[Dict[str, Any]]) -> bool:
    """按无序集合比较查询结果。"""
    return normalize_result_rows(actual_rows) == normalize_result_rows(expected_rows)


def build_pipeline_runner(compiled_graph: Any = None) -> Runner:
    """构建多节点流水线 runner。"""
    if compiled_graph is None:
        from agent.graph import build_graph

        compiled_graph = build_graph()

    from agent.state import create_initial_state

    def runner(question: str, chat_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        state = create_initial_state(question, chat_history=copy.deepcopy(chat_history or []))
        return compiled_graph.invoke(state)

    return runner


def build_sql_validator() -> SqlValidator:
    """构建 SQL 安全校验器。"""
    from agent.nodes.sql_validate import sql_validate_node
    from agent.state import create_initial_state

    def validator(sql: str) -> Dict[str, Any]:
        state = create_initial_state("Week7 安全测试")
        state["generated_sql"] = sql
        return sql_validate_node(state)

    return validator


def is_safety_blocked(state: Dict[str, Any]) -> bool:
    """判断状态是否被安全策略拦截。"""
    execution_stats = dict(state.get("execution_stats") or {})
    if execution_stats.get("safety_blocked"):
        return True

    validation_result = dict(state.get("validation_result") or {})
    error_message = str(validation_result.get("error") or "").lower()
    return any(hint in error_message for hint in _SAFETY_HINTS)


def resolve_expected_rows(case: EvaluationCase, db_service: Any = None) -> List[Dict[str, Any]]:
    """获取样例期望结果。"""
    if case.expected_result:
        return case.expected_result

    if case.expected_result_sql:
        if db_service is None:
            raise ValueError(f"样例 {case.case_id} 需要 db_service 才能计算 expected_result_sql")
        return db_service.execute_query(case.expected_result_sql)

    return []


def evaluate_cases(
    cases: Sequence[EvaluationCase],
    runner: Runner,
    db_service: Any = None,
    label: str = "pipeline",
) -> Dict[str, Any]:
    """批量评测问答样例。"""
    results: List[Dict[str, Any]] = []

    for raw_case in cases:
        case = raw_case if isinstance(raw_case, EvaluationCase) else EvaluationCase.from_dict(raw_case)
        start_time = time.perf_counter()
        failure_reason = ""
        final_state: Dict[str, Any] = {}

        try:
            final_state = runner(case.question, case.chat_history)
        except Exception as exc:
            failure_reason = str(exc)
            final_state = {
                "generated_sql": "",
                "query_result": [],
                "validation_result": {"valid": False, "error": failure_reason},
                "execution_stats": {
                    "validation_attempted": False,
                    "validation_passed": False,
                    "fix_attempted": False,
                    "fix_success": False,
                    "safety_blocked": False,
                    "execution_attempted": False,
                    "execution_success": False,
                    "execution_error": failure_reason,
                },
            }
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        generated_sql = str(final_state.get("generated_sql") or "")
        validation_result = dict(final_state.get("validation_result") or {})
        query_result = list(final_state.get("query_result") or [])
        execution_stats = dict(final_state.get("execution_stats") or {})
        error_type = str(final_state.get("error_type") or "")
        expected_rows = resolve_expected_rows(case, db_service=db_service)

        em_measurable = bool(case.expected_sql)
        ex_measurable = bool(case.expected_result or case.expected_result_sql)
        exact_match = em_measurable and normalize_sql(generated_sql) == normalize_sql(case.expected_sql)
        execution_match = ex_measurable and compare_result_rows(query_result, expected_rows)
        valid_sql = bool(validation_result.get("valid")) or bool(execution_stats.get("execution_success"))

        results.append({
            "case_id": case.case_id,
            "question": case.question,
            "tags": case.tags,
            "chat_history": case.chat_history,
            "generated_sql": generated_sql,
            "validation_result": validation_result,
            "query_result": query_result,
            "latency_ms": latency_ms,
            "exact_match": exact_match,
            "execution_match": execution_match,
            "em_measurable": em_measurable,
            "ex_measurable": ex_measurable,
            "valid_sql": valid_sql,
            "fix_attempted": bool(execution_stats.get("fix_attempted")),
            "fix_success": bool(execution_stats.get("fix_success")),
            "safety_blocked": is_safety_blocked(final_state),
            "error_type": error_type or infer_error_type(
                failure_reason
                or str(validation_result.get("error") or execution_stats.get("execution_error") or "")
            ),
            "error": failure_reason or str(validation_result.get("error") or execution_stats.get("execution_error") or ""),
            "execution_stats": execution_stats,
        })

    summary = summarize_case_results(results)
    return {
        "label": label,
        "summary": summary,
        "results": results,
        "failures": [item for item in results if item["ex_measurable"] and not item["execution_match"]],
    }


def evaluate_safety_sql_cases(cases: Sequence[SafetySqlCase], validator: SqlValidator, label: str = "safety") -> Dict[str, Any]:
    """批量评测 SQL 注入/危险 SQL 拦截能力。"""
    results: List[Dict[str, Any]] = []

    for raw_case in cases:
        case = raw_case if isinstance(raw_case, SafetySqlCase) else SafetySqlCase.from_dict(raw_case)
        start_time = time.perf_counter()
        state = validator(case.sql)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        validation_result = dict(state.get("validation_result") or {})
        error_message = str(validation_result.get("error") or "")
        blocked = is_safety_blocked(state)

        results.append({
            "case_id": case.case_id,
            "sql": case.sql,
            "expected_reason": case.expected_reason,
            "tags": case.tags,
            "blocked": blocked,
            "latency_ms": latency_ms,
            "error": error_message,
        })

    total = len(results)
    blocked_count = sum(1 for item in results if item["blocked"])
    return {
        "label": label,
        "summary": {
            "total_cases": total,
            "blocked_cases": blocked_count,
            "block_rate": round(blocked_count / total * 100, 2) if total else 0.0,
            "avg_latency_ms": round(sum(item["latency_ms"] for item in results) / total, 2) if total else 0.0,
        },
        "results": results,
        "failures": [item for item in results if not item["blocked"]],
    }


def summarize_case_results(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总评测结果。"""
    total = len(results)
    em_results = [item for item in results if item.get("em_measurable")]
    ex_results = [item for item in results if item.get("ex_measurable")]
    valid_results = [item for item in results if item.get("valid_sql")]
    fix_attempts = [item for item in results if item.get("fix_attempted")]
    fix_successes = [item for item in fix_attempts if item.get("fix_success")]
    safety_results = [item for item in results if "safety" in item.get("tags", [])]
    safety_blocks = [item for item in safety_results if item.get("safety_blocked")]
    failed_results = [item for item in results if item.get("ex_measurable") and not item.get("execution_match")]
    failure_breakdown: Dict[str, int] = {}
    for item in failed_results:
        key = str(item.get("error_type") or "unknown")
        failure_breakdown[key] = failure_breakdown.get(key, 0) + 1

    return {
        "total_cases": total,
        "measured_em_cases": len(em_results),
        "exact_match_cases": sum(1 for item in em_results if item.get("exact_match")),
        "em_rate": round(sum(1 for item in em_results if item.get("exact_match")) / len(em_results) * 100, 2) if em_results else 0.0,
        "measured_ex_cases": len(ex_results),
        "execution_match_cases": sum(1 for item in ex_results if item.get("execution_match")),
        "ex_rate": round(sum(1 for item in ex_results if item.get("execution_match")) / len(ex_results) * 100, 2) if ex_results else 0.0,
        "valid_sql_cases": len(valid_results),
        "valid_sql_rate": round(len(valid_results) / total * 100, 2) if total else 0.0,
        "fix_attempt_cases": len(fix_attempts),
        "fix_success_cases": len(fix_successes),
        "fix_success_rate": round(len(fix_successes) / len(fix_attempts) * 100, 2) if fix_attempts else 0.0,
        "safety_case_count": len(safety_results),
        "safety_block_cases": len(safety_blocks),
        "safety_block_rate": round(len(safety_blocks) / len(safety_results) * 100, 2) if safety_results else 0.0,
        "failure_breakdown": failure_breakdown,
        "avg_latency_ms": round(sum(item.get("latency_ms", 0.0) for item in results) / total, 2) if total else 0.0,
    }


def infer_error_type(error_message: str) -> str:
    """Map free-form error messages to a compact error type label."""
    msg = str(error_message or "").lower()
    if not msg:
        return ""
    if "timeout" in msg:
        return "timeout"
    if "permission denied" in msg or "unsafe" in msg or "dangerous sql" in msg:
        return "permission_error"
    if "no sql generated" in msg or "sql is empty" in msg:
        return "no_sql"
    if "connection" in msg or "api" in msg:
        return "upstream_connection_error"
    if "syntax error" in msg or "does not exist" in msg:
        return "sql_error"
    return "execution_error"


def save_report(report: Dict[str, Any], output_path: str) -> None:
    """保存评测报告到 JSON 文件。"""
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
