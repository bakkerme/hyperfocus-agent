"""Custom state schema for LangChain agent migration.

This module defines the extended state schema that preserves all functionality
from the original implementation while leveraging LangChain's state management.
"""
from typing import Any
from langgraph.prebuilt.chat_agent_executor import AgentState


class HyperfocusState(AgentState):
    """Extended agent state for Hyperfocus agent.

    This state schema extends the base AgentState with custom fields needed
    to preserve the original behavior:
    - Iteration tracking for context stubbing
    - Tool result metadata for conditional context inclusion
    - Multimodal routing flags
    - Stored data for task execution

    Note: AgentState already provides the 'messages' field, so we only need
    to add our custom fields here. All custom fields have defaults to make
    them optional.
    """

    # Custom state fields for original functionality
    # Note: TypedDict fields can't have defaults, but fields not listed in __required_keys__
    # are automatically optional. These will be initialized in the agent invocation.

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


class HyperfocusContext:
    """Runtime context for Hyperfocus agent.

    This would be used for things that don't change during a conversation
    but might vary between sessions (like user permissions, config, etc.).
    For now, keeping it minimal as most of our config comes from env vars.
    """
    pass
