# Week 4 Test
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("=" * 70)
print("Week 4 Simple Test")
print("=" * 70)

passed = 0
total = 0


def run_test(index: int, name: str, test_func):
    global passed, total

    total += 1
    print(f"\n[{index}/6] Testing {name}...")

    try:
        test_func()
        passed += 1
    except AssertionError as e:
        print(f"FAIL - {e}")
    except Exception as e:
        print(f"FAIL - Error: {e}")


def build_users_schema():
    from services.db_service import get_db_service

    db = get_db_service()
    table_info = db.get_table_info("users")
    ddl = db.get_table_schema("users")
    return {
        "table_name": "users",
        "ddl": ddl,
        "columns": table_info["columns"],
        "row_count": table_info["row_count"],
        "primary_keys": table_info["primary_keys"],
        "foreign_keys": table_info["foreign_keys"],
    }


def test_sql_generate():
    from agent.nodes.sql_generate import sql_generate_node
    from agent.state import create_initial_state

    state = create_initial_state("各品类的销售额排行")
    state["intent"] = {"query_type": "ranking", "entities": ["品类", "销售额"], "limit": 10}
    result = sql_generate_node(state)
    sql = result.get("generated_sql", "").strip()
    assert sql, "生成 SQL 不能为空"
    assert sql.lower().startswith("select"), "生成结果必须是 SELECT"
    assert "limit" in sql.lower(), "结果集查询应包含 LIMIT"
    print(f"OK - SQL preview: {sql[:100]}...")


def test_sql_validate_valid_query():
    from agent.nodes.sql_validate import sql_validate_node
    from agent.state import create_initial_state

    state = create_initial_state("查询用户")
    state["generated_sql"] = "SELECT username, city FROM users LIMIT 5"
    state["relevant_schemas"] = [build_users_schema()]
    result = sql_validate_node(state)
    validation = result.get("validation_result", {})
    assert validation.get("valid") is True, f"有效 SQL 校验失败: {validation.get('error')}"
    assert validation.get("validation_type") == "explain", "有效 SQL 应走 EXPLAIN 校验"
    print("OK - Valid SQL passed EXPLAIN validation")


def test_sql_validate_fixable_query():
    from agent.nodes.sql_validate import sql_validate_node
    from agent.state import create_initial_state

    state = create_initial_state("查询用户名")
    state["generated_sql"] = "SELECT usernme FROM users LIMIT 5"
    state["relevant_schemas"] = [build_users_schema()]
    result = sql_validate_node(state)
    validation = result.get("validation_result", {})
    fixed_sql = result.get("generated_sql", "")
    assert validation.get("valid") is True, f"可修复 SQL 未修复成功: {validation.get('error')}"
    assert "username" in fixed_sql.lower(), "修复后的 SQL 应包含正确字段名 username"
    print(f"OK - Fixed SQL: {fixed_sql}")


def test_route_function():
    from agent.graph import should_retry_sql
    from agent.state import create_initial_state

    valid_state = create_initial_state("test")
    valid_state["validation_result"] = {"valid": True}
    assert should_retry_sql(valid_state) == "sql_execute", "valid 时应进入 sql_execute"

    retry_state = create_initial_state("test")
    retry_state["validation_result"] = {"valid": False}
    retry_state["error_type"] = "fixable"
    retry_state["retry_count"] = 0
    retry_state["max_retries"] = 3
    assert should_retry_sql(retry_state) == "sql_generate", "fixable 且可重试时应回到 sql_generate"

    stop_state = create_initial_state("test")
    stop_state["validation_result"] = {"valid": False}
    stop_state["error_type"] = "unfixable"
    assert should_retry_sql(stop_state) == "result_interpret", "unfixable 时应结束到结果解释"
    print("OK - Route function works as expected")


def test_sql_execute_success():
    from agent.nodes.sql_execute import sql_execute_node
    from agent.state import create_initial_state

    state = create_initial_state("查询用户")
    state["generated_sql"] = "SELECT username, city FROM users LIMIT 3"
    result = sql_execute_node(state)
    rows = result.get("query_result", [])
    assert result.get("validation_result", {}).get("valid") is True, "SQL 执行应成功"
    assert len(rows) > 0, "应返回至少 1 行数据"
    print(f"OK - Returned {len(rows)} rows")


def test_graph_compilation():
    from agent.graph import build_graph

    graph = build_graph()
    assert graph is not None, "图编译结果不能为空"
    print("OK - Graph compiled successfully")


run_test(1, "SQL Generate", test_sql_generate)
run_test(2, "SQL Validate Valid Query", test_sql_validate_valid_query)
run_test(3, "SQL Validate Fixable Query", test_sql_validate_fixable_query)
run_test(4, "Route Function", test_route_function)
run_test(5, "SQL Execute", test_sql_execute_success)
run_test(6, "Graph Compilation", test_graph_compilation)

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"Total: {total}")
print(f"Passed: {passed}")
print(f"Success Rate: {(passed / total * 100) if total else 0:.1f}%")
print("=" * 70)

if passed == total:
    print("\n[SUCCESS] Week 4 components are ready!")
    sys.exit(0)

print(f"\n[FAILED] {total - passed} tests failed")
sys.exit(1)
