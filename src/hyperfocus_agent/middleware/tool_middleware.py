from collections.abc import Callable
import pprint

from langchain.agents.middleware import (
    wrap_model_call,
    ModelRequest,
    ModelResponse,
)

@wrap_model_call
def available_tools(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Adjust the available tools in the state.

    This allows for dynamic tool availability based on context.
    """
    state = request.state
    messages = state.get("messages", [])
    # Capture the full, canonical tool list once so we can
    # safely derive filtered views without permanently losing tools.
    all_tools = state.get("all_tools")
    if all_tools is None:
        all_tools = list(request.tools)
        state["all_tools"] = all_tools

    tools = all_tools

    # Before a web page has been loaded, restrict web tools
    # to just the loader; afterwards, restore the full list.
    if not has_loaded_web_page(messages):
        tools = remove_web_tools(tools)

    # Use a filtered copy for this model call only.
    request.tools = list(tools)

    return handler(request)

def has_loaded_web_page(messages: list) -> bool:
    """Check if a web page has been loaded in the conversation history."""
    return any(
        getattr(msg, 'name', '') == 'web_load_web_page'
        for msg in messages
    )


def remove_web_tools(tools: list) -> list:
    """Remove web-related tools except for web_load_web_page."""
    return [
        tool for tool in tools
        if not tool.name.startswith("web_") or tool.name == "web_load_web_page"
    ]