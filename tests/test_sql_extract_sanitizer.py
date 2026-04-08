import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.nodes.sql_generate import extract_sql_from_llm_response, sanitize_sql_structure


class SqlExtractSanitizerTest(unittest.TestCase):
    def test_extract_from_sql_fence(self):
        raw = """Here is SQL:
```sql
SELECT COUNT(*) FROM singer;
```"""
        sql = extract_sql_from_llm_response(raw)
        self.assertEqual(sql, "SELECT COUNT(*) FROM singer")

    def test_repair_missing_with_cte(self):
        raw = """
SELECT AVG(Age) AS average_age FROM singer
)
SELECT DISTINCT s.Song_Name
FROM singer s
CROSS JOIN avg_age a
WHERE s.Age > a.average_age
"""
        sql = sanitize_sql_structure(raw)
        self.assertTrue(sql.startswith("WITH avg_age AS ("))
        self.assertIn("CROSS JOIN avg_age a", sql)

    def test_strip_trailing_explanation(self):
        raw = """SELECT Name FROM singer
Explanation: this gets all names"""
        sql = sanitize_sql_structure(raw)
        self.assertEqual(sql, "SELECT Name FROM singer")

    def test_keep_valid_sql_unchanged(self):
        raw = "SELECT Name, Age FROM singer ORDER BY Age DESC"
        self.assertEqual(sanitize_sql_structure(raw), raw)


if __name__ == "__main__":
    unittest.main()
