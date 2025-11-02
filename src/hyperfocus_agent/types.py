"""Type definitions for OpenAI function calling schemas.

Re-exports OpenAI SDK types for convenience and to ensure type consistency
across the codebase.
"""
from openai.types.chat import ChatCompletionToolParam

# Re-export the OpenAI SDK type for use throughout the codebase
__all__ = ["ChatCompletionToolParam"]
