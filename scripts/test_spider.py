"""
Spider dataset test runner and evaluation script.
Supports full dataset evaluation with structured output, charts, and JSON/CSV export.

Usage:
  python scripts/test_spider.py                          # run all dev.json cases
  python scripts/test_spider.py --max-tests 50           # first 50 cases
  python scripts/test_spider.py --db-list concert_singer car_1  # specific DBs
  python scripts/test_spider.py --skip-errors false      # don't skip error cases
"""

import json
import time
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from agent.graph import build_graph
from agent.state import create_initial_state


# ── Data ─────────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    """Single test result."""
    index: int
    db_id: str
    question: str
    gold_sql: str
    predicted_sql: str
    execution_time: float
    error: Optional[str] = None
    exact_result_match: bool = False
    exact_sql_match: bool = False


# ── SQL helpers ──────────────────────────────────────────────────────────────

def normalize_sql(sql: str) -> str:
    sql = re.sub(r'\s+', ' ', sql.strip())
    sql = sql.lower()
    return sql


def check_exact_sql_match(gold_sql: str, pred_sql: str) -> bool:
    return normalize_sql(gold_sql) == normalize_sql(pred_sql)


def execute_sql_result(sql: str, sqlite_path: str) -> Optional[list]:
    """Execute SQL via sqlite3 directly, bypassing is_safe_sql (Spider gold SQL may have semicolons)."""
    try:
        import sqlite3
        conn = sqlite3.connect(sqlite_path)
        cur = conn.cursor()
        cur.execute(sql.rstrip(";"))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return None


def check_result_match(gold_sql: str, pred_sql: str, sqlite_path: str) -> bool:
    gold_result = execute_sql_result(gold_sql, sqlite_path)
    pred_result = execute_sql_result(pred_sql, sqlite_path)
    if gold_result is None or pred_result is None:
        return False
    # Compare as sets of tuples; normalize string values for case-insensitive matching
    def _norm_row(row):
        return tuple(str(v).strip().lower() if isinstance(v, str) else v for v in row)
    return set(_norm_row(r) for r in gold_result) == set(_norm_row(r) for r in pred_result)


def get_sqlite_uri(spider_db_path: Path, db_id: str) -> str:
    sqlite_file = spider_db_path / db_id / f"{db_id}.sqlite"
    return f"sqlite:///{sqlite_file}"


# ── Single test runner ──────────────────────────────────────────────────────

def run_single_test(
    index: int,
    db_id: str,
    question: str,
    gold_sql: str,
    graph,
    spider_db_path: Path,
) -> TestResult:
    start_time = time.time()
    db_uri = get_sqlite_uri(spider_db_path, db_id)

    try:
        state = create_initial_state(question=question, db_uri=db_uri)
        result = graph.invoke(state, {"recursion_limit": 25})
        predicted_sql = result.get("generated_sql", "").strip()
        err_msg = None
    except Exception as exc:
        predicted_sql = ""
        err_msg = str(exc)

    elapsed = time.time() - start_time
    sql_ok = False
    res_ok = False

    if predicted_sql and not err_msg:
        try:
            sql_ok = check_exact_sql_match(gold_sql, predicted_sql)
            sqlite_file = spider_db_path / db_id / f"{db_id}.sqlite"
            res_ok = check_result_match(gold_sql, predicted_sql, str(sqlite_file))
        except Exception as exc:
            err_msg = f"eval error: {exc}"

    return TestResult(
        index=index,
        db_id=db_id,
        question=question,
        gold_sql=gold_sql,
        predicted_sql=predicted_sql,
        execution_time=round(elapsed, 2),
        error=err_msg,
        exact_sql_match=sql_ok,
        exact_result_match=res_ok,
    )


# ── Full test runner ────────────────────────────────────────────────────────

def run_spider_tests(
    test_json_path: Path,
    spider_db_path: Path,
    max_tests: Optional[int] = None,
    db_list: Optional[List[str]] = None,
    skip_errors: bool = True,
) -> List[TestResult]:
    print(f"Loading test data from {test_json_path}")
    with open(test_json_path, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    # Filter
    if db_list:
        test_data = [t for t in test_data if t["db_id"] in db_list]
    if max_tests:
        test_data = test_data[:max_tests]

    total = len(test_data)
    print(f"Running {total} tests ...\n")

    # Build graph once
    print("Building agent graph ...")
    graph = build_graph()
    print(f"Graph ready.\n")

    results: List[TestResult] = []
    error_count = 0

    t_start_all = time.time()

    for i, case in enumerate(test_data, 1):
        db_id = case["db_id"]
        question = case["question"]
        gold_sql = case.get("query", "")

        print(f"[{i}/{total}] db={db_id}")
        print(f"  Q: {question}")

        tr = run_single_test(
            index=i, db_id=db_id, question=question, gold_sql=gold_sql,
            graph=graph, spider_db_path=spider_db_path,
        )

        # Tag
        if tr.error:
            tag = "ERROR"
            error_count += 1
        elif tr.exact_result_match:
            tag = "PASS (result)"
        elif tr.exact_sql_match:
            tag = "PASS (sql)"
        else:
            tag = "FAIL"

        # Skip error cases from further analysis if requested
        if tr.error and skip_errors:
            print(f"  [{tag}]  {tr.execution_time:.2f}s")
            print(f"  Err: {tr.error[:200]}")
            print()
            results.append(tr)
            continue

        results.append(tr)

        # Progress ETA
        elapsed_all = time.time() - t_start_all
        eta = (elapsed_all / i) * (total - i)
        print(f"  [{tag}]  {tr.execution_time:.2f}s  (ETA {eta:.0f}s)")
        if not tr.exact_result_match and not tr.exact_sql_match:
            print(f"  Gold : {tr.gold_sql[:120]}")
            print(f"  Pred : {tr.predicted_sql[:120]}")
        if tr.error:
            print(f"  Err  : {tr.error[:200]}")
        print()

    return results


# ── Metrics ─────────────────────────────────────────────────────────────────

def calculate_metrics(results: List[TestResult]) -> Dict:
    total = len(results)
    if total == 0:
        return {"total": 0, "correct_sql": 0, "correct_result": 0,
                "accuracy_sql": 0, "accuracy_result": 0, "errors": 0,
                "avg_time": 0, "by_database": {}}

    errors = sum(1 for r in results if r.error)
    valid = [r for r in results if not r.error]
    valid_n = len(valid) if valid else 1
    correct_sql = sum(1 for r in valid if r.exact_sql_match)
    correct_result = sum(1 for r in valid if r.exact_result_match)
    avg_time = sum(r.execution_time for r in results) / total

    metrics: Dict = {
        "total": total,
        "errors": errors,
        "valid": total - errors,
        "correct_sql": correct_sql,
        "correct_result": correct_result,
        "accuracy_sql": correct_sql / valid_n * 100,
        "accuracy_result": correct_result / valid_n * 100,
        "avg_time": round(avg_time, 2),
        "by_database": {},
    }

    # Per-database
    db_map: Dict[str, List[TestResult]] = {}
    for r in results:
        db_map.setdefault(r.db_id, []).append(r)

    for db_id, db_res in sorted(db_map.items()):
        db_valid = [r for r in db_res if not r.error]
        db_valid_n = len(db_valid) if db_valid else 1
        metrics["by_database"][db_id] = {
            "total": len(db_res),
            "errors": sum(1 for r in db_res if r.error),
            "correct_sql": sum(1 for r in db_valid if r.exact_sql_match),
            "correct_result": sum(1 for r in db_valid if r.exact_result_match),
            "accuracy_sql": round(sum(1 for r in db_valid if r.exact_sql_match) / db_valid_n * 100, 1),
            "accuracy_result": round(sum(1 for r in db_valid if r.exact_result_match) / db_valid_n * 100, 1),
        }

    return metrics


# ── Console output ──────────────────────────────────────────────────────────

def print_table(results: List[TestResult]):
    total = len(results)
    sep = "=" * 110
    header = f"{'#':>4} | {'DB':<22} | {'Result':<12} | {'SQL':<5} | {'Time(s)':<8} | {'Question':<40}"
    print(f"\n{sep}")
    print(f"  DETAILED RESULTS TABLE  ({total} cases)")
    print(sep)
    print(header)
    print("-" * 110)
    for r in results:
        tag = "PASS (result)" if r.exact_result_match else ("PASS (sql)" if r.exact_sql_match else ("ERROR" if r.error else "FAIL"))
        sql_m = "Yes" if r.exact_sql_match else "No"
        q = r.question[:38] + "..." if len(r.question) > 38 else r.question
        print(f"{r.index:>4} | {r.db_id:<22} | {tag:<12} | {sql_m:<5} | {r.execution_time:<8.2f} | {q}")
    print(sep)


def print_summary(metrics: Dict):
    total = metrics["total"]
    valid = metrics["valid"]
    print(f"\n{'=' * 55}")
    print(f"  SUMMARY STATISTICS")
    print(f"{'=' * 55}")
    print(f"  Total cases        : {total}")
    print(f"  Valid (no error)   : {valid}")
    print(f"  Errors             : {metrics['errors']}")
    print(f"  SQL Exact Match    : {metrics['correct_sql']}  ({metrics['accuracy_sql']:.1f}%)")
    print(f"  Result Match (EX)  : {metrics['correct_result']}  ({metrics['accuracy_result']:.1f}%)")
    print(f"  Avg response time  : {metrics['avg_time']:.2f}s")
    print()

    if metrics["by_database"]:
        print(f"{'─' * 55}")
        print(f"  PER-DATABASE BREAKDOWN")
        print(f"{'─' * 55}")
        print(f"  {'DB':<24} {'Total':>5} {'Res OK':>7} {'SQL OK':>7} {'Res%':>7} {'SQL%':>7}")
        print(f"  {'─' * 60}")
        for db_id, m in metrics["by_database"].items():
            print(f"  {db_id:<24} {m['total']:>5} {m['correct_result']:>7} {m['correct_sql']:>7} {m['accuracy_result']:>6.1f}% {m['accuracy_sql']:>6.1f}%")
        print()


# ── Charts ──────────────────────────────────────────────────────────────────

def generate_charts(results: List[TestResult], metrics: Dict, save_dir: Path):
    total = len(results)
    if total == 0:
        print("  No results to chart.")
        return None

    errors = sum(1 for r in results if r.error)
    valid = [r for r in results if not r.error]
    sql_ok = sum(1 for r in valid if r.exact_sql_match)
    res_ok = sum(1 for r in valid if r.exact_result_match)
    failures = len(valid) - res_ok
    sql_only = sql_ok - res_ok

    # ── Figure with 4 subplots ─────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(f"Spider Test Results  (n={total}, valid={total - errors})",
                 fontsize=15, fontweight="bold")

    # 1. Pie: result distribution
    ax1 = axes[0, 0]
    labels = ["Result Match", "SQL Match Only", "Failures", "Errors"]
    sizes = [res_ok, sql_only, failures, errors]
    colors = ["#4CAF50", "#8BC34A", "#FF9800", "#F44336"]
    explode = (0.05, 0.02, 0.02, 0.02)
    filtered = [(l, s, c, e) for l, s, c, e in zip(labels, sizes, colors, explode) if s > 0]
    if filtered:
        fl, fs, fc, fe = zip(*filtered)
        wedges, texts, autotexts = ax1.pie(
            fs, labels=fl, colors=fc, explode=fe,
            autopct="%1.1f%%", startangle=90, textprops={"fontsize": 9},
        )
        for t in autotexts:
            t.set_fontsize(8)
    ax1.set_title("Result Distribution", fontsize=12)

    # 2. Bar: accuracy metrics
    ax2 = axes[0, 1]
    bar_labels = ["SQL Exact\nMatch", "Result\nMatch (EX)", "Failure\nRate", "Error\nRate"]
    valid_n = len(valid) if valid else 1
    values = [sql_ok / valid_n * 100, res_ok / valid_n * 100,
              failures / valid_n * 100, errors / total * 100]
    bar_colors = ["#2196F3", "#4CAF50", "#FF9800", "#F44336"]
    bars = ax2.bar(bar_labels, values, color=bar_colors, width=0.6, edgecolor="white")
    for bar, val in zip(bars, values):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax2.set_ylim(0, 115)
    ax2.set_ylabel("Percentage (%)")
    ax2.set_title("Accuracy Metrics", fontsize=12)
    ax2.axhline(y=50, color="gray", linestyle="--", alpha=0.3)

    # 3. Per-database accuracy (horizontal bar)
    ax3 = axes[1, 0]
    db_metrics = metrics.get("by_database", {})
    if db_metrics:
        db_names = sorted(db_metrics.keys())
        res_acc = [db_metrics[d]["accuracy_result"] for d in db_names]
        sql_acc = [db_metrics[d]["accuracy_sql"] for d in db_names]
        y_pos = range(len(db_names))
        ax3.barh(y_pos, res_acc, height=0.4, color="#4CAF50", alpha=0.8, label="Result Match")
        ax3.barh([y + 0.4 for y in y_pos], sql_acc, height=0.4, color="#2196F3", alpha=0.8, label="SQL Match")
        ax3.set_yticks([y + 0.2 for y in y_pos])
        ax3.set_yticklabels(db_names, fontsize=7)
        ax3.set_xlim(0, 110)
        ax3.set_xlabel("Accuracy (%)")
        ax3.set_title("Per-Database Accuracy", fontsize=12)
        ax3.legend(fontsize=8, loc="lower right")
    else:
        ax3.text(0.5, 0.5, "No per-DB data", ha="center", va="center", transform=ax3.transAxes)
        ax3.set_title("Per-Database Accuracy", fontsize=12)

    # 4. Response time histogram
    ax4 = axes[1, 1]
    times = [r.execution_time for r in results]
    status_colors = []
    for r in results:
        if r.exact_result_match:
            status_colors.append("#4CAF50")
        elif r.exact_sql_match:
            status_colors.append("#8BC34A")
        elif r.error:
            status_colors.append("#F44336")
        else:
            status_colors.append("#FF9800")

    # For large datasets, show histogram instead of per-case bars
    if total <= 50:
        indices = list(range(1, total + 1))
        ax4.bar(indices, times, color=status_colors, edgecolor="white", linewidth=0.3)
        ax4.set_xlabel("Test Case #")
    else:
        ax4.hist(times, bins=min(30, total // 5), color="#2196F3", edgecolor="white", alpha=0.8)
        ax4.set_xlabel("Time (seconds)")

    avg_t = sum(times) / total
    ax4.axvline(x=avg_t, color="red", linestyle="--", alpha=0.6, linewidth=1)
    ax4.text(avg_t + avg_t * 0.02, ax4.get_ylim()[1] * 0.9,
             f"Avg: {avg_t:.1f}s", fontsize=8, color="red")
    ax4.set_ylabel("Frequency / Time (s)")
    ax4.set_title("Response Time Distribution", fontsize=12)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    chart_path = save_dir / "spider_test_chart.png"
    fig.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Chart saved to: {chart_path}")
    return chart_path


# ── Save results ────────────────────────────────────────────────────────────

def save_results(results: List[TestResult], metrics: Dict, save_dir: Path, timestamp: str):
    save_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = save_dir / f"spider_results_{timestamp}.json"
    payload = {
        "timestamp": timestamp,
        "summary": metrics,
        "cases": [asdict(r) for r in results],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  JSON saved to: {json_path}")

    # CSV
    csv_path = save_dir / f"spider_results_{timestamp}.csv"
    df = pd.DataFrame([asdict(r) for r in results])
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"  CSV  saved to: {csv_path}")

    # Metrics JSON
    metrics_path = save_dir / f"spider_metrics_{timestamp}.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"  Metrics saved to: {metrics_path}")

    return json_path, csv_path


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Spider dataset test runner")
    parser.add_argument("--test-json", type=str,
                        default="E:/spider_data/spider_data/dev.json")
    parser.add_argument("--spider-path", type=str,
                        default="E:/spider_data/spider_data/database")
    parser.add_argument("--max-tests", type=int, default=None,
                        help="Max number of tests (default: all)")
    parser.add_argument("--db-list", type=str, nargs="+", default=None,
                        help="Only test these databases")
    parser.add_argument("--skip-errors", type=str, default="true",
                        choices=["true", "false"],
                        help="Whether to count errors in results (default: true)")
    parser.add_argument("--output-dir", type=str, default="results",
                        help="Directory to save results (default: results)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    total_wall_start = time.time()

    # Run
    results = run_spider_tests(
        test_json_path=Path(args.test_json),
        spider_db_path=Path(args.spider_path),
        max_tests=args.max_tests,
        db_list=args.db_list,
        skip_errors=args.skip_errors == "true",
    )

    total_wall = time.time() - total_wall_start

    # Metrics
    metrics = calculate_metrics(results)

    # Output
    print_table(results)
    print_summary(metrics)
    print(f"  Total wall time : {total_wall:.0f}s ({total_wall / 60:.1f}min)")
    print()

    # Save
    print("Saving results ...")
    save_results(results, metrics, output_dir, timestamp)
    generate_charts(results, metrics, output_dir)
    print("\nDone.")
