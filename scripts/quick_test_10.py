"""
Quick test: Run the first N Spider test cases with visual report.
Thin wrapper around test_spider.py for quick runs.

Usage:
  python scripts/quick_test_10.py              # default 10 cases
  python scripts/quick_test_10.py --max 50     # 50 cases
  python scripts/quick_test_10.py --db concert_singer  # single DB
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scripts.test_spider import (
    run_spider_tests, calculate_metrics, print_table,
    print_summary, generate_charts, save_results,
)
import time
from datetime import datetime


MAX_TESTS = 10
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=MAX_TESTS, help="Number of test cases")
    parser.add_argument("--db", type=str, default=None, help="Specific database to test")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    t0 = time.time()

    results = run_spider_tests(
        test_json_path=Path("E:/spider_data/spider_data/dev.json"),
        spider_db_path=Path("E:/spider_data/spider_data/database"),
        max_tests=args.max,
        db_list=[args.db] if args.db else None,
    )

    metrics = calculate_metrics(results)
    print_table(results)
    print_summary(metrics)

    wall = time.time() - t0
    print(f"  Total wall time : {wall:.0f}s ({wall / 60:.1f}min)\n")

    print("Saving results ...")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    save_results(results, metrics, RESULTS_DIR, timestamp)
    generate_charts(results, metrics, RESULTS_DIR)
    print("\nDone.")


if __name__ == "__main__":
    main()
