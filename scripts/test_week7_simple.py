# Week 7 Test
import os
import sys
from typing import Callable


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("=" * 70)
print("Week 7 Simple Test")
print("=" * 70)

passed = 0
total = 0


def run_test(index: int, name: str, test_func: Callable[[], None]):
    global passed, total

    total += 1
    print(f"\n[{index}/7] Testing {name}...")

    try:
        test_func()
        passed += 1
    except AssertionError as error:
        print(f"FAIL - {error}")
    except Exception as error:
        print(f"FAIL - Error: {error}")



def test_case_catalog_size():
    from tests.eval_cases import get_week7_eval_cases, get_week7_safety_sql_cases

    eval_cases = get_week7_eval_cases()
    safety_cases = get_week7_safety_sql_cases()
    assert len(eval_cases) >= 50, "端到端样例应不少于 50 条"
    assert len(safety_cases) >= 8, "安全测试样例应不少于 8 条"
    print("OK - Evaluation case catalog is ready")



def test_normalize_sql():
    from services.evaluation_service import normalize_sql

    sql_a = "SELECT  COUNT(*)   AS count FROM orders  WHERE status = 'completed';"
    sql_b = "select count(*) as count from orders where status='completed'"
    assert normalize_sql(sql_a) == normalize_sql(sql_b), "SQL 标准化应忽略大小写、空格和末尾分号"
    print("OK - SQL normalization works")



def test_compare_result_rows():
    from services.evaluation_service import compare_result_rows

    actual = [{"city": "北京", "user_count": 2.0}, {"city": "上海", "user_count": 1.0}]
    expected = [{"user_count": 1, "city": "上海"}, {"user_count": 2, "city": "北京"}]
    assert compare_result_rows(actual, expected), "结果集比较应忽略顺序并兼容数值类型"
    print("OK - Result comparison works")



def test_evaluate_cases_with_mock_runner():
    from services.evaluation_service import EvaluationCase, evaluate_cases

    class DummyDbService:
        def execute_query(self, sql: str):
            if "COUNT(*) AS count FROM users" in sql:
                return [{"count": 100}]
            raise AssertionError(f"Unexpected SQL: {sql}")

    def runner(question: str, chat_history=None):
        return {
            "generated_sql": "SELECT COUNT(*) AS count FROM users",
            "query_result": [{"count": 100}],
            "validation_result": {"valid": True},
            "execution_stats": {"execution_success": True},
        }

    case = EvaluationCase(
        case_id="mock_01",
        question="一共有多少用户？",
        expected_sql="SELECT COUNT(*) AS count FROM users",
        expected_result_sql="SELECT COUNT(*) AS count FROM users",
    )
    report = evaluate_cases([case], runner, db_service=DummyDbService(), label="mock")
    assert report["summary"]["em_rate"] == 100.0, "Mock EM 应为 100%"
    assert report["summary"]["ex_rate"] == 100.0, "Mock EX 应为 100%"
    print("OK - Evaluation runner works")



def test_summarize_case_results():
    from services.evaluation_service import summarize_case_results

    summary = summarize_case_results([
        {
            "em_measurable": True,
            "exact_match": True,
            "ex_measurable": True,
            "execution_match": True,
            "valid_sql": True,
            "fix_attempted": True,
            "fix_success": True,
            "tags": ["safety"],
            "safety_blocked": True,
            "latency_ms": 10,
        },
        {
            "em_measurable": True,
            "exact_match": False,
            "ex_measurable": True,
            "execution_match": False,
            "valid_sql": False,
            "fix_attempted": True,
            "fix_success": False,
            "tags": [],
            "safety_blocked": False,
            "latency_ms": 20,
        },
    ])
    assert summary["em_rate"] == 50.0, "EM 应按可测样例计算"
    assert summary["ex_rate"] == 50.0, "EX 应按可测样例计算"
    assert summary["fix_success_rate"] == 50.0, "修复成功率应正确统计"
    assert summary["safety_block_rate"] == 100.0, "安全样例拦截率应正确统计"
    print("OK - Summary metrics work")



def test_schema_retrieve_uses_resolved_question():
    import agent.nodes.schema_retrieve as schema_module

    captured = {"query": ""}

    class DummyKB:
        def search_ddl(self, query: str, n_results: int = 5):
            captured["query"] = query
            return [{"metadata": {"table_name": "orders"}}]

    class DummyDbService:
        def get_table_info(self, table_name: str):
            return {
                "columns": [{"name": "order_id", "type": "INTEGER", "nullable": False}],
                "row_count": 1,
                "primary_keys": ["order_id"],
                "foreign_keys": [],
            }

        def get_table_schema(self, table_name: str):
            return "CREATE TABLE orders (order_id INTEGER NOT NULL);"

        def get_table_names(self):
            return ["orders"]

    original_kb = schema_module.KnowledgeBase
    original_db = schema_module.get_db_service
    schema_module.KnowledgeBase = DummyKB
    schema_module.get_db_service = lambda: DummyDbService()

    try:
        state = {
            "question": "那上个月呢？",
            "resolved_question": "上月订单总数是多少？",
            "intent": {"entities": ["订单"]},
            "messages": [],
        }
        result = schema_module.schema_retrieve_node(state)
        assert "上月订单总数是多少？" in captured["query"], "Schema 检索应优先使用改写后的完整问题"
        assert result["relevant_schemas"][0]["table_name"] == "orders", "应返回检索到的 schema"
    finally:
        schema_module.KnowledgeBase = original_kb
        schema_module.get_db_service = original_db
    print("OK - Schema retrieval uses resolved question")



def test_evaluate_safety_sql_cases():
    from services.evaluation_service import SafetySqlCase, evaluate_safety_sql_cases

    def validator(sql: str):
        blocked = ";" in sql or sql.lower().startswith("drop")
        return {
            "validation_result": {
                "valid": not blocked,
                "error": "检测到危险 SQL 模式" if blocked else None,
            },
            "execution_stats": {"safety_blocked": blocked},
        }

    report = evaluate_safety_sql_cases(
        [
            SafetySqlCase(case_id="s1", sql="SELECT * FROM users; DROP TABLE users"),
            SafetySqlCase(case_id="s2", sql="DROP TABLE users"),
        ],
        validator,
        label="mock-safety",
    )
    assert report["summary"]["block_rate"] == 100.0, "安全 SQL 样例应全部被拦截"
    print("OK - Safety SQL evaluation works")


run_test(1, "Evaluation Case Catalog", test_case_catalog_size)
run_test(2, "Normalize SQL", test_normalize_sql)
run_test(3, "Compare Result Rows", test_compare_result_rows)
run_test(4, "Evaluate Cases With Mock Runner", test_evaluate_cases_with_mock_runner)
run_test(5, "Summarize Metrics", test_summarize_case_results)
run_test(6, "Schema Retrieve Uses Resolved Question", test_schema_retrieve_uses_resolved_question)
run_test(7, "Evaluate Safety SQL Cases", test_evaluate_safety_sql_cases)

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"Total: {total}")
print(f"Passed: {passed}")
print(f"Success Rate: {(passed / total * 100) if total else 0:.1f}%")
print("=" * 70)

if passed == total:
    print("\n[SUCCESS] Week 7 components are ready!")
    sys.exit(0)

print(f"\n[FAILED] {total - passed} tests failed")
sys.exit(1)
