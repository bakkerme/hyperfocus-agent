"""Data structures for agent trajectory planning.

These are intentionally lightweight so they can be:
- Returned from a LangChain / LangGraph sub-agent as JSON
- Stored inside the Hyperfocus agent state if needed
"""

from __future__ import annotations

from typing import TypedDict


class TrajectoryStep(TypedDict):
    """Single step in a high-level execution trajectory.

    The main agent should treat these as guidance, not rigid instructions.
    """

    id: str
    description: str
    rationale: str
    suggested_tools: list[str]


class AgentTrajectory(TypedDict):
    """High-level execution trajectory for a task.

    - ``steps``: ordered list of suggested steps to accomplish the task
    - ``disabled_tools``: tools that are unlikely to help and should be gated off
    """

    comment: str
    steps: list[TrajectoryStep]
    disabled_tools: list[str]