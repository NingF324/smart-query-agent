"""
Spider dataset test runner and evaluation script.
Uses SQLite databases directly (recommended for Spider evaluation).
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
from dataclasses import dataclass
from agent.graph import build_graph
from agent.state import create_initial_state
from services.db_service import DatabaseService
from config import DEEPSEEK_API_KEY
import re


@dataclass
class TestResult:
    """Single test result."""
    db_id: str
    question: str
    gold_sql: str
    predicted_sql: str
    execution_time: float
    error: Optional[str] = None
    exact_result_match: bool = False  # Result-based match
    exact_sql_match: bool = False  # SQL text match


def normalize_sql(sql: str) -> str:
    """Normalize SQL for comparison."""
    # Remove extra whitespace
'    sql = re.sub(r'\s+', ' ', sql.strip())

    # Convert to lowercase (for comparison)
    sql = sql.lower()

    return sql


def check_exact_sql_match(gold_sql: str, pred_sql: str) -> bool:
    """Check exact match between SQLs (text-based)."""
    # Normalize both SQLs
    gold_normalized = normalize_sql(gold_sql)
    pred_normalized = normalize_sql(pred_sql)

    return gold_normalized == pred_normalized


def execute_sql_result(sql: str, db_service: DatabaseService) -> Optional[list]:
    """Execute SQL and return result."""
    try:
        result = db_service.execute_query(sql)
        return result
    except Exception as e:
        print(f"Error executing SQL: {e}")
        return None


def check_result_match(
    gold_sql: str,
    pred_sql: str,
    db_service: DatabaseService
) -> bool:
    """Check if SQL results match (execution-based)."""
    gold_result = execute_sql_result(gold_sql, db_service)
    pred_result = execute_sql_result(pred_sql, db_service)

    if gold_result is None or pred_result is None:
        return False

    # Convert to sets for comparison (order insensitive)
    gold_set = set(tuple(row) for row in gold_result)
    pred_set = set(tuple(row) for row in pred_result)

    return gold_set == pred_set


def get_sqlite_uri(spider_db_path: Path, db_id: str) -> str:
    """Get SQLite URI for a specific Spider database."""
    sqlite_file = spider_db_path / db_id / f"{db_id}.sqlite"
    return f"sqlite:///{sqlite_file}"


def run_single_test(
    db_id: str,
    question: str,
    gold_sql: str,
    graph,
    spider_db_path: Path,
    use_sqlite: bool = True
) -> TestResult:
    """Run a single test case."""
    start_time = time.time()

    try:
        # Get database URI
        if use_sqlite:
            db_uri = get_sqlite_uri(spider_db_path, db_id)
        else:
            # PostgreSQL (if needed)
            db_uri = f"postgresql://postgres:password@localhost:55432/spider?options=-csearch_path%3D{db_id}"

        # Create initial state
        state = create_initial_state(
            question=question,
            db_uri=db_uri
        )

        # Run agent
        result = graph.invoke(state, {"recursion_limit": 20})
        predicted_sql = result.get("sql", "")

        execution_time = time.time() - start_time

        # Check SQL text match
        exact_sql_match = check_exact_sql_match(gold_sql, predicted_sql)

        # Check result match
        db_service = DatabaseService(db_uri)
        exact_result_match = check_result_match(gold_sql, predicted_sql, db_service)

        return TestResult(
            db_id=db_id,
            question=question,
            gold_sql=gold_sql,
            predicted_sql=predicted_sql,
            execution_time=execution_time,
            exact_sql_match=exact_sql_match,
            exact_result_match=exact_result_match
        )

    except Exception as e:
        execution_time = time.time() - start_time
        return TestResult(
            db_id=db_id,
            question=question,
            gold_sql=gold_sql,
            predicted_sql="",
            execution_time=execution_time,
            error=str(e),
            exact_sql_match=False,
            exact_result_match=False
        )


def run_spider_tests(
    test_json_path: Path,
    spider_db_path: Path,
    gold_sql_path: Optional[Path] = None,
    max_tests: int = None,
    db_list: Optional[List[str]] = None,
    skip_errors: bool = True,
    use_sqlite: bool = True
) -> List[TestResult]:
    """Run Spider dataset tests."""
    print(f"Loading test data from {test_json_path}")

    # Load test JSON
    with open(test_json_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    # Load gold SQL if provided
    gold_sqls = {}
    if gold_sql_path and gold_sql_path.exists():
        with open(gold_sql_path, 'r', encoding='utf-8') as f:
            gold_sqls = [line.strip() for line in f.readlines()]

    # Filter tests
    if db_list:
        test_data = [t for t in test_data if t['db_id'] in db_list]
    if max_tests:
        test_data = test_data[:max_tests]

    print(f"Running {len(test_data)} tests...")
    print(f"Using {'SQLite' if use_sqlite else 'PostgreSQL'} databases\n")

    # Build agent graph
    print("Building agent graph...")
    graph = build_graph()

    results = []
    skipped = 0

    for idx, test_case in enumerate(test_data):
        db_id = test_case['db_id']
        question = test_case['question']
        gold_sql = test_case.get('query', '')

        # Use gold SQL from file if available
        if gold_sqls and idx < len(gold_sqls):
            gold_sql = gold_sqls[idx]

        print(f"[{idx+1}/{len(test_data)}] DB: {db_id}")
        print(f"  Question: {question}")

        result = run_single_test(
            db_id=db_id,
            question=question,
            gold_sql=gold_sql,
            graph=graph,
            spider_db_path=spider_db_path,
            use_sqlite=use_sqlite
        )

        if result.error and skip_errors:
            print(f"  ❌ Error: {result.error}")
            skipped += 1
            continue

        results.append(result)

        match_type = "Result" if result.exact_result_match else ("SQL" if result.exact_sql_match else "None")
        status = "✅" if result.exact_result_match or result.exact_sql_match else "❌"
        print(f"  {status} Match Type: {match_type} ({result.execution_time:.2f}s)")

        if not result.exact_result_match and not result.exact_sql_match:
            print(f"  Gold: {gold_sql[:100]}...")
            print(f"  Pred: {result.predicted_sql[:100]}...")

        print()

    if skipped > 0:
        print(f"Skipped {skipped} tests due to errors")

    return results


def calculate_metrics(results: List[TestResult]) -> Dict:
    """Calculate evaluation metrics."""
    total = len(results)
    correct_sql = sum(1 for r in results if r.exact_sql_match)
    correct_result = sum(1 for r in results if r.exact_result_match)
    avg_time = sum(r.execution_time for r in results) / total if total > 0 else 0

    metrics = {
        "total": total,
        "correct_sql": correct_sql,
        "correct_result": correct_result,
        "accuracy_sql": correct_sql / total if total > 0 else 0,
        "accuracy_result": correct_result / total if total > 0 else 0,
        "avg_time": avg_time,
        "by_database": {}
    }

    # Per-database metrics
    db_results = {}
    for r in results:
        if r.db_id not in db_results:
            db_results[r.db_id] = []
        db_results[r.db_id].append(r)

    for db_id, db_res in db_results.items():
        total_db = len(db_res)
        correct_db_sql = sum(1 for r in db_res if r.exact_sql_match)
        correct_db_result = sum(1 for r in db_res if r.exact_result_match)
        metrics["by_database"][db_id] = {
            "total": total_db,
            "correct_sql": correct_db_sql,
            "correct_result": correct_db_result,
            "accuracy_sql": correct_db_sql / total_db if total_db > 0 else 0,
            "accuracy_result": correct_db_result / total_db if total_db > 0 else 0
        }

    return metrics


def print_report(metrics: Dict, use_sqlite: bool = True):
    """Print evaluation report."""
    db_type = "SQLite" if use_sqlite else "PostgreSQL"

    print("=" * 60)
    print(f"SPIDER EVALUATION REPORT ({db_type})")
    print("=" * 60)

    print(f"\nOverall Results:")
    print(f"  Total Tests: {metrics['total']}")
    print(f"  SQL Match: {metrics['correct_sql']} ({metrics['accuracy_sql'] * 100:.2f}%)")
    print(f"  Result Match: {metrics['correct_result']} ({metrics['accuracy_result'] * 100:.2f}%)")
    print(f"  Avg Time: {metrics['avg_time']:.2f}s")

    print(f"\nResults by Database:")
    for db_id, db_metrics in sorted(metrics["by_database"].items()):
        print(f"  {db_id}:")
        print(f"    SQL: {db_metrics['correct_sql']}/{db_metrics['total']} "
              f"({db_metrics['accuracy_sql'] * 100:.1f}%)")
        print(f"    Result: {db_metrics['correct_result']}/{db_metrics['total']} "
              f"({db_metrics['accuracy_result'] * 100:.1f}%)")

    print()


def save_results(results: List[TestResult], metrics: Dict, output_path: Path):
    """Save results to CSV."""
    data = []
    for r in results:
        data.append({
            "db_id": r.db_id,
            "question": r.question,
            "gold_sql": r.gold_sql,
            "predicted_sql": r.predicted_sql,
            "execution_time": r.execution_time,
            "exact_sql_match": r.exact_sql_match,
            "exact_result_match": r.exact_result_match,
            "error": r.error or ""
        })

    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding='utf-8')

    # Save metrics
    metrics_path = output_path.parent / f"{output_path.stem}_metrics.json"
    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(f"Results saved to: {output_path}")
    print(f"Metrics saved to: {metrics_path}")


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Test on Spider dataset")
    parser.add_argument(
        "--test-json",
        type=str,
        default="E:/spider_data/spider_data/dev.json",
        help="Path to Spider test/dev JSON"
    )
    parser.add_argument(
        "--spider-path",
        type=str,
        default="E:/spider_data/spider_data/database",
        help="Path to Spider database directory"
    )
    parser.add_argument(
        "--gold-sql",
        type=str,
        default="E:/spider_data/spider_data/dev_gold.sql",
        help="Path to gold SQL file"
    )
    parser.add_argument(
        "--max-tests",
        type=int,
        help="Maximum number of tests to run"
    )
    parser.add_argument(
        "--db-list",
        type=str,
        nargs="+",
        help="List of specific databases to test"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/spider_test_results.csv",
        help="Output path for results CSV"
    )
    parser.add_argument(
        "--use-postgres",
        action="store_true",
        help="Use PostgreSQL instead of SQLite"
    )

    args = parser.parse_args()

    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Run tests
    results = run_spider_tests(
        test_json_path=Path(args.test_json),
        spider_db_path=Path(args.spider_path),
        gold_sql_path=Path(args.gold_sql) if args.gold_sql else None,
        max_tests=args.max_tests,
        db_list=args.db_list,
        use_sqlite=not args.use_postgres
    )

    # Calculate metrics
    metrics = calculate_metrics(results)

    # Print report
    print_report(metrics, use_sqlite=not args.use_postgres)

    # Save results
    save_results(results, metrics, Path(args.output))
