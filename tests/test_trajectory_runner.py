import json
from typing import Any, Iterable

import pytest
from langchain_core.messages import AIMessage
from unittest.mock import MagicMock, patch

from hyperfocus_agent.trajectory.runner import (
    _format_tools_for_prompt,
    plan_agent_trajectory,
)


class DummyTool:
    """Simple stand-in for a LangChain tool."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description


def test_format_tools_for_prompt_basic():
    tools: Iterable[Any] = [
        DummyTool("tool_a", "Does A things"),
        DummyTool("tool_b", "Does B things"),
    ]

    text = _format_tools_for_prompt(tools)

    assert "tool_a" in text
    assert "Does A things" in text
    assert "tool_b" in text
    assert "Does B things" in text


@patch("hyperfocus_agent.trajectory.runner.ModelConfig.from_environment")
def test_plan_agent_trajectory_parses_json(mock_from_env):
    # Prepare a fake LLM that returns a valid trajectory JSON
    trajectory = {
        "steps": [
            {
                "id": "discover",
                "description": "Discover relevant web pages",
                "rationale": "Need a reliable data source first",
                "suggested_tools": ["web_load_web_page"],
            },
            {
                "id": "extract",
                "description": "Extract structured data",
                "rationale": "Prepare rows for CSV output",
                "suggested_tools": ["web_extract_with_xpath"],
            },
        ],
        "disabled_tools": ["execute_shell_command"],
    }
    json_response = json.dumps(trajectory)

    class FakeLLM:
        def __init__(self) -> None:
            self.last_messages = None

        def invoke(self, messages):
            self.last_messages = messages
            return AIMessage(content=json_response)

    fake_llm = FakeLLM()

    fake_config = MagicMock()
    fake_config.create_non_streaming_local.return_value = fake_llm
    mock_from_env.return_value = fake_config

    tools = [DummyTool("web_load_web_page"), DummyTool("web_extract_with_xpath")]

    result = plan_agent_trajectory("Turn Pokémon data into a CSV", tools)

    # Ensure JSON was parsed into a dict-like structure
    assert result["steps"][0]["id"] == "discover"
    assert result["steps"][1]["suggested_tools"] == ["web_extract_with_xpath"]
    assert result["disabled_tools"] == ["execute_shell_command"]

    # Verify that tools and task description were included in the prompt
    assert fake_llm.last_messages is not None
    user_content = fake_llm.last_messages[1]["content"]
    assert "Turn Pokémon data into a CSV" in user_content
    assert "web_load_web_page" in user_content
    assert "web_extract_with_xpath" in user_content


@patch("hyperfocus_agent.trajectory.runner.ModelConfig.from_environment")
def test_plan_agent_trajectory_invalid_json_raises(mock_from_env):
    class FakeLLM:
        def invoke(self, messages):
            # Intentionally invalid JSON
            return AIMessage(content="not valid json")

    fake_config = MagicMock()
    fake_config.create_non_streaming_local.return_value = FakeLLM()
    mock_from_env.return_value = fake_config

    with pytest.raises(ValueError):
        plan_agent_trajectory("Some task", [])

