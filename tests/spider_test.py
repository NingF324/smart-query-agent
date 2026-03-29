import json
import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


SPIDER_CANDIDATES = [
    os.path.join(PROJECT_ROOT, "data", "spider", "dev.json"),
    os.path.join(PROJECT_ROOT, "data", "spider", "spider_dev.json"),
]


class SpiderDatasetHarnessTest(unittest.TestCase):
    def test_spider_dataset_harness(self):
        dataset_path = next((path for path in SPIDER_CANDIDATES if os.path.exists(path)), "")
        if not dataset_path:
            self.skipTest("未提供 Spider 数据集，已保留 Week7 评测入口")

        with open(dataset_path, "r", encoding="utf-8") as file:
            payload = json.load(file)

        self.assertTrue(payload)


if __name__ == "__main__":
    unittest.main()
