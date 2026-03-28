# Week 5 Test
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("=" * 70)
print("Week 5 Simple Test")
print("=" * 70)

passed = 0
total = 0


def run_test(index: int, name: str, test_func):
    global passed, total

    total += 1
    print(f"\n[{index}/7] Testing {name}...")

    try:
        test_func()
        passed += 1
    except AssertionError as e:
        print(f"FAIL - {e}")
    except Exception as e:
        print(f"FAIL - Error: {e}")


def test_sql_safety_rejects_semicolon():
    from services.db_service import get_db_service

    db = get_db_service()
    is_safe, error = db.is_safe_sql("SELECT username FROM users;")
    assert is_safe is False, "带分号的 SQL 应被拦截"
    assert "分号" in (error or ""), "错误信息应提示分号风险"
    print("OK - Semicolon SQL rejected")


def test_sql_safety_rejects_injection():
    from services.db_service import get_db_service

    db = get_db_service()
    is_safe, error = db.is_safe_sql("SELECT * FROM users -- drop table users")
    assert is_safe is False, "注释注入 SQL 应被拦截"
    assert error, "应返回错误信息"
    print("OK - Injection pattern rejected")


def test_sql_validate_unfixable_relation_error():
    from agent.nodes.sql_validate import classify_error

    error_type = classify_error('relation "userz" does not exist')
    assert error_type == "unfixable", "表不存在应归类为 unfixable"
    print("OK - Relation missing classified as unfixable")


def test_validate_route_respects_retry_limit():
    from agent.graph import should_retry_sql
    from agent.state import create_initial_state

    state = create_initial_state("test")
    state["validation_result"] = {"valid": False, "error": "column does not exist"}
    state["error_type"] = "fixable"
    state["retry_count"] = 3
    state["max_retries"] = 3
    assert should_retry_sql(state) == "error_response", "超过最大重试次数后应进入 error_response"
    print("OK - Validation route stops at retry limit")


def test_execute_route_retries_execution_error():
    from agent.graph import should_retry_execution
    from agent.state import create_initial_state

    state = create_initial_state("test")
    state["validation_result"] = {"valid": False, "error": "timeout"}
    state["error_type"] = "execution_error"
    state["retry_count"] = 0
    state["max_retries"] = 3
    assert should_retry_execution(state) == "sql_generate", "执行错误且未超限时应回到 sql_generate"
    assert state["retry_count"] == 1, "执行错误重试时应递增 retry_count"
    print("OK - Execution route retries correctly")


def test_error_response_node():
    from agent.nodes.error_response import error_response_node
    from agent.state import create_initial_state

    state = create_initial_state("查询异常数据")
    state["generated_sql"] = "SELECT * FROM users"
    state["validation_result"] = {"valid": False, "error": "permission denied"}
    state["error_type"] = "unfixable"
    result = error_response_node(state)
    answer = result.get("final_answer", "")
    assert "不可修复" in answer, "错误响应应说明不可修复"
    assert "permission denied" in answer, "错误响应应包含原始错误"
    print("OK - Error response generated")


def test_result_interpret_fallback():
    import agent.nodes.result_interpret as result_module
    from agent.state import create_initial_state

    original_key = result_module.DEEPSEEK_API_KEY
    result_module.DEEPSEEK_API_KEY = ""
    try:
        state = create_initial_state("查询用户")
        state["generated_sql"] = "SELECT username, city FROM users LIMIT 2"
        state["query_result"] = [
            {"username": "alice", "city": "Beijing"},
            {"username": "bob", "city": "Shanghai"},
        ]
        state["validation_result"] = {"valid": True}
        result = result_module.result_interpret_node(state)
        answer = result.get("final_answer", "")
        assert "查询成功" in answer, "降级解释应返回成功摘要"
        assert "alice" in answer, "降级解释应包含结果内容"
    finally:
        result_module.DEEPSEEK_API_KEY = original_key
    print("OK - Result interpretation fallback works")


run_test(1, "SQL Safety Semicolon", test_sql_safety_rejects_semicolon)
run_test(2, "SQL Safety Injection", test_sql_safety_rejects_injection)
run_test(3, "Classify Unfixable Error", test_sql_validate_unfixable_relation_error)
run_test(4, "Validation Retry Limit", test_validate_route_respects_retry_limit)
run_test(5, "Execution Retry Route", test_execute_route_retries_execution_error)
run_test(6, "Error Response Node", test_error_response_node)
run_test(7, "Result Interpret Fallback", test_result_interpret_fallback)

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"Total: {total}")
print(f"Passed: {passed}")
print(f"Success Rate: {(passed / total * 100) if total else 0:.1f}%")
print("=" * 70)

if passed == total:
    print("\n[SUCCESS] Week 5 components are ready!")
    sys.exit(0)

print(f"\n[FAILED] {total - passed} tests failed")
sys.exit(1)
