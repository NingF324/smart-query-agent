"""
Spider dataset test runner and evaluation script.
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
    exact_match: bool = False


def normalize_sql(sql: str) -> str:
    """Normalize SQL for comparison."""
    # Remove extra whitespace
    sql = re.sub(r'\s+', ' ', sql.strip())

    # Convert to lowercase (for comparison)
    sql = sql.lower()

    return sql


def check_exact_match(gold_sql: str, pred_sql: str) -> bool:
    """Check exact match between SQLs."""
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
    """Check if SQL results match."""
    gold_result = execute_sql_result(gold_sql, db_service)
    pred_result = execute_sql_result(pred_sql, db_service)

    if gold_result is None or pred_result is None:
        return False

    # Convert to sets for comparison (order insensitive)
    gold_set = set(tuple(row) for row in gold_result)
    pred_set = set(tuple(row) for row in pred_result)

    return gold_set == pred_set


def run_single_test(
    db_id: str,
    question: str,
    gold_sql: str,
    graph,
    db_uri: str,
    timeout: float = 30.0
) -> TestResult:
    """Run a single test case."""
    start_time = time.time()

    # Set database URI for this test
    test_db_uri = db_uri.replace("/spider", f"/spider?options=-csearch_path%3D{db_id}")

    try:
        # Create initial state
        state = create_initial_state(
            question=question,
            db_uri=test_db_uri
        )

        # Run agent
        result = graph.invoke(state, {"recursion_limit": 20})
        predicted_sql = result.get("sql", "")

        execution_time = time.time() - start_time

        # Check exact match
        exact_match = check_exact_match(gold_sql, predicted_sql)

        return TestResult(
            db_id=db_id,
            question=question,
            gold_sql=gold_sql,
            predicted_sql=predicted_sql,
            execution_time=execution_time,
            exact_match=exact_match
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
            exact_match=False
        )


def run_spider_tests(
    test_json_path: Path,
    gold_sql_path: Optional[Path] = None,
    max_tests: int = None,
    db_list: Optional[List[str]] = None,
    skip_errors: bool = True
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

    print(f"Running {len(test_data)} tests...\n")

    # Build agent graph
    print("Building agent graph...")
    graph = build_graph()

    # Database URI (will be modified per test)
    db_uri = "postgresql://postgres:password@localhost:55432/spider"

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
            db_uri=db_uri
        )

        if result.error and skip_errors:
            print(f"  ❌ Error: {result.error}")
            skipped += 1
            continue

        results.append(result)

        if result.exact_match:
            print(f"  ✅ Exact match! ({result.execution_time:.2f}s)")
        else:
            print(f"  ❌ No match ({result.execution_time:.2f}s)")
            if result.predicted_sql:
                print(f"  Gold: {gold_sql[:100]}...")
                print(f"  Pred: {result.predicted_sql[:100]}...")

        print()

    if skipped > 0:
        print(f"Skipped {skipped} tests due to errors")

    return results


def calculate_metrics(results: List[TestResult]) -> Dict:
    """Calculate evaluation metrics."""
    total = len(results)
    correct = sum(1 for r in results if r.exact_match)
    avg_time = sum(r.execution_time for r in results) / total if total > 0 else 0

    metrics = {
        "total": total,
        "correct": correct,
        "wrong": total - correct,
        "accuracy": correct / total if total > 0 else 0,
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
        correct_db = sum(1 for r in db_res if r.exact_match)
        metrics["by_database"][db_id] = {
            "total": total_db,
            "correct": correct_db,
            "accuracy": correct_db / total_db if total_db > 0 else 0
        }

    return metrics


def print_report(metrics: Dict):
    """Print evaluation report."""
    print("=" * 60)
    print("SPIDER EVALUATION REPORT")
    print("=" * 60)

    print(f"\nOverall Results:")
    print(f"  Total Tests: {metrics['total']}")
    print(f"  Correct: {metrics['correct']}")
    print(f"  Wrong: {metrics['wrong']}")
    print(f"  Accuracy: {metrics['accuracy'] * 100:.2f}%")
    print(f"  Avg Time: {metrics['avg_time']:.2f}s")

    print(f"\nResults by Database:")
    for db_id, db_metrics in sorted(metrics["by_database"].items()):
        print(f"  {db_id}: {db_metrics['correct']}/{db_metrics['total']} "
              f"({db_metrics['accuracy'] * 100:.1f}%)")

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
            "exact_match": r.exact_match,
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

    args = parser.parse_args()

    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Run tests
    results = run_spider_tests(
        test_json_path=Path(args.test_json),
        gold_sql_path=Path(args.gold_sql) if args.gold_sql else None,
        max_tests=args.max_tests,
        db_list=args.db_list
    )

    # Calculate metrics
    metrics = calculate_metrics(results)

    # Print report
    print_report(metrics)

    # Save results
    save_results(results, metrics, Path(args.output))
