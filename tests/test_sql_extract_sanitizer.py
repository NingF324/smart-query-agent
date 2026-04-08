import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.nodes.sql_generate import (
    align_sql_with_question,
    extract_sql_from_llm_response,
    sanitize_sql_structure,
)


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

    def test_repair_misplaced_distinct(self):
        raw = "SELECT c.CountryName, DISTINCT c.CountryId FROM countries c"
        sql = sanitize_sql_structure(raw)
        self.assertEqual(sql, "SELECT DISTINCT c.CountryName, c.CountryId FROM countries c")

    def test_keep_valid_sql_unchanged(self):
        raw = "SELECT Name, Age FROM singer ORDER BY Age DESC"
        self.assertEqual(sanitize_sql_structure(raw), raw)

    def test_trim_year_count_projection(self):
        sql = """SELECT Year, COUNT(*) AS concert_count
FROM concert
GROUP BY Year
ORDER BY concert_count DESC
LIMIT 1"""
        aligned = align_sql_with_question(sql, "Which year has most number of concerts?")
        self.assertTrue(aligned.startswith("SELECT Year FROM"))
        self.assertNotIn("SELECT Year, COUNT(*)", aligned)

    def test_keep_projection_order_for_each(self):
        sql = "SELECT PetType, MAX(weight) AS max_weight FROM Pets GROUP BY PetType"
        aligned = align_sql_with_question(sql, "Find the maximum weight for each type of pet.")
        self.assertEqual(aligned, sql)

    def test_prune_extra_projection_columns_for_each_count(self):
        sql = (
            "SELECT s.Stadium_ID, s.Name, COUNT(c.concert_ID) AS concert_count "
            "FROM stadium s LEFT JOIN concert c ON s.Stadium_ID = c.Stadium_ID "
            "GROUP BY s.Stadium_ID, s.Name"
        )
        aligned = align_sql_with_question(sql, "For each stadium, how many concerts play there?")
        self.assertTrue(aligned.startswith("SELECT s.Name, COUNT"))
        self.assertNotIn("SELECT s.Stadium_ID,", aligned)

    def test_align_name_id_order_name_first(self):
        sql = "SELECT c.CountryId, c.CountryName FROM countries c"
        aligned = align_sql_with_question(sql, "List country name and id.")
        self.assertEqual(aligned, "SELECT c.CountryName, c.CountryId FROM countries c")

    def test_align_name_id_order_id_first(self):
        sql = "SELECT c.CountryName, c.CountryId FROM countries c"
        aligned = align_sql_with_question(sql, "List country id and name.")
        self.assertEqual(aligned, "SELECT c.CountryId, c.CountryName FROM countries c")

    def test_prefer_inner_join_for_count_per_entity(self):
        sql = (
            "SELECT s.Name, COUNT(c.concert_ID) AS concert_count "
            "FROM stadium s LEFT JOIN concert c ON s.Stadium_ID = c.Stadium_ID "
            "GROUP BY s.Stadium_ID, s.Name"
        )
        aligned = align_sql_with_question(sql, "For each stadium, how many concerts play there?")
        self.assertNotIn("LEFT JOIN", aligned.upper())

    def test_normalize_demonym_literal(self):
        sql = "SELECT AVG(Age) FROM singer WHERE Country = 'French'"
        aligned = align_sql_with_question(sql, "What is the average age of French singers?")
        self.assertIn("'france'", aligned.lower())


if __name__ == "__main__":
    unittest.main()
