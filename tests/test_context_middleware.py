"""Test the context middleware filtering logic."""
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage

# Import the module to get the unwrapped function
import src.hyperfocus_agent.middleware.context_middleware as middleware_module
from src.hyperfocus_agent.langchain_state import HyperfocusState


def test_filter_old_script_versions():
    """Test that old script versions are filtered out."""

    # Create a mock state with multiple create_python_script calls for the same path
    messages = [
        HumanMessage(content="Create a script"),

        # First version
        AIMessage(
            content="Creating script version 1",
            tool_calls=[{
                "name": "create_python_script",
                "args": {"path": "/tmp/test.py", "content": "print('v1')"},
                "id": "call_1"
            }]
        ),
        ToolMessage(
            content="Python script '/tmp/test.py' created with 12 characters.",
            tool_call_id="call_1"
        ),

        HumanMessage(content="Update the script"),

        # Second version (same path)
        AIMessage(
            content="Creating script version 2",
            tool_calls=[{
                "name": "create_python_script",
                "args": {"path": "/tmp/test.py", "content": "print('v2')"},
                "id": "call_2"
            }]
        ),
        ToolMessage(
            content="Python script '/tmp/test.py' created with 12 characters.",
            tool_call_id="call_2"
        ),

        HumanMessage(content="Update it again"),

        # Third version (same path)
        AIMessage(
            content="Creating script version 3",
            tool_calls=[{
                "name": "create_python_script",
                "args": {"path": "/tmp/test.py", "content": "print('v3')"},
                "id": "call_3"
            }]
        ),
        ToolMessage(
            content="Python script '/tmp/test.py' created with 12 characters.",
            tool_call_id="call_3"
        ),

        # Different path (should be kept)
        HumanMessage(content="Create another script"),
        AIMessage(
            content="Creating different script",
            tool_calls=[{
                "name": "create_python_script",
                "args": {"path": "/tmp/other.py", "content": "print('other')"},
                "id": "call_4"
            }]
        ),
        ToolMessage(
            content="Python script '/tmp/other.py' created with 14 characters.",
            tool_call_id="call_4"
        ),
    ]

    state: HyperfocusState = {"messages": messages}

    # Apply the middleware - call the before_model method
    middleware = middleware_module.filter_old_script_versions
    result = middleware.before_model(state, runtime=None)

    # Check that we got a state update
    assert result is not None, "Should return state update"
    assert "messages" in result, "Should update messages"

    filtered_messages = result["messages"]

    # Count how many create_python_script calls remain for /tmp/test.py
    test_py_calls = []
    for msg in filtered_messages:
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls'):
            for tc in msg.tool_calls:
                if tc.get("name") == "create_python_script":
                    if tc.get("args", {}).get("path") == "/tmp/test.py":
                        test_py_calls.append(tc.get("id"))

    print(f"Original messages: {len(messages)}")
    print(f"Filtered messages: {len(filtered_messages)}")
    print(f"create_python_script calls for /tmp/test.py: {test_py_calls}")

    # Should only have the most recent call (call_3)
    assert len(test_py_calls) == 1, f"Should have 1 call for /tmp/test.py, got {len(test_py_calls)}"
    assert test_py_calls[0] == "call_3", "Should keep the most recent call"

    # Verify that call_4 (different path) is still present
    other_py_calls = []
    for msg in filtered_messages:
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls'):
            for tc in msg.tool_calls:
                if tc.get("name") == "create_python_script":
                    if tc.get("args", {}).get("path") == "/tmp/other.py":
                        other_py_calls.append(tc.get("id"))

    assert len(other_py_calls) == 1, "Should keep call for different path"
    assert other_py_calls[0] == "call_4", "Should keep call_4"

    # Verify that tool results for hidden calls are removed
    tool_call_ids_in_results = []
    for msg in filtered_messages:
        if isinstance(msg, ToolMessage):
            tool_call_ids_in_results.append(msg.tool_call_id)

    print(f"Tool call IDs in results: {tool_call_ids_in_results}")

    assert "call_1" not in tool_call_ids_in_results, "Should remove result for call_1"
    assert "call_2" not in tool_call_ids_in_results, "Should remove result for call_2"
    assert "call_3" in tool_call_ids_in_results, "Should keep result for call_3"
    assert "call_4" in tool_call_ids_in_results, "Should keep result for call_4"
