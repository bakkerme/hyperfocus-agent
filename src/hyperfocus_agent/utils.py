"""Utility functions and related tool definitions."""


def say_hello(name: str) -> str:
    """Print a greeting message."""
    print(f"Hello, {name}!")


# Tool definitions for utility functions
UTILITY_TOOLS = [
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
