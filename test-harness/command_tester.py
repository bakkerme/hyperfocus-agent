#!/usr/bin/env python3
"""
Command Loop Tester - Run a command repeatedly and track success rate based on output matching.
"""

import subprocess
import sys
import argparse
import time
import statistics
from typing import Tuple


def run_command_and_check(command: str, search_string: str, timeout: int = 300) -> Tuple[bool, str]:
    """
    Run a command and check if the output contains the search string.
    Streams output to screen in real-time, line by line.

    Args:
        command: The command to execute
        search_string: The string to search for in the output
        timeout: Maximum seconds to wait for command (default: 300)

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,  # Line buffered
        )

        collected_output = []
        start_time = time.time()

        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                process.kill()
                return False, f"Command timed out after {timeout} seconds"

            # Read line from stdout
            line = process.stdout.readline()

            if line:
                print(line, end='')  # Stream to screen
                collected_output.append(line)

            # Check if process finished
            if process.poll() is not None:
                # Read any remaining output
                remaining = process.stdout.read()
                if remaining:
                    print(remaining, end='')
                    collected_output.append(remaining)
                break

        # Combine all output and check for search string
        full_output = ''.join(collected_output)
        success = search_string in full_output

        return success, full_output

    except Exception as e:
        return False, f"Error running command: {str(e)}"


def main():
    successes = 0
    failures = 0
    iteration = 0

    iterations = 15
    command = "/home/brandon/sources/hyperfocus-agent/scripts/run-docker.sh dev-prompt 'Load pikachu.jpg and describe the card content, then look up the card symbol code (it will be a small string like 'cp4') and look it up in the provided website and include the set name alongside the card content. Make sure to get an exact match on the code, since there are sets and subsets that have similar codes. http://asset-server:8080/pokemon.html'"
    search = '151'
    timeout = 600
    verbose = True

    print(f"Command: {command}")
    print(f"Search string: '{search}'")
    print(f"Iterations: {'infinite' if iterations == 0 else iterations}")
    print(f"Timeout: {timeout}s")
    print("-" * 60)

    # Lists for timing stats
    durations = []  # all runs
    durations_success = []  # successful runs
    durations_failure = []  # failed runs

    try:
        while iterations == 0 or iteration < iterations:
            iteration += 1

            # Run command and check result (time the run)
            t0 = time.perf_counter()
            success, output = run_command_and_check(
                command,
                search,
                timeout,
            )
            t1 = time.perf_counter()
            dur = t1 - t0
            durations.append(dur)

            # Update counters
            if success:
                successes += 1
                print("✓", end="", flush=True)
                durations_success.append(dur)
            else:
                failures += 1
                print("✗", end="", flush=True)
                durations_failure.append(dur)

                # Print failure details if verbose
                if verbose:
                    print(f"\n  Failure on iteration {iteration}:")
                    print(f"  Output preview: {output[:200]}...")
                    print()

            # Print stats every 50 iterations or at the end
            total = successes + failures
            if total % 50 == 0 or (iterations > 0 and iteration == iterations):
                success_rate = (successes / total * 100) if total > 0 else 0
                # Also print a quick timing summary for recent runs
                avg_time = statistics.mean(durations) if durations else 0
                try:
                    stddev_time = statistics.stdev(durations) if len(durations) > 1 else 0
                except statistics.StatisticsError:
                    stddev_time = 0
                print(f"\n[{total} runs] Success: {successes} | Failures: {failures} | Rate: {success_rate:.1f}% | Avg: {avg_time:.2f}s ± {stddev_time:.2f}s")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    finally:
        # Print final statistics
        total = successes + failures
        if total > 0:
            success_rate = (successes / total * 100)
            print("\n" + "=" * 60)
            print(f"FINAL RESULTS ({total} total runs)")
            print(f"  Successes: {successes}")
            print(f"  Failures:  {failures}")
            print(f"  Success Rate: {success_rate:.2f}%")
            print()

            # Timing summary
            if durations:
                avg = statistics.mean(durations)
                minimum = min(durations)
                maximum = max(durations)
                try:
                    sd = statistics.stdev(durations) if len(durations) > 1 else 0
                except statistics.StatisticsError:
                    sd = 0

                print("  Timing (all runs):")
                print(f"    Average: {avg:.3f}s")
                print(f"    StdDev:  {sd:.3f}s")
                print(f"    Min:     {minimum:.3f}s")
                print(f"    Max:     {maximum:.3f}s")

            # Optional: timing summary per success/failure
            if durations_success:
                avg_s = statistics.mean(durations_success)
                sd_s = statistics.stdev(durations_success) if len(durations_success) > 1 else 0
                print(f"  Timing (successes - {len(durations_success)} runs): avg {avg_s:.3f}s ± {sd_s:.3f}s")
            if durations_failure:
                avg_f = statistics.mean(durations_failure)
                sd_f = statistics.stdev(durations_failure) if len(durations_failure) > 1 else 0
                print(f"  Timing (failures - {len(durations_failure)} runs): avg {avg_f:.3f}s ± {sd_f:.3f}s")

            print("=" * 60)


if __name__ == "__main__":
    main()
