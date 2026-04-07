import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.db_service import get_db_service
from services.evaluation_service import build_pipeline_runner, build_sql_validator, evaluate_cases, evaluate_safety_sql_cases
from tests.eval_cases import get_week7_eval_cases, get_week7_safety_sql_cases, get_week7_smoke_cases


class Week7DatasetTest(unittest.TestCase):
    def test_eval_case_catalog_size(self):
        cases = get_week7_eval_cases()
        self.assertGreaterEqual(len(cases), 50)
        self.assertTrue(any(case.chat_history for case in cases))

    def test_safety_case_catalog_size(self):
        cases = get_week7_safety_sql_cases()
        self.assertGreaterEqual(len(cases), 8)


class Week7EndToEndSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.db_service = get_db_service()
            cls.pipeline_runner = build_pipeline_runner()
            cls.sql_validator = build_sql_validator()
        except Exception as exc:
            raise unittest.SkipTest(f"Week7 端到端环境不可用: {exc}")

    def test_pipeline_smoke_subset(self):
        cases = get_week7_smoke_cases()
        report = evaluate_cases(cases, self.pipeline_runner, db_service=self.db_service, label="pipeline-smoke")

        self.assertEqual(report["summary"]["total_cases"], len(cases))
        self.assertGreater(report["summary"]["measured_ex_cases"], 0)
        self.assertGreaterEqual(report["summary"]["valid_sql_rate"], 0)
        self.assertIn("failure_breakdown", report["summary"])

    def test_safety_sql_suite(self):
        safety_report = evaluate_safety_sql_cases(
            get_week7_safety_sql_cases(),
            type(self).sql_validator,
            label="safety-smoke",
        )
        self.assertEqual(safety_report["summary"]["blocked_cases"], safety_report["summary"]["total_cases"])



if __name__ == "__main__":
    unittest.main()
