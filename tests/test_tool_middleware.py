"""Tests for the tool middleware business logic.

These tests focus on the pure helper functions and the
`available_tools` middleware behavior.
"""

from dataclasses import dataclass

from langchain.agents.middleware import ModelRequest

from src.hyperfocus_agent.middleware.tool_middleware import (
    available_tools,
    has_loaded_web_page,
    remove_web_tools,
)


@dataclass
class FakeTool:
    name: str

def test_has_loaded_web_page_true_when_tool_message_present():
    class Msg:
        def __init__(self, tool_name: str):
            self.tool_name = tool_name

    messages = [Msg("web_load_web_page")]

    assert has_loaded_web_page(messages) is True


def test_has_loaded_web_page_false_when_no_matching_message():
    class Msg:
        def __init__(self, tool_name: str | None = None):
            if tool_name is not None:
                self.tool_name = tool_name

    messages = [Msg("other_tool"), Msg(), object()]

    assert has_loaded_web_page(messages) is False


def test_remove_web_tools_keeps_non_web_and_loader():
    tools = [
        FakeTool("shell_run"),
        FakeTool("web_load_web_page"),
        FakeTool("web_readable_web_get"),
        FakeTool("web_other"),
    ]

    filtered = remove_web_tools(tools)

    names = [t.name for t in filtered]

    # Non-web tool is kept
    assert "shell_run" in names
    # Loader is kept
    assert "web_load_web_page" in names
    # Other web_* tools are removed
    assert "web_readable_web_get" not in names
    assert "web_other" not in names

def test_web_tools_exist_after_page_load_in_middleware():
    """Test that after a web page load, all web tools are available."""
    tools = [
        FakeTool("shell_run"),
        FakeTool("web_load_web_page"),
        FakeTool("web_readable_web_get"),
        FakeTool("web_other"),
    ]
   
    class FakeHandler: 