"""Hyperfocus agent setup and creation.

This module contains the main agent factory using LangChain's create_agent API.
"""
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import SummarizationMiddleware, ContextEditingMiddleware, ClearToolUsesEdit

from .prompts import get_base_prompt
from .model_config import ModelConfig
from .langchain_state import HyperfocusState, HyperfocusContext
from .langchain_tools.csv_tools import CSV_TOOLS
from .langchain_tools.directory_tools import DIRECTORY_TOOLS
from .langchain_tools.file_tools import FILE_TOOLS
from .langchain_tools.image_tools import IMAGE_TOOLS
from .langchain_tools.shell_tools import SHELL_TOOLS
from .langchain_tools.task_tools import TASK_TOOLS
from .langchain_tools.web_tools import WEB_TOOLS
from .middleware.image_middleware import (
    initialize_models,
    dynamic_model_selection,
    strip_processed_images,
)
from .middleware.logging_middleware import log_tool_execution
from .middleware.context_middleware import filter_old_script_versions
from .middleware.tool_middleware import available_tools

def create_hyperfocus_agent():
    """Create the Hyperfocus agent with all middleware and tools.

    This uses LangChain 1.0's create_agent API.

    Returns:
        Configured Hyperfocus agent ready to use
    """
    # Load all model configuration from environment
    config = ModelConfig.from_environment()
    
    # Initialize global model references for middleware
    initialize_models(
        config.local,
        config.remote,
        config.multimodal,
        config.router_threshold
    )

    # Get system prompt
    system_prompt = get_base_prompt()

    # Combine all tools into a single flat list
    all_tools = [
        # *CSV_TOOLS,
        # *TASK_TOOLS,
        *DIRECTORY_TOOLS,
        *FILE_TOOLS,
        *IMAGE_TOOLS,
        *SHELL_TOOLS,
        *WEB_TOOLS,
    ]

    # summarisation_middleware = SummarizationMiddleware(
    #     model=config.local,
    #     max_tokens_before_summary=20000,  # Trigger summarization at 20000 tokens
    #     messages_to_keep=5,  # Keep last 5 messages after summary
    # )

    context_editing_middleware = ContextEditingMiddleware(
        edits=[
            ClearToolUsesEdit(
                trigger=10000,
                keep=3,
            ),
        ],
    )

    # Middleware order:
    # 1. filter_old_script_versions - Removes old create_python_script calls for same path
    # 2. strip_processed_images - Removes images after they've been processed
    # 3. dynamic_model_selection - Routes to multimodal LLM when images detected
    # 4. log_tool_execution - Logs tool calls and inputs for observability
    # 5. SummarizationMiddleware - Summarizes old messages when context gets too large
    agent = create_agent(
        model=config.local,  # Default model (can be overridden by middleware)
        tools=all_tools,
        system_prompt=system_prompt,
        state_schema=HyperfocusState,
        context_schema=HyperfocusContext,
        middleware=[
            filter_old_script_versions,
            strip_processed_images,
            dynamic_model_selection,
            log_tool_execution,
            available_tools,
            # summarisation_middleware,
            context_editing_middleware,
        ],
        checkpointer=InMemorySaver(),
    )

    print("✓ Agent initialized successfully")
    return agent


def get_agent_config(thread_id: str = "cli-session") -> dict:
    """Get the configuration for agent invocation.

    Args:
        thread_id: Unique identifier for this conversation thread

    Returns:
        Configuration dict for agent.invoke() or agent.stream()
    """
    return {
        "configurable": {
            "thread_id": thread_id
        }
    }
