"""Context middleware to manage message history and reduce context bloat.

This middleware filters and truncates messages to keep only relevant context,
helping to stay within token limits and improve response quality.
"""
from collections import defaultdict
from langchain.agents.middleware import before_model
from langchain_core.messages import AIMessage, ToolMessage

from ..langchain_state import HyperfocusState

@before_model
def filter_old_script_versions(state: HyperfocusState, runtime) -> dict | None:
    """Keep only the most recent create_python_script tool call for each path.

    This middleware:
    1. Tracks all create_python_script tool calls by path
    2. Identifies the most recent call for each unique path
    3. Hides older tool calls and their results for the same path

    This prevents context bloat from multiple iterations of script development.
    """
    messages = state.get("messages", [])

    if not messages:
        return None

    # Track create_python_script calls by path
    # Map: path -> list of (message_index, tool_call_id)
    script_calls_by_path: dict[str, list[tuple[int, str]]] = defaultdict(list)

    # Map tool_call_id to message index for ToolMessages
    tool_call_to_message: dict[str, int] = {}

    # First pass: identify all create_python_script calls and their positions
    for i, message in enumerate(messages):
        if isinstance(message, AIMessage) and hasattr(message, 'tool_calls'):
            for tool_call in message.tool_calls:
                if tool_call.get("name") == "create_python_script":
                    args = tool_call.get("args", {})
                    path = args.get("path")
                    tool_call_id = tool_call.get("id")

                    if path and tool_call_id:
                        script_calls_by_path[path].append((i, tool_call_id))
                        tool_call_to_message[tool_call_id] = i

        elif isinstance(message, ToolMessage):
            # Track where tool results appear
            tool_call_id = message.tool_call_id
            if tool_call_id:
                tool_call_to_message[tool_call_id] = i

    # Determine which tool calls to hide (all except the most recent for each path)
    tool_calls_to_hide: set[str] = set()

    for path, calls in script_calls_by_path.items():
        if len(calls) > 1:
            # Sort by message index to find the most recent
            calls_sorted = sorted(calls, key=lambda x: x[0])

            # Hide all but the last one
            for msg_idx, tool_call_id in calls_sorted[:-1]:
                tool_calls_to_hide.add(tool_call_id)

    # If no calls to hide, return early
    if not tool_calls_to_hide:
        return None

    # Second pass: create modified messages
    modified_messages = []
    hidden_count = 0

    for i, message in enumerate(messages):
        should_hide = False

        # Check if this is an AI message with tool calls to hide
        if isinstance(message, AIMessage) and hasattr(message, 'tool_calls'):
            # Filter out hidden tool calls
            filtered_tool_calls = [
                tc for tc in message.tool_calls
                if tc.get("id") not in tool_calls_to_hide
            ]

            # If we filtered out some tool calls, we need to modify the message
            if len(filtered_tool_calls) < len(message.tool_calls):
                hidden_count += len(message.tool_calls) - len(filtered_tool_calls)

                # If no tool calls remain, keep the message but clear tool calls
                if filtered_tool_calls:
                    # Create new AI message with filtered tool calls
                    modified_message = AIMessage(
                        content=message.content,
                        tool_calls=filtered_tool_calls
                    )
                    if hasattr(message, 'id'):
                        modified_message.id = message.id
                    modified_messages.append(modified_message)
                elif message.content:
                    # Keep the message but without tool calls
                    modified_message = AIMessage(content=message.content)
                    if hasattr(message, 'id'):
                        modified_message.id = message.id
                    modified_messages.append(modified_message)
                # If no content and no remaining tool calls, skip the message
                continue
            else:
                modified_messages.append(message)

        # Check if this is a ToolMessage for a hidden tool call
        elif isinstance(message, ToolMessage):
            if message.tool_call_id in tool_calls_to_hide:
                should_hide = True
                hidden_count += 1

        # Add message if not hidden
        if not should_hide and message not in modified_messages:
            modified_messages.append(message)

    # Return state update if we modified anything
    if hidden_count > 0:
        print(f"-> [Context Filter] Hid {hidden_count} old script version(s)")
        return {"messages": modified_messages}

    return None
