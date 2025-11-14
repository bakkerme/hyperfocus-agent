"""Hyperfocus agent setup and creation.

This module contains the main agent factory using LangChain's create_agent API.
"""
import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langgraph.checkpoint.memory import InMemorySaver

from .prompts import get_base_prompt
from .langchain_state import HyperfocusState, HyperfocusContext
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
    # Read environment variables
    local_base_url = os.getenv("LOCAL_OPENAI_BASE_URL")
    local_api_key = os.getenv("LOCAL_OPENAI_API_KEY")
    local_model_name = os.getenv("LOCAL_OPENAI_MODEL")

    remote_base_url = os.getenv("REMOTE_OPENAI_BASE_URL")
    remote_api_key = os.getenv("REMOTE_OPENAI_API_KEY")
    remote_model_name = os.getenv("REMOTE_OPENAI_MODEL")

    multimodal_base_url = os.getenv("MULTIMODAL_OPENAI_BASE_URL")
    multimodal_api_key = os.getenv("MULTIMODAL_OPENAI_API_KEY")
    multimodal_model_name = os.getenv("MULTIMODAL_OPENAI_MODEL")

    router_threshold = 10000
    router_threshold_str = os.getenv("LLM_ROUTER_THRESHOLD")
    if router_threshold_str and router_threshold_str.isdigit():
        router_threshold = int(router_threshold_str)

    # Validate required environment variables
    if not all([local_base_url, local_api_key, local_model_name]):
        raise ValueError(
            "LOCAL_OPENAI_BASE_URL, LOCAL_OPENAI_API_KEY, and LOCAL_OPENAI_MODEL "
            "environment variables must be set."
        )

    if not all([remote_base_url, remote_api_key, remote_model_name]):
        raise ValueError(
            "REMOTE_OPENAI_BASE_URL, REMOTE_OPENAI_API_KEY, and REMOTE_OPENAI_MODEL "
            "environment variables must be set."
        )

    print(f"Initializing agent...")
    print(f"  Local: {local_base_url} / {local_model_name}")
    print(f"  Remote: {remote_base_url} / {remote_model_name}")

    # Initialize models using LangChain's ChatOpenAI
    # Attach streaming callback so every iteration is echoed to stdout
    stream_handler = StreamingStdOutCallbackHandler()

    # Set reasonable max_tokens to avoid exceeding context limits
    local_model = ChatOpenAI(
        model=local_model_name,
        api_key=local_api_key,
        base_url=local_base_url,
        temperature=0,
        streaming=True,
        callbacks=[stream_handler],
    )

    remote_model = ChatOpenAI(
        model=remote_model_name,
        api_key=remote_api_key,
        base_url=remote_base_url,
        temperature=0,
        streaming=True,
        callbacks=[stream_handler],
    )

    # Optional multimodal model
    multimodal_model = None
    if multimodal_base_url and multimodal_api_key and multimodal_model_name:
        print(f"  Multimodal: {multimodal_base_url} / {multimodal_model_name}")
        multimodal_model = ChatOpenAI(
            model=multimodal_model_name,
            api_key=multimodal_api_key,
            base_url=multimodal_base_url,
            temperature=0,
            streaming=True,
            callbacks=[stream_handler],
        )

    # Initialize global model references for middleware
    initialize_models(local_model, remote_model, multimodal_model, router_threshold)

    # Get system prompt from agent module
    system_prompt = get_base_prompt()

    # Combine all tools into a single flat list
    all_tools = [
        *DIRECTORY_TOOLS,
        *FILE_TOOLS,
        *IMAGE_TOOLS,
        *SHELL_TOOLS,
        # *TASK_TOOLS,
        *WEB_TOOLS,
    ]

    # Middleware order matters:
    # 1. strip_processed_images - Removes images after they've been processed
    # 2. dynamic_model_selection - Routes to multimodal LLM when images detected
    agent = create_agent(
        model=local_model,  # Default model (will be overridden by middleware)
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
