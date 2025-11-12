"""Custom state schema for LangChain agent migration.

This module defines the extended state schema that preserves all functionality
from the original implementation while leveraging LangChain's state management.
"""
from typing import Annotated, Any, TypedDict
from langgraph.graph import add_messages


class HyperfocusState(TypedDict):
    """Extended agent state for Hyperfocus agent.

    This state schema extends the base AgentState with custom fields needed
    to preserve the original behavior:
    - Iteration tracking for context stubbing
    - Tool result metadata for conditional context inclusion
    - Multimodal routing flags
    - Stored data for task execution
    """

    # Built-in messages list (required by AgentState)
    # The add_messages reducer automatically handles message appending/updating
    messages: Annotated[list, add_messages]

    # Custom state fields for original functionality

    # Track which iteration we're on (for context stubbing logic)
    current_iteration: int = 0

    # Metadata about tool results to control context inclusion
    # Maps tool_call_id -> {include_in_context, function_name, stub_message, created_at_iteration, context_guidance}
    tool_result_metadata: dict[str, dict] = {}

    # LLM routing context
    # Flag to force multimodal model usage (e.g., when images are loaded)
    use_multimodal: bool = False

    # Task execution context
    # Store large data for task-based processing
    # Note: Could also use LangGraph Store for this, but keeping in state initially for simplicity
    stored_data: dict[str, Any] = {}


class HyperfocusContext:
    """Runtime context for Hyperfocus agent.

    This would be used for things that don't change during a conversation
    but might vary between sessions (like user permissions, config, etc.).
    For now, keeping it minimal as most of our config comes from env vars.
    """
    pass
