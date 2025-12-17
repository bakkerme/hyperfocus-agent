"""Runtime helper to plan an agent trajectory using the local model.

This is intentionally independent from the main LangGraph agent so it can be
called before the primary agent is created.
"""

from __future__ import annotations

import json
from typing import Any, cast
from collections.abc import Iterable

from ..model_config import ModelConfig
from .trajectory_prompts import get_trajectory_planner_prompt
from .trajectory_spec import AgentTrajectory


def _format_tools_for_prompt(tools: Iterable[Any]) -> str:
    """Render a human-readable list of tools for the planner prompt."""
    lines: list[str] = []
    for tool in tools:
        # LangChain tools usually expose .name and .description
        name = getattr(tool, "name", getattr(tool, "__name__", "unknown_tool"))
        description = getattr(tool, "description", "") or ""

        # Some tools wrap a function in .func with a docstring
        if not description:
            func = getattr(tool, "func", None)
            description = getattr(func, "__doc__", "") or ""

        # Ensure we have some minimal description
        if not description:
            description = "No description available."

        lines.append(f"- {name}: {description}")

    if not lines:
        return "No tools are available."

    return "\n".join(lines)


def plan_agent_trajectory(task_description: str, tools: Iterable[Any]) -> AgentTrajectory:
    """Plan a high-level trajectory for the given task.

    Args:
        task_description: The user's task in natural language.
        tools: Iterable of tools that will be available to the main agent.

    Returns:
        Parsed :class:`AgentTrajectory` object describing steps and disabled tools.

    Raises:
        ValueError: If the model response cannot be parsed into a valid trajectory.
    """
    # Use a non-streaming local model to avoid stdout noise
    config = ModelConfig.from_environment(verbose=False)
    llm = config.create_non_streaming_local()

    system_prompt = get_trajectory_planner_prompt()
    tools_text = _format_tools_for_prompt(tools)

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": (
                "User task:\n"
                f"{task_description}\n\n"
                "Available tools:\n"
                f"{tools_text}\n"
            ),
        },
    ]

    response = llm.invoke(messages)  # type: ignore[arg-type]
    content = getattr(response, "content", response)

    # Handle both simple string and structured content cases
    if isinstance(content, list):
        # e.g., [{"type": "text", "text": "..."}]
        # Prefer the first text-like entry
        for part in content:
            if isinstance(part, dict) and "text" in part:
                content = part["text"]
                break

    if not isinstance(content, str):
        raise ValueError("Unexpected model response format for trajectory planning.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        print(content)
        raise ValueError(f"Failed to parse trajectory JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Trajectory JSON must be an object.")

    if "steps" not in parsed or "disabled_tools" not in parsed:
        raise ValueError("Trajectory JSON must contain 'steps' and 'disabled_tools'.")

    return cast(AgentTrajectory, parsed)

