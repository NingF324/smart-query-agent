import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.baseline_service import run_single_agent_baseline
from services.db_service import get_db_service
from services.evaluation_service import build_pipeline_runner, evaluate_cases
from tests.eval_cases import get_week7_smoke_cases


class CompareBaselinesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.db_service = get_db_service()
            cls.pipeline_runner = build_pipeline_runner()
        except Exception as exc:
            raise unittest.SkipTest(f"Baseline 对比环境不可用: {exc}")

    def test_pipeline_not_worse_than_single_agent(self):
        cases = get_week7_smoke_cases()
        pipeline_report = evaluate_cases(cases, self.pipeline_runner, db_service=self.db_service, label="pipeline")
        baseline_report = evaluate_cases(cases, run_single_agent_baseline, db_service=self.db_service, label="baseline")

        self.assertGreaterEqual(
            pipeline_report["summary"]["ex_rate"],
            baseline_report["summary"]["ex_rate"],
            "多节点流水线在 EX 指标上不应低于单 Agent 基线",
        )


if __name__ == "__main__":
    unittest.main()
