"""Type definitions for OpenAI function calling schemas and tool results.

Re-exports OpenAI SDK types for convenience and to ensure type consistency
across the codebase.
"""
from typing import TypedDict, Any
from openai.types.chat import ChatCompletionToolParam


class ToolResult(TypedDict, total=False):
    """
    Standardized return type for all tool functions.

    All tools should return a ToolResult dictionary with these fields:
    - data: The actual result data for the LLM (required)
    - include_in_context: Whether to include this result in future context (optional, default: True)
    - stub_message: Custom message to show when excluded from context (optional)
    - metadata: Additional metadata about the result (optional)
    """
    data: Any  # The actual result data for the LLM (required)
    include_in_context: bool  # Whether to keep in context (optional, defaults to True)
    stub_message: str  # Custom stub message when excluded (optional)
    metadata: dict[str, Any]  # Additional metadata (optional)


# Re-export the OpenAI SDK type for use throughout the codebase
__all__ = ["ChatCompletionToolParam", "ToolResult"]
