"""Docker-based benchmark runner using docker-py."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docker
from docker.errors import ContainerError, ImageNotFound, APIError

from .config import ModelConfig


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    benchmark_name: str
    model_name: str
    success: bool
    output: str
    duration_seconds: float
    error: str | None = None


@dataclass
class DockerConfig:
    """Docker container configuration."""

    image: str = "hyperfocus-agent-hyperfocus-dev"
    network: str = "hyperfocus-agent_hyperfocus-net"
    mem_limit: str = "2g"
    cpu_period: int = 100000
    cpu_quota: int = 200000  # 2 CPUs
    timeout: int = 300  # 5 minutes default
    verbose: bool = False


class DockerAgentRunner:
    """Runs the hyperfocus agent in a Docker container."""

    def __init__(
        self,
        model_config: ModelConfig,
        docker_config: DockerConfig | None = None,
        project_root: Path | None = None,
    ):
        self.model_config = model_config
        self.docker_config = docker_config or DockerConfig()
        self.project_root = project_root or Path(__file__).parents[3]
        self.client = docker.from_env()

    def _build_environment(self) -> dict[str, str]:
        """Build environment variables for the container.

        ModelConfig.to_environment() includes extra_env from benchmark-config.yml.
        """
        return self.model_config.to_environment()

    def run(self, prompt: str, working_dir: Path) -> str:
        """Run the agent with a prompt and return the output.

        Args:
            prompt: The prompt to send to the agent
            working_dir: Directory to mount as /workspace

        Returns:
            The agent's complete output as a string
        """
        # Escape quotes in prompt for shell
        escaped_prompt = prompt.replace('"', '\\"')
        command = f'hyperfocus "{escaped_prompt}"'

        # Build volume mounts matching docker-compose dev config
        src_path = self.project_root / "src"
        pyproject_path = self.project_root / "pyproject.toml"

        volumes = {
            str(working_dir.absolute()): {"bind": "/workspace/test_area", "mode": "rw"},
            str(src_path.absolute()): {"bind": "/app/src", "mode": "rw"},
            str(pyproject_path.absolute()): {"bind": "/app/pyproject.toml", "mode": "ro"},
        }

        container = None
        try:
            # Create and start container in detached mode
            container = self.client.containers.run(
                image=self.docker_config.image,
                command=command,
                volumes=volumes,
                environment=self._build_environment(),
                network=self.docker_config.network,
                mem_limit=self.docker_config.mem_limit,
                cpu_period=self.docker_config.cpu_period,
                cpu_quota=self.docker_config.cpu_quota,
                detach=True,  # Run in background so we can stream logs
                stdout=True,
                stderr=True,
            )

            # Stream logs to stdout in real-time
            # Use a thread to handle timeout since logs() blocks
            import threading

            output_lines: list[str] = []
            timed_out = False

            def stream_logs():
                nonlocal output_lines
                try:
                    for line in container.logs(stream=True, follow=True):
                        decoded = line.decode("utf-8")
                        print(decoded, end="", flush=True)
                        output_lines.append(decoded)
                except Exception:
                    pass  # Container may have been killed

            log_thread = threading.Thread(target=stream_logs, daemon=True)
            log_thread.start()

            # Wait for container with timeout
            try:
                result = container.wait(timeout=self.docker_config.timeout)
                exit_code = result.get("StatusCode", 0)
            except Exception:
                # Timeout or other error - kill the container
                timed_out = True
                try:
                    container.kill()
                except Exception:
                    pass

            # Wait for log thread to finish (with short timeout)
            log_thread.join(timeout=2)

            # Collect full output
            full_output = "".join(output_lines)

            if timed_out:
                return f"Container timed out after {self.docker_config.timeout}s:"

            if exit_code != 0:
                return f"Container error (exit {exit_code}):\n{full_output}"

            return full_output

        except ImageNotFound:
            raise RuntimeError(
                f"Docker image '{self.docker_config.image}' not found. "
                "Run 'docker compose build hyperfocus-dev' first."
            )
        except APIError as e:
            raise RuntimeError(f"Docker API error: {e}")
        finally:
            # Clean up container
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass  # Container may already be removed


class BenchmarkRunner:
    """Orchestrates benchmark runs across models."""

    def __init__(
        self,
        benchmarks_dir: Path | None = None,
        output_dir: Path | None = None,
        docker_config: DockerConfig | None = None,
    ):
        self.benchmarks_dir = benchmarks_dir or Path(__file__).parent.parent
        self.output_dir = output_dir or self.benchmarks_dir.parent / "output"
        self.docker_config = docker_config or DockerConfig()

    def discover_benchmarks(self) -> list[str]:
        """Find all available benchmarks."""
        benchmarks = []
        for path in self.benchmarks_dir.iterdir():
            if path.is_dir() and (path / "benchmark.py").exists():
                benchmarks.append(path.name)
        return sorted(benchmarks)

    def load_benchmark(self, name: str) -> Any:
        """Dynamically load a benchmark module."""
        import importlib.util

        benchmark_path = self.benchmarks_dir / name / "benchmark.py"
        if not benchmark_path.exists():
            raise ValueError(f"Benchmark '{name}' not found at {benchmark_path}")

        spec = importlib.util.spec_from_file_location(f"benchmark_{name}", benchmark_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load benchmark from {benchmark_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "Benchmark"):
            raise ValueError(f"Benchmark module {name} must define a 'Benchmark' class")

        return module.Benchmark()

    def run_benchmark(
        self,
        benchmark_name: str,
        model_config: ModelConfig,
        prompt_version: str = "default",
        iteration: int = 1,
    ) -> BenchmarkResult:
        """Run a single benchmark with a specific model.

        Args:
            benchmark_name: Name of the benchmark to run
            model_config: Model configuration
            prompt_version: Version of prompt to use
            iteration: Current iteration number (for output naming)

        Returns:
            BenchmarkResult with success status and output
        """
        # Load the benchmark
        benchmark = self.load_benchmark(benchmark_name)

        # Create agent runner
        runner = DockerAgentRunner(
            model_config=model_config,
            docker_config=self.docker_config,
        )

        # Setup output directory
        model_output_dir = self.output_dir / model_config.name.replace("/", "_") / benchmark_name
        model_output_dir.mkdir(parents=True, exist_ok=True)

        run_output_dir = model_output_dir / f"run_{iteration}"
        run_output_dir.mkdir(parents=True, exist_ok=True)

        # Run the benchmark
        start_time = time.perf_counter()
        try:
            output = benchmark.run(runner, model_config.model, prompt_version)
            duration = time.perf_counter() - start_time

            # Verify the result
            success = benchmark.verify(output)

            # Save output to file
            output_file = run_output_dir / f"{iteration}.txt"
            output_file.write_text(output)

            # Cleanup after benchmark run. This will also copy any output files to the run directory.
            benchmark.cleanup(run_output_dir)

            return BenchmarkResult(
                benchmark_name=benchmark_name,
                model_name=model_config.name,
                success=success,
                output=output,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.perf_counter() - start_time
            error_output = f"Exception: {e}"

            # Save error to file
            output_file = model_output_dir / f"{iteration}_error.txt"
            output_file.write_text(error_output)

            return BenchmarkResult(
                benchmark_name=benchmark_name,
                model_name=model_config.name,
                success=False,
                output=error_output,
                duration_seconds=duration,
                error=str(e),
            )

    def run_all(
        self,
        model_configs: list[ModelConfig],
        benchmark_names: list[str] | None = None,
        iterations: int = 1,
    ) -> list[BenchmarkResult]:
        """Run multiple benchmarks across multiple models.

        Args:
            model_configs: List of model configurations to test
            benchmark_names: Specific benchmarks to run (None = all)
            iterations: Number of times to run each benchmark

        Returns:
            List of all benchmark results
        """
        if benchmark_names is None:
            benchmark_names = self.discover_benchmarks()

        results: list[BenchmarkResult] = []
        verbose = self.docker_config.verbose

        for model_config in model_configs:
            print(f"\n{'='*60}")
            print(f"Model: {model_config.name}")
            print(f"{'='*60}")

            for benchmark_name in benchmark_names:
                print(f"\n  Benchmark: {benchmark_name}")

                for i in range(iterations):
                    iter_label = f" (iter {i+1}/{iterations})" if iterations > 1 else ""
                    print(f"    Running{iter_label}...", end=" ", flush=True)

                    result = self.run_benchmark(
                        benchmark_name, model_config, iteration=i + 1
                    )
                    results.append(result)

                    status = "✓" if result.success else "✗"
                    print(f"{status} ({result.duration_seconds:.1f}s)")

                    if result.error:
                        print(f"      Error: {result.error}")

                    # Show output preview on failure if verbose
                    if verbose and not result.success and result.output:
                        preview = result.output
                        print(f"      Output preview:\n{preview}")

                    # Show where output was saved
                    output_dir = self.output_dir / model_config.name.replace("/", "_") / benchmark_name
                    print(f"      Output saved to: {output_dir}/{i+1}.txt")

        return results
