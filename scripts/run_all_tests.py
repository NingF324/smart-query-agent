#!/usr/bin/env python3
# Run All Tests - Comprehensive Test Suite Runner
import os
import sys
import subprocess
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")

# Test suite definitions
TEST_SUITES: list[dict[str, Any]] = [
    {
        "week": 1,
        "name": "Infrastructure & Basic Framework",
        "script": "test_week1_simple.py",
        "required": True,
    },
    {
        "week": 2,
        "name": "Basic Services",
        "script": "test_week2_final.py",
        "required": True,
    },
    {
        "week": 3,
        "name": "Core Agent (Part 1)",
        "script": "test_week3_simple.py",
        "required": True,
    },
    {
        "week": 4,
        "name": "Core Agent (Part 2)",
        "script": "test_week4_simple.py",
        "required": True,
    },
    {
        "week": 5,
        "name": "Error Handling & Security",
        "script": "test_week5_simple.py",
        "required": True,
    },
    {
        "week": 6,
        "name": "Frontend & Multi-turn",
        "script": "test_week6_simple.py",
        "required": True,
    },
    {
        "week": 7,
        "name": "Testing & Evaluation",
        "script": "test_week7_simple.py",
        "required": True,
    },
    {
        "week": "E2E",
        "name": "End-to-End Integration",
        "script": "test_e2e_simple.py",
        "required": True,
    },
]


def print_header():
    print("\n" + "=" * 80)
    print("COMPREHENSIVE TEST SUITE - Intelligent Query Agent")
    print("=" * 80)
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Scripts Directory: {SCRIPTS_DIR}")
    print("=" * 80)


def run_test_suite(suite: dict[str, Any]) -> dict[str, Any]:
    """Run a single test suite and return results."""
    script_path = os.path.join(SCRIPTS_DIR, suite["script"])

    if not os.path.exists(script_path):
        return {
            "week": suite["week"],
            "name": suite["name"],
            "status": "SKIP",
            "reason": "Script not found",
        }

    print(f"\n{'─' * 80}")
    print(f"Running Week {suite['week']}: {suite['name']}")
    print(f"{'─' * 80}")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=SCRIPTS_DIR,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes timeout per suite
        )

        if result.returncode == 0:
            status = "PASS"
            reason = None
        else:
            status = "FAIL"
            reason = "Non-zero exit code"

        return {
            "week": suite["week"],
            "name": suite["name"],
            "status": status,
            "reason": reason,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "week": suite["week"],
            "name": suite["name"],
            "status": "TIMEOUT",
            "reason": "Test suite exceeded 120s timeout",
        }
    except Exception as e:
        return {
            "week": suite["week"],
            "name": suite["name"],
            "status": "ERROR",
            "reason": str(e),
        }


def print_summary(results: list[dict[str, Any]]) -> int:
    """Print test summary."""
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] in ["FAIL", "ERROR", "TIMEOUT"])
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    print(f"\nTotal Suites: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"Success Rate: {(passed / total * 100) if total else 0:.1f}%")

    # Detailed results
    print("\n" + "─" * 80)
    print("DETAILED RESULTS")
    print("─" * 80)

    for result in results:
        status_icon = {
            "PASS": "[PASS]",
            "FAIL": "[FAIL]",
            "ERROR": "[ERROR]",
            "TIMEOUT": "[TIMEOUT]",
            "SKIP": "[SKIP]",
        }.get(result["status"], "[UNKNOWN]")

        print(f"\n{status_icon} Week {result['week']}: {result['name']}")
        print(f"   Status: {result['status']}")

        if result.get("reason"):
            print(f"   Reason: {result['reason']}")

        if result["status"] in ["FAIL", "ERROR"] and result.get("stderr"):
            # Show first few lines of error
            error_lines = result["stderr"].strip().split("\n")[:5]
            print(f"   Error output:")
            for line in error_lines:
                print(f"     {line}")

    # Overall status
    print("\n" + "=" * 80)
    if failed == 0 and skipped == 0:
        print("ALL TESTS PASSED")
        print("=" * 80)
        return 0
    elif failed == 0:
        print("SOME TESTS SKIPPED")
        print("=" * 80)
        return 0
    else:
        print("SOME TESTS FAILED")
        print("=" * 80)
        return 1


def main():
    print_header()

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Run all test suites")
    parser.add_argument(
        "--week",
        type=int,
        choices=list(range(1, 8)) + [99],
        help="Run only specific week (1-7, 99 for E2E)",
    )
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")

    args = parser.parse_args()

    # Filter test suites if week specified
    suites_to_run = TEST_SUITES
    if args.week:
        if args.week == 99:
            suites_to_run = [s for s in TEST_SUITES if s["week"] == "E2E"]
        else:
            suites_to_run = [s for s in TEST_SUITES if s["week"] == args.week]

    # Run all test suites
    results = []
    for suite in suites_to_run:
        result = run_test_suite(suite)
        results.append(result)

        # Print output
        if result.get("stdout"):
            print(result["stdout"])
        if result.get("stderr") and result["status"] != "PASS":
            print(result["stderr"], file=sys.stderr)

        # Fail fast
        if args.fail_fast and result["status"] in ["FAIL", "ERROR", "TIMEOUT"]:
            print("\nStopping due to --fail-fast flag")
            break

    # Print summary and exit
    exit_code = print_summary(results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
