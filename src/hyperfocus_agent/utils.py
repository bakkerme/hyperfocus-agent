"""Utility functions and related tool definitions."""
from .types import ChatCompletionToolParam


def say_hello(name: str) -> str:
    """Print a greeting message."""
    message = f"Hello, {name}!"
    print(message)
    return message


# Tool definitions for utility functions
UTILITY_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "say_hello",
            "description": "Says hello to someone",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The person's name"
                    }
                },
                "required": ["name"]
            }
        }
    }
]
