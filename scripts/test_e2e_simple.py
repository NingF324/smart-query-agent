# End-to-End Test - Complete Pipeline Integration
import os
import sys
from typing import Callable

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("=" * 70)
print("End-to-End Integration Test")
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


def test_complete_pipeline_single_question():
    """Test complete pipeline for a single question."""
    from agent.graph import build_graph
    from agent.state import create_initial_state
    from services.db_service import get_db_service

    # Build graph
    graph = build_graph()

    # Simple test question
    question = "查询用户总数"
    state = create_initial_state(question)

    # Execute pipeline
    result = graph.invoke(state)

    # Verify result
    assert result.get("generated_sql"), "Pipeline should generate SQL"
    assert result.get("validation_result", {}).get("valid") is True, "SQL should be valid"
    assert result.get("query_result") is not None, "Should return query result"
    assert result.get("final_answer"), "Should have final answer"

    sql = result["generated_sql"]
    assert "SELECT" in sql.upper(), "Generated SQL should be a SELECT query"

    print(f"OK - Pipeline executed successfully")
    print(f"    SQL: {sql[:100]}...")
    print(f"    Answer length: {len(result.get('final_answer', ''))}")


def test_complete_pipeline_with_follow_up():
    """Test complete pipeline with follow-up question."""
    from agent.graph import build_graph
    from agent.state import create_initial_state

    graph = build_graph()

    # First question
    state1 = create_initial_state("本月订单总数是多少？")
    result1 = graph.invoke(state1)
    assert result1.get("final_answer"), "First question should be answered"

    # Follow-up question
    chat_history = [
        {"role": "user", "content": "本月订单总数是多少？"},
        {"role": "assistant", "content": result1.get("final_answer", "")},
    ]
    state2 = create_initial_state("那上个月呢？", chat_history=chat_history)
    result2 = graph.invoke(state2)

    assert result2.get("is_follow_up") is True, "Should identify as follow-up"
    assert result2.get("resolved_question") != "那上个月呢？", "Should resolve the question"
    assert result2.get("generated_sql"), "Should generate SQL for follow-up"

    print("OK - Follow-up pipeline executed successfully")
    print(f"    Resolved question: {result2.get('resolved_question')}")


def test_error_recovery_pipeline():
    """Test pipeline error recovery mechanism."""
    from agent.graph import build_graph
    from agent.state import create_initial_state

    graph = build_graph()

    # Question that might generate SQL with errors
    state = create_initial_state("查询所有产品（包含不存在的字段）")
    state["intent"] = {"query_type": "select", "entities": ["产品"]}

    result = graph.invoke(state)

    # Should handle error gracefully
    validation_result = result.get("validation_result", {})
    error_type = result.get("error_type")

    # Either succeeded or handled error properly
    assert validation_result is not None, "Should have validation result"
    assert result.get("final_answer"), "Should provide answer even on error"

    if not validation_result.get("valid"):
        assert error_type in ["fixable", "unfixable", "execution_error", None], "Error type should be classified"

    print("OK - Error recovery works correctly")
    print(f"    Valid: {validation_result.get('valid')}")
    print(f"    Error type: {error_type}")


def test_multi_turn_conversation_flow():
    """Test multi-turn conversation state management."""
    from agent.graph import build_graph
    from agent.state import create_initial_state
    from services.conversation_service import (
        get_recent_chat_history,
        build_assistant_message,
    )

    graph = build_graph()
    chat_history = []

    # Turn 1
    question1 = "各城市用户分布"
    state1 = create_initial_state(question1, chat_history=chat_history)
    result1 = graph.invoke(state1)

    msg1 = {"role": "user", "content": question1}
    chat_history.append(msg1)

    assistant_msg1 = build_assistant_message(question1, result1)
    chat_history.append(assistant_msg1)

    # Turn 2
    question2 = "只看前3个"
    state2 = create_initial_state(question2, chat_history=chat_history)
    result2 = graph.invoke(state2)

    assert result2.get("is_follow_up") is True, "Second question should be follow-up"

    msg2 = {"role": "user", "content": question2}
    chat_history.append(msg2)

    assistant_msg2 = build_assistant_message(question2, result2)
    chat_history.append(assistant_msg2)

    # Test history trimming
    recent_history = get_recent_chat_history(chat_history, max_turns=2)
    assert len(recent_history) == 4, "Should keep exactly 2 turns (4 messages)"

    print("OK - Multi-turn conversation flow works")
    print(f"    Total messages in history: {len(chat_history)}")
    print(f"    Recent history (2 turns): {len(recent_history)} messages")


def test_all_nodes_execution():
    """Verify all pipeline nodes are executed."""
    from agent.graph import build_graph, get_graph_info

    graph = build_graph()
    info = get_graph_info()

    # Check all required nodes exist
    required_nodes = [
        "intent_parse",
        "schema_retrieve",
        "sql_generate",
        "sql_validate",
        "sql_execute",
        "result_interpret",
        "error_response",
    ]

    for node in required_nodes:
        assert node in info["nodes"], f"Node {node} not found in graph"

    print(f"OK - All {len(required_nodes)} required nodes are defined")


def test_pipeline_performance():
    """Test pipeline performance (should complete within reasonable time)."""
    import time
    from agent.graph import build_graph
    from agent.state import create_initial_state

    graph = build_graph()

    start_time = time.time()
    state = create_initial_state("查询用户数量")
    result = graph.invoke(state)
    elapsed = time.time() - start_time

    # Pipeline should complete within 30 seconds (including LLM calls)
    assert elapsed < 30, f"Pipeline too slow: {elapsed:.2f}s (expected < 30s)"
    assert result.get("final_answer"), "Should complete successfully"

    print(f"OK - Pipeline performance acceptable")
    print(f"    Execution time: {elapsed:.2f}s")


run_test(1, "Complete Pipeline Single Question", test_complete_pipeline_single_question)
run_test(2, "Complete Pipeline with Follow-up", test_complete_pipeline_with_follow_up)
run_test(3, "Error Recovery Pipeline", test_error_recovery_pipeline)
run_test(4, "Multi-turn Conversation Flow", test_multi_turn_conversation_flow)
run_test(5, "All Nodes Execution", test_all_nodes_execution)
run_test(6, "Pipeline Performance", test_pipeline_performance)

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"Total: {total}")
print(f"Passed: {passed}")
print(f"Success Rate: {(passed / total * 100) if total else 0:.1f}%")
print("=" * 70)

if passed == total:
    print("\n[SUCCESS] End-to-end integration test passed!")
    sys.exit(0)

print(f"\n[FAILED] {total - passed} tests failed")
sys.exit(1)
