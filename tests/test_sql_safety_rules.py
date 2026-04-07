import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.db_service import DatabaseService


class SqlSafetyRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseService("sqlite:///:memory:")

    def test_allows_single_trailing_semicolon(self):
        ok, err = self.db.is_safe_sql("SELECT 1;")
        self.assertTrue(ok, msg=err)

    def test_blocks_multi_statement_sql(self):
        ok, err = self.db.is_safe_sql("SELECT 1; DROP TABLE users")
        self.assertFalse(ok)
        self.assertIn("multi-statement", (err or "").lower())

    def test_blocks_dml_statement(self):
        ok, err = self.db.is_safe_sql("UPDATE users SET username='x'")
        self.assertFalse(ok)
        self.assertTrue(err)

    def test_blocks_sql_comment_payload(self):
        ok, err = self.db.is_safe_sql("SELECT * FROM users -- comment")
        self.assertFalse(ok)
        self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()

