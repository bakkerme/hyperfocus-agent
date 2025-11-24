from collections.abc import Callable

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

    tools = request.tools

    # check history for a web page load
    has_web_page = any(
        getattr(msg, 'tool_name', '') == 'web_load_web_page'
        for msg in messages
    )

    if not has_web_page:
        tools = [
            tool for tool in tools
            if not tool.name.startswith("web_") or tool.name == "web_load_web_page"
        ]

        request.tools = tools

    return handler(request)