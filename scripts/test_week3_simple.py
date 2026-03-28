# Week 3 Test
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("=" * 70)
print("Week 3 Simple Test")
print("=" * 70)

passed = 0
total = 0


def run_test(index: int, name: str, test_func):
    global passed, total

    total += 1
    print(f"\n[{index}/8] Testing {name}...")

    try:
        test_func()
        passed += 1
    except AssertionError as e:
        print(f"FAIL - {e}")
    except Exception as e:
        print(f"FAIL - Error: {e}")


def test_agent_state():
    from agent.state import create_initial_state

    state = create_initial_state("Test question")
    assert isinstance(state, dict), "state 应该是 dict"
    assert len(state) >= 12, "state 字段数量不正确"
    print(f"OK - State type: {type(state)}")
    print(f"OK - State has {len(state)} keys")


def test_field_mappings():
    from agent.state import get_field_mapping

    mapping = get_field_mapping("本月")
    assert mapping, "未找到 '本月' 的字段映射"
    print(f"OK - Found mapping: {mapping}")


def test_intent_parse():
    from agent.nodes.intent_parse import intent_parse_node
    from agent.state import create_initial_state

    state = create_initial_state("本月订单总数是多少")
    result = intent_parse_node(state)
    intent = result.get("intent", {})
    assert intent.get("query_type") == "count", "query_type 应为 count"
    assert "订单" in intent.get("entities", []), "应识别出 '订单' 实体"
    print(f"OK - Query type: {intent.get('query_type')}")
    print(f"OK - Entities: {intent.get('entities', [])}")


def test_sql_generate():
    from agent.nodes.sql_generate import sql_generate_node
    from agent.state import create_initial_state

    state = create_initial_state("各品类的销售额排行")
    state["intent"] = {"query_type": "ranking", "entities": ["品类", "销售额"], "limit": 100}
    result = sql_generate_node(state)
    sql = result.get("generated_sql", "").strip()
    assert sql, "生成的 SQL 不能为空"
    assert sql.lower().startswith("select"), "生成结果不是 SELECT SQL"
    print(f"OK - SQL length: {len(sql)}")
    print(f"OK - SQL preview: {sql[:100]}...")


def test_sql_validate():
    from agent.nodes.sql_validate import sql_validate_node
    from agent.state import create_initial_state

    state = create_initial_state("测试查询")
    state["generated_sql"] = "SELECT * FROM users LIMIT 10"
    result = sql_validate_node(state)
    validation = result.get("validation_result", {})
    assert validation.get("valid") is True, f"SQL 校验失败: {validation.get('error')}"
    print(f"OK - Valid: {validation.get('valid')}")


def test_result_interpret():
    from agent.nodes.result_interpret import result_interpret_node
    from agent.state import create_initial_state

    state = create_initial_state("测试查询")
    state["query_result"] = [{"name": "Test", "value": 100}]
    state["generated_sql"] = "SELECT COUNT(*) FROM users"
    state["validation_result"] = {"valid": True}
    result = result_interpret_node(state)
    answer = result.get("final_answer", "")
    assert answer, "最终回答不能为空"
    print(f"OK - Answer length: {len(answer)}")
    print(f"OK - Answer preview: {answer[:100]}...")


def test_schema_retrieve():
    from agent.nodes.schema_retrieve import schema_retrieve_node
    from agent.state import create_initial_state

    state = create_initial_state("用户表结构")
    result = schema_retrieve_node(state)
    schemas = result.get("relevant_schemas", [])
    assert isinstance(schemas, list), "relevant_schemas 应为列表"
    assert len(schemas) > 0, "未检索到任何 schema"
    print(f"OK - Retrieved {len(schemas)} schemas")


def test_graph_compilation():
    from agent.graph import build_graph

    graph = build_graph()
    assert graph is not None, "图编译结果不能为空"
    print("OK - Graph compiled successfully")


run_test(1, "Agent State", test_agent_state)
run_test(2, "Field Mappings", test_field_mappings)
run_test(3, "Intent Parse", test_intent_parse)
run_test(4, "SQL Generate", test_sql_generate)
run_test(5, "SQL Validate", test_sql_validate)
run_test(6, "Result Interpret", test_result_interpret)
run_test(7, "Schema Retrieve", test_schema_retrieve)
run_test(8, "Graph Compilation", test_graph_compilation)

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"Total: {total}")
print(f"Passed: {passed}")
print(f"Success Rate: {(passed / total * 100) if total else 0:.1f}%")
print("=" * 70)

if passed == total:
    print("\n[SUCCESS] Week 3 components are ready!")
    sys.exit(0)

print(f"\n[FAILED] {total - passed} tests failed")
sys.exit(1)

