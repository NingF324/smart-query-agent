import argparse
import json
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.baseline_service import run_single_agent_baseline
from services.db_service import get_db_service
from services.evaluation_service import (
    build_pipeline_runner,
    build_sql_validator,
    evaluate_cases,
    evaluate_safety_sql_cases,
    save_report,
)
from tests.eval_cases import get_week7_eval_cases, get_week7_safety_sql_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Week7 自动评测脚本")
    parser.add_argument("--mode", choices=["pipeline", "baseline", "both"], default="both")
    parser.add_argument("--limit", type=int, default=0, help="只评测前 N 条样例")
    parser.add_argument("--output", type=str, default="", help="可选：将结果保存到 JSON 文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_service = get_db_service()
    cases = get_week7_eval_cases()
    if args.limit > 0:
        cases = cases[:args.limit]

    report = {
        "case_count": len(cases),
        "safety_case_count": len(get_week7_safety_sql_cases()),
        "reports": {},
    }

    if args.mode in {"pipeline", "both"}:
        report["reports"]["pipeline"] = evaluate_cases(
            cases=cases,
            runner=build_pipeline_runner(),
            db_service=db_service,
            label="pipeline",
        )

    if args.mode in {"baseline", "both"}:
        report["reports"]["baseline"] = evaluate_cases(
            cases=cases,
            runner=run_single_agent_baseline,
            db_service=db_service,
            label="baseline",
        )

    report["reports"]["safety"] = evaluate_safety_sql_cases(
        cases=get_week7_safety_sql_cases(),
        validator=build_sql_validator(),
        label="safety",
    )

    print(json.dumps({key: value["summary"] for key, value in report["reports"].items()}, ensure_ascii=False, indent=2))

    if args.output:
        save_report(report, args.output)
        print(f"\n评测报告已写入: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
