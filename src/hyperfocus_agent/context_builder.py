"""Context building system for managing LLM conversation context.

This module handles the conversion of the full internal message history into
the context sent to the LLM, allowing tool results to control whether they
stay in context or are replaced with stubs.
"""
from typing import cast
from openai.types.chat import ChatCompletionMessageParam


def build_context(
    messages: list[ChatCompletionMessageParam],
    tool_result_metadata: dict[str, dict],
    current_iteration: int = 0
) -> list[ChatCompletionMessageParam]:
    """
    Build the LLM context from the full message history.

    This function processes the internal message list and creates a context
    list for the LLM. Tool results that should not be included are replaced
    with stubs, while all other messages pass through unchanged.

    Tool results are only stubbed if they were created in a PREVIOUS iteration.
    Results from the current iteration are always shown in full, even if
    include_in_context=False (they'll be stubbed in the next iteration).

    Args:
        messages: Full internal message history
        tool_result_metadata: Dict mapping tool_call_id to metadata about each result.
                            Expected keys:
                            - include_in_context: Whether to include full result in future iterations
                            - function_name: Name of the function
                            - stub_message: Optional custom stub message
                            - created_at_iteration: Iteration when this result was created
                            - context_guidance: Optional guidance on retrieval
        current_iteration: The current iteration number (results from this iteration shown in full)

    Returns:
        List of messages ready to send to the LLM
    """
    context: list[ChatCompletionMessageParam] = []

    for msg in messages:
        # For tool messages, check if they should be stubbed
        if msg.get("role") == "tool":
            tool_call_id = msg.get("tool_call_id") or ""

            # Get metadata for this tool call
            metadata = tool_result_metadata.get(tool_call_id)
            if not metadata:
                # No metadata, include full message
                context.append(msg)
                continue

            include_in_context = metadata.get("include_in_context", True)
            created_at_iteration = metadata.get("created_at_iteration", -1)

            print(f"build_context: tool_call_id={tool_call_id}, include_in_context={include_in_context}, created_at_iteration={created_at_iteration}, current_iteration={current_iteration}")

            # Only stub if:
            # 1. include_in_context is False, AND
            # 2. This result was created in a PREVIOUS iteration (not current)
            should_stub = (not include_in_context) and (created_at_iteration < current_iteration - 1)

            if should_stub:
                # Replace with a stub message
                function_name = metadata.get("function_name", "unknown")
                stub_message = metadata.get(
                    "stub_message",
                    f"[Result from {function_name} excluded from context - processed in previous iteration]"
                )

                # Add context_guidance if provided
                context_guidance = metadata.get("context_guidance")
                if context_guidance:
                    stub_message = f"{stub_message}\n\n{context_guidance}"

                stub_msg = cast(
                    ChatCompletionMessageParam,
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": stub_message
                    }
                )
                context.append(stub_msg)
            else:
                # Include the full message
                # (either include_in_context=True, or it's from current iteration)
                context.append(msg)
        else:
            # Non-tool messages pass through unchanged
            context.append(msg)

    return context