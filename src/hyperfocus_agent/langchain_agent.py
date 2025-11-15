"""Hyperfocus agent setup and creation.

This module contains the main agent factory using LangChain's create_agent API.
"""
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

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
from .langchain_middleware import (
    initialize_models,
    dynamic_model_selection,
    strip_processed_images,
)

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
        *CSV_TOOLS,
        *DIRECTORY_TOOLS,
        *FILE_TOOLS,
        *IMAGE_TOOLS,
        *SHELL_TOOLS,
        *TASK_TOOLS,
        *WEB_TOOLS,
    ]

    # Middleware order:
    # 1. strip_processed_images - Removes images after they've been processed
    # 2. dynamic_model_selection - Routes to multimodal LLM when images detected
    agent = create_agent(
        model=config.local,  # Default model (will be overridden by middleware)
        tools=all_tools,
        system_prompt=system_prompt,
        state_schema=HyperfocusState,
        context_schema=HyperfocusContext,
        middleware=[strip_processed_images, dynamic_model_selection],
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
