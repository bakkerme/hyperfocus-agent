"""Custom state schema for LangChain agent migration.

This module defines the extended state schema that preserves all functionality
from the original implementation while leveraging LangChain's state management.
"""
from typing import Any, TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class HyperfocusState(TypedDict, total=False):
    """Extended agent state for Hyperfocus agent.

    LangChain 1.0 requires state to be a TypedDict (not a class extending AgentState).
    This state schema includes both the core messages field and custom fields needed
    to preserve the original behavior:
    - Iteration tracking for context stubbing
    - Tool result metadata for conditional context inclusion
    - Multimodal routing flags
    - Stored data for task execution

    Note: Using total=False makes all fields optional by default.
    The 'messages' field uses the add_messages reducer for proper message handling.
    """

    # Core messages field (required by LangChain agents)
    # Annotated with add_messages for proper message list reduction
    messages: Annotated[list[BaseMessage], add_messages]

    # Track which iteration we're on (for context stubbing logic)
    current_iteration: int

    # Metadata about tool results to control context inclusion
    # Maps tool_call_id -> {include_in_context, function_name, stub_message, created_at_iteration, context_guidance}
    tool_result_metadata: dict[str, dict]

    # LLM routing context
    # Flag to force multimodal model usage (e.g., when images are loaded)
    use_multimodal: bool

    # Task execution context
    # Store large data for task-based processing
    # Note: Could also use LangGraph Store for this, but keeping in state initially for simplicity
    stored_data: dict[str, Any]


class HyperfocusContext(TypedDict, total=False):
    """Runtime context for Hyperfocus agent.

    LangChain 1.0 uses TypedDict for context as well.
    This would be used for things that don't change during a conversation
    but might vary between sessions (like user permissions, config, etc.).
    For now, keeping it minimal as most of our config comes from env vars.
    """
    pass
