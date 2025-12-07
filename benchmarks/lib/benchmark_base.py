"""Base class for benchmark definitions."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol


class AgentRunner(Protocol):
    """Protocol for running the agent."""

    def run(self, prompt: str, working_dir: Path) -> str:
        """Run the agent with a prompt and return the output."""
        ...


class BenchmarkBase(ABC):
    """Base class for all benchmarks.

    Each benchmark defines:
    - A name identifier
    - Input assets directory
    - A run() method that executes the benchmark
    - A verify() method that checks if the output is correct
    """

    def __init__(self, name: str, assets_dir: str | Path):
        self.name = name
        self.assets_dir = Path(assets_dir)
        self.input_path = self.assets_dir / "input"
        self.comparison_path = self.assets_dir / "comparison"

    @abstractmethod
    def run(self, runner: AgentRunner, model: str, prompt_version: str) -> str:
        """Execute the benchmark and return the agent's output.

        Args:
            runner: The agent runner to use for execution
            model: The model identifier being tested
            prompt_version: Version of the prompt being used

        Returns:
            The agent's complete output as a string
        """
        ...

    @abstractmethod
    def verify(self, output: str) -> bool:
        """Verify if the benchmark output is correct.

        Args:
            output: The agent's output from run()

        Returns:
            True if the output passes verification, False otherwise
        """
        ...
    
    def verify_with_stats(self, output: str) -> dict[str, Any]:
        """Verify output and return structured metrics.

        Default implementation wraps the boolean result from verify().

        Benchmarks with richer scoring (e.g. numeric scores) should override
        this method and include at least a ``success`` key.
        """

        return {"success": self.verify(output)}
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up any files or state created during the benchmark run."""
        ...

    def get_input_files(self) -> list[Path]:
        """List all files in the input directory."""
        if self.input_path.exists():
            return list(self.input_path.iterdir())
        return []

    def get_comparison_files(self) -> list[Path]:
        """List all files in the comparison directory."""
        if self.comparison_path.exists():
            return list(self.comparison_path.iterdir())
        return []
