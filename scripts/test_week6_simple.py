# Week 6 Test
import os
import sys
from typing import Callable


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("=" * 70)
print("Week 6 Simple Test")
print("=" * 70)

passed = 0
total = 0


def run_test(index: int, name: str, test_func: Callable[[], None]):
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



def test_resolve_time_follow_up():
    from services.conversation_service import resolve_question_with_history

    chat_history = [{"role": "user", "content": "本月订单总数是多少？"}]
    result = resolve_question_with_history("那上个月呢？", chat_history)
    assert result["is_follow_up"] is True, "应识别为追问"
    assert result["resolved_question"] == "上月订单总数是多少？", "应继承主体并替换时间范围"
    print("OK - Time follow-up resolved")



def test_resolve_limit_follow_up():
    from services.conversation_service import resolve_question_with_history

    chat_history = [{"role": "user", "content": "各品类的销售额排行"}]
    result = resolve_question_with_history("只看前5个", chat_history)
    assert "前5个" in result["resolved_question"], "应把 limit 追加到完整问题中"
    print("OK - Limit follow-up resolved")



def test_recent_chat_history_trim():
    from services.conversation_service import get_recent_chat_history

    chat_history = []
    for index in range(14):
        chat_history.append({"role": "user" if index % 2 == 0 else "assistant", "content": f"msg-{index}", "extra": "x"})

    result = get_recent_chat_history(chat_history, max_turns=5)
    assert len(result) == 10, "应只保留最近 5 轮共 10 条消息"
    assert result[0]["content"] == "msg-4", "应裁剪较早消息"
    assert "extra" not in result[0], "应只保留必要字段"
    print("OK - Chat history trimmed correctly")



def test_intent_parse_uses_history():
    from agent.nodes.intent_parse import intent_parse_node
    from agent.state import create_initial_state

    state = create_initial_state("那上个月呢？", chat_history=[{"role": "user", "content": "本月订单总数是多少？"}])
    result = intent_parse_node(state)
    assert result["is_follow_up"] is True, "应识别为追问"
    assert result["resolved_question"] == "上月订单总数是多少？", "应输出改写后的完整问题"
    assert result["intent"]["query_type"] == "count", "应继承原问题的查询类型"
    assert "订单" in result["intent"]["entities"], "应继承原问题主体实体"
    print("OK - Intent parse uses chat history")



def test_sql_generate_follow_up_fallback():
    import agent.nodes.sql_generate as sql_generate_module
    from agent.nodes.intent_parse import intent_parse_node
    from agent.state import create_initial_state

    original_key = sql_generate_module.DEEPSEEK_API_KEY
    sql_generate_module.DEEPSEEK_API_KEY = ""
    try:
        state = create_initial_state("那上个月呢？", chat_history=[{"role": "user", "content": "本月订单总数是多少？"}])
        parsed = intent_parse_node(state)
        state["intent"] = parsed["intent"]
        state["resolved_question"] = parsed["resolved_question"]
        state["is_follow_up"] = parsed["is_follow_up"]
        state["messages"] = parsed["messages"]
        result = sql_generate_module.sql_generate_node(state)
        sql = result.get("generated_sql", "")
        assert "FROM orders" in sql, "应继承订单主体生成 SQL"
        assert "DATE_TRUNC('month'" in sql, "应使用上月时间条件"
    finally:
        sql_generate_module.DEEPSEEK_API_KEY = original_key
    print("OK - SQL fallback handles follow-up context")



def test_build_assistant_message_payload():
    from services.conversation_service import build_assistant_message

    result = {
        "final_answer": "查询完成",
        "generated_sql": "SELECT username FROM users LIMIT 2",
        "query_result": [{"username": "alice"}, {"username": "bob"}],
        "resolved_question": "各城市的用户分布",
    }
    message = build_assistant_message("各城市的用户分布", result)
    assert message["role"] == "assistant", "消息角色应为 assistant"
    assert len(message["table_data"]) == 2, "应保留表格数据用于前端重绘"
    assert message["resolved_question"] == "各城市的用户分布", "应保留完整问题"
    print("OK - Assistant message payload built")


run_test(1, "Resolve Time Follow-up", test_resolve_time_follow_up)
run_test(2, "Resolve Limit Follow-up", test_resolve_limit_follow_up)
run_test(3, "Trim Chat History", test_recent_chat_history_trim)
run_test(4, "Intent Parse With History", test_intent_parse_uses_history)
run_test(5, "SQL Generate Follow-up Fallback", test_sql_generate_follow_up_fallback)
run_test(6, "Assistant Message Payload", test_build_assistant_message_payload)

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"Total: {total}")
print(f"Passed: {passed}")
print(f"Success Rate: {(passed / total * 100) if total else 0:.1f}%")
print("=" * 70)

if passed == total:
    print("\n[SUCCESS] Week 6 components are ready!")
    sys.exit(0)

print(f"\n[FAILED] {total - passed} tests failed")
sys.exit(1)
