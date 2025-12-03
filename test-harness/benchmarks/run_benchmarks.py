#!/usr/bin/env python3
"""CLI for running hyperfocus-agent benchmarks."""

import argparse
import json
import statistics
import sys
from pathlib import Path

from lib import BenchmarkRunner, DockerConfig, load_config


def print_summary(results: list) -> None:
    """Print a summary of benchmark results."""
    if not results:
        print("No results to summarize.")
        return

    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)

    # Overall stats for the entire run
    total_runs = len(results)
    total_successes = sum(1 for r in results if r.success)
    total_durations = [r.duration_seconds for r in results]
    overall_rate = (total_successes / total_runs * 100) if total_runs else 0
    overall_avg = statistics.mean(total_durations)
    overall_std = statistics.stdev(total_durations) if total_runs > 1 else 0
    overall_total_duration = sum(total_durations)

    print("Overall:")
    print(f"  Runs: {total_runs}")
    print(f"  Success Rate: {total_successes}/{total_runs} ({overall_rate:.1f}%)")
    print(f"  Avg Duration: {overall_avg:.2f}s (std: {overall_std:.2f}s)")
    print(f"  Total Duration: {overall_total_duration:.2f}s")

    # Group by model
    by_model: dict[str, list] = {}
    for r in results:
        by_model.setdefault(r.model_name, []).append(r)

    for model_name, model_results in by_model.items():
        successes = sum(1 for r in model_results if r.success)
        total = len(model_results)
        rate = (successes / total * 100) if total > 0 else 0

        durations = [r.duration_seconds for r in model_results]
        avg_dur = statistics.mean(durations)
        std_dur = statistics.stdev(durations) if len(durations) > 1 else 0

        print(f"\nModel: {model_name}")
        print(f"  Success Rate: {successes}/{total} ({rate:.1f}%)")
        print(f"  Avg Duration: {avg_dur:.2f}s (std: {std_dur:.2f}s)")

        # Group by benchmark within model
        by_benchmark: dict[str, list] = {}
        for r in model_results:
            by_benchmark.setdefault(r.benchmark_name, []).append(r)

        for benchmark_name, bench_results in by_benchmark.items():
            b_successes = sum(1 for r in bench_results if r.success)
            b_total = len(bench_results)
            b_rate = (b_successes / b_total * 100) if b_total > 0 else 0
            b_durations = [r.duration_seconds for r in bench_results]
            b_avg = statistics.mean(b_durations)
            b_std = statistics.stdev(b_durations) if len(b_durations) > 1 else 0
            b_total_duration = sum(b_durations)
            print(
                f"    {benchmark_name}: {b_successes}/{b_total} ({b_rate:.1f}%) | "
                f"avg {b_avg:.2f}s (std: {b_std:.2f}s) | total {b_total_duration:.2f}s"
            )

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Run hyperfocus-agent benchmarks in Docker containers"
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        help="Model name from benchmark-config.yml (e.g., grok41fast, qwen3next)",
    )
    parser.add_argument(
        "--remote", "-r",
        type=str,
        help="Model to use for remote/fallback tasks (required)",
    )
    parser.add_argument(
        "--multimodal", "-M",
        type=str,
        help="Model to use for multimodal/vision tasks (e.g., qwen3vl30b)",
    )
    parser.add_argument(
        "--benchmark", "-b",
        type=str,
        help="Specific benchmark to run (default: all)",
    )
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=1,
        help="Number of iterations per benchmark (default: 1)",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models from config and exit",
    )
    parser.add_argument(
        "--list-benchmarks",
        action="store_true",
        help="List available benchmarks and exit",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to benchmark-config.yml (default: auto-detect)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds for each run (default: 300)",
    )
    parser.add_argument(
        "--image",
        type=str,
        default="hyperfocus-agent-hyperfocus-dev",
        help="Docker image to use",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        help="Output directory for results",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output on failures",
    )

    args = parser.parse_args()

    # Load config
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    # List models if requested
    if args.list_models:
        print("Available models:")
        for name in config.list_models():
            model = config.get_model(name)
            print(f"  {name}: {model.model}: {model.provider_name}")
        return 0

    # Setup runner
    benchmarks_dir = Path(__file__).parent
    docker_config = DockerConfig(
        image=args.image,
        timeout=args.timeout,
        verbose=args.verbose,
    )
    runner = BenchmarkRunner(
        benchmarks_dir=benchmarks_dir,
        output_dir=args.output_dir,
        docker_config=docker_config,
    )

    # List benchmarks if requested
    if args.list_benchmarks:
        benchmarks = runner.discover_benchmarks()
        print("Available benchmarks:")
        for name in benchmarks:
            print(f"  - {name}")
        return 0

    # Require model for actual benchmark runs
    if not args.model:
        print("Error: --model is required to run benchmarks")
        print("Use --list-models to see available models")
        return 1

    # Get model config
    try:
        model_config = config.get_model(args.model)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    if not model_config.base_url:
        print(f"Error: Model '{args.model}' has no base_url configured")
        return 1

    # Check remote is specified (required)
    if not args.remote:
        print("Error: --remote is required to run benchmarks")
        print("Use --list-models to see available models")
        return 1

    # Apply remote model
    try:
        model_config = config.with_remote(model_config, args.remote)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    # Apply multimodal model if specified
    if args.multimodal:
        try:
            model_config = config.with_multimodal(model_config, args.multimodal)
        except ValueError as e:
            print(f"Error: {e}")
            return 1

    print(f"Model: {model_config.name}")
    print(f"  Provider URL: {model_config.base_url}")
    print(f"  Model ID: {model_config.model}")
    print(f"  Remote: {model_config.remote_model}")
    if model_config.multimodal_model:
        print(f"  Multimodal: {model_config.multimodal_model}")

    # Determine which benchmarks to run
    benchmark_names = [args.benchmark] if args.benchmark else None

    # Run benchmarks
    results = runner.run_all(
        model_configs=[model_config],
        benchmark_names=benchmark_names,
        iterations=args.iterations,
    )

    # Output results
    if args.json:
        output = [
            {
                "benchmark": r.benchmark_name,
                "model": r.model_name,
                "success": r.success,
                "duration": r.duration_seconds,
                "error": r.error,
            }
            for r in results
        ]
        print(json.dumps(output, indent=2))
    else:
        print_summary(results)

    # Return exit code based on success
    all_passed = all(r.success for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
