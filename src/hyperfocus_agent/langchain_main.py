"""LangChain 1.0 main entry point for Hyperfocus Agent.

This is the main entry point that uses LangChain 1.0's create_agent API
instead of the deprecated create_react_agent or manual orchestration.

Usage:
    poetry run python -m hyperfocus_agent.langchain_main "your message here"
    poetry run hyperfocus-lc "your message here"
"""
import argparse
import os
import sys

# Phoenix observability
from phoenix.otel import register

from .langchain_agent import create_hyperfocus_agent, get_agent_config


def parse_args():
    """Parse CLI arguments for the message to send to the model."""
    parser = argparse.ArgumentParser(
        description="Send a user message to the LangChain-powered Hyperfocus agent."
    )
    parser.add_argument(
        "message",
        nargs="+",
        help="User message content for the agent"
    )
    parser.add_argument(
        "--thread-id",
        default="cli-session",
        help="Thread ID for conversation persistence (default: cli-session)"
    )
    return parser.parse_args()


def main():
    """Main entry point for LangChain-based agent."""
    print("=" * 80)
    print("HYPERFOCUS AGENT - LangChain Edition")
    print("=" * 80)
    print()

    # Initialize Phoenix observability
    phoenix_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    try:
        tracer_provider = register(
            auto_instrument=True,  # Auto-trace LangChain calls
            project_name="hyperfocus-agent-langchain",
            endpoint=f"{phoenix_endpoint}/v1/traces"
        )
        print(f"✓ Phoenix tracing initialized - UI at {phoenix_endpoint}")
    except Exception as e:
        print(f"⚠ Phoenix tracing unavailable: {e}")
        print("Continuing without observability...")
    print()

    # Parse arguments
    args = parse_args()
    user_message = " ".join(args.message)

    print(f"User: {user_message}")
    print()

    try:
        # Create the agent
        agent = create_hyperfocus_agent()
        config = get_agent_config(args.thread_id)

        print()
        print("-" * 80)
        print("AGENT RESPONSE")
        print("-" * 80)
        print()

        # Invoke the agent
        # Using invoke() for simpler output
        # Note: LangChain 1.0 streaming node name is "model" (not "agent")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config
        )

        # Extract and print the final response
        messages = result.get("messages", [])
        if messages:
            final_message = messages[-1]
            if hasattr(final_message, 'content'):
                print(final_message.content)
            else:
                print(final_message)
        else:
            print("(No response from agent)")

        print()
        print("-" * 80)
        print("✓ Agent execution complete")
        print("-" * 80)

    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
