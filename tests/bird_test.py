import json
import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


BIRD_CANDIDATES = [
    os.path.join(PROJECT_ROOT, "data", "bird", "dev.json"),
    os.path.join(PROJECT_ROOT, "data", "bird", "bird_dev.json"),
]


class BirdDatasetHarnessTest(unittest.TestCase):
    def test_bird_dataset_harness(self):
        dataset_path = next((path for path in BIRD_CANDIDATES if os.path.exists(path)), "")
        if not dataset_path:
            self.skipTest("未提供 BIRD 数据集，已保留 Week7 评测入口")

        with open(dataset_path, "r", encoding="utf-8") as file:
            payload = json.load(file)

        self.assertTrue(payload)


if __name__ == "__main__":
    unittest.main()
