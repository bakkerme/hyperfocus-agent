"""Task execution tools migrated to LangChain @tool decorator pattern.

This module provides flexible sub-agent task execution with support for:
1. Multiple input types (stored data, direct text, images)
2. Isolated execution without main conversation history
3. Optional tool access for sub-agents
4. Multimodal processing when images are present
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from ..langchain_state import  HyperfocusContext, HyperfocusState, data_exists, retrieve_data, get_data_info
from ..model_config import ModelConfig
from ..utils.image_utils import load_image_as_base64

# Import tools that sub-agents can optionally use
from .directory_tools import DIRECTORY_TOOLS
from .file_tools import FILE_TOOLS

# Constants
MAX_ROWS_PER_TASK = 200
# MAX_TEXT_LENGTH = 100000  # 100k chars max for direct text input
MAX_PREVIEW_LENGTH = 500


@tool
def run_task(
    prompt: str,
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState],
    data_id: str | None = None,
    data_text: str | None = None,
    image_path: str | None = None,
    enable_tools: bool = False,
) -> Command:
    """Execute a task using a sub-agent with flexible input types.
    
    This tool runs an isolated LLM sub-agent that can process various inputs:
    - Stored data (CSV results, web content, task results, etc.)
    - Direct text input
    - Images for vision analysis
    - Combinations of the above
    
    The sub-agent operates without access to the main conversation history,
    focusing solely on the task prompt and provided data.
    
    Args:
        prompt: Task instructions for what to do with the data
        data_id: Optional ID of stored data to process
        data_text: Optional direct text input (max 100k chars)
        image_path: Optional path to image file for vision analysis
        enable_tools: Whether to give sub-agent access to file/directory tools
        runtime: LangChain tool runtime for state access
        
    Returns:
        Command updating state with task results
        
    Examples:
        # Process stored CSV data
        run_task("Summarize key trends", data_id="csv_query_abc123")
        
        # Process direct text
        run_task("Extract key entities", data_text="Long article text...")
        
        # Analyze image
        run_task("Describe this diagram", image_path="/path/to/chart.png")
        
        # Combined: stored data + image
        run_task(
            "Compare this chart to the query results",
            data_id="csv_query_abc123",
            image_path="/path/to/chart.png"
        )
        
        # With tool access (sub-agent can read files, list directories)
        run_task(
            "Analyze the code structure and identify patterns",
            data_text="Project overview...",
            enable_tools=True
        )
    """
    try:
        # Execute using core logic
        final_response = execute_task(
            runtime=runtime,
            prompt=prompt,
            data_id=data_id,
            data_text=data_text,
            image_path=image_path,
            enable_tools=enable_tools,
        )
        
        # PREPARE SUMMARY
        input_summary = []
        if data_id:
            input_summary.append(f"data_id: {data_id}")
        if data_text:
            input_summary.append(f"text: {len(data_text)} chars")
        if image_path:
            input_summary.append(f"image: {Path(image_path).name}")
        
        summary = (
            f"✓ Task completed\n"
            f"Input: {', '.join(input_summary)}\n"
            f"Output length: {len(final_response):,} characters\n\n"
            f"{final_response}"
        )
        
        # RETURN COMMAND
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=summary,
                        tool_call_id=runtime.tool_call_id
                    )
                ]
            }
        )
        
    except ValueError as e:
        return _error_command(runtime, f"Error: {e}")
    except Exception as e:
        return _error_command(runtime, f"Error: Task execution failed: {e}")


@tool
def run_task_on_stored_row_data(
    data_id: str,
    prompt: str,
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState],
) -> str:
    """Execute a task on stored CSV query results using a sub-agent.
    
    This is a specialized wrapper around run_task() for CSV data processing.
    It validates that the data is a csv_query_result and enforces row limits.
    
    Args:
        data_id: ID of stored csv_query_result data
        prompt: Task instructions for processing the data
        runtime: LangChain tool runtime for state access
        
    Returns:
        Command updating state with task results
        
    Example:
        After running query_csv_sql and getting result ID 'csv_query_abc123':
        run_task_on_stored_row_data(
            'csv_query_abc123',
            'Categorize each transaction and extract key entities'
        )
    """
    # Validate it's CSV data with row limits
    if not data_exists(runtime, data_id):
        return f"Error: No data found with ID '{data_id}'"
    
    try:
        info = get_data_info(runtime, data_id)
        if not info or info.get("data_type") != "csv_query_result":
            return f"Error: Data ID '{data_id}' is not of type 'csv_query_result'."

        metadata = info["metadata"]
        row_count = metadata.get("row_count", 0)
        
        if row_count > MAX_ROWS_PER_TASK:
            return f"Error: Too many rows ({row_count}). Maximum {MAX_ROWS_PER_TASK} rows allowed.\n" \
                   f"Consider filtering data with query_csv_sql before running task."
    except Exception:
        # If we can't get metadata, let run_task handle it
        pass
    
    # Delegate to generic run_task
    result = execute_task(
        runtime=runtime,
        prompt=prompt,
        data_id=data_id,
        enable_tools=True,
    )

    return result

# Core task execution logic
def execute_task(
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState],
    prompt: str,
    data_id: str | None = None,
    data_text: str | None = None,
    image_path: str | None = None,
    enable_tools: bool = False,
) -> str:
    """Execute a task using a sub-agent with flexible input types.
    
    This is the internal implementation that can be called directly by other tools
    without going through the LangChain @tool decorator and Command system.
    
    Args:
        prompt: Task instructions for what to do with the data
        data_id: Optional ID of stored data to process
        data_text: Optional direct text input (max 100k chars)
        image_path: Optional path to image file for vision analysis
        enable_tools: Whether to give sub-agent access to file/directory tools
        
    Returns:
        String containing the sub-agent's response
        
    Raises:
        ValueError: If inputs are invalid or task execution fails
        
    Examples:
        # From another tool
        result = execute_task(
            runtime,
            "Summarize this data",
            data_id="csv_query_abc123"
        )
        
        # With direct text
        result = execute_task(
            runtime,
            "Extract key points",
            data_text="Long article..."
        )
    """
    # 1. VALIDATE INPUTS
    if not any([data_id, data_text, image_path]):
        raise ValueError("Must provide at least one of: data_id, data_text, or image_path")
    
    # if data_text and len(data_text) > MAX_TEXT_LENGTH:
    #     raise ValueError(
    #         f"data_text exceeds maximum length ({len(data_text)} > {MAX_TEXT_LENGTH} chars)"
    #     )
    
    # 2. BUILD TASK MESSAGES
    messages = _build_task_messages(prompt, data_id, data_text, image_path, runtime)
    
    # 3. CREATE APPROPRIATE SUB-AGENT
    has_image = image_path is not None
    sub_agent = _create_sub_agent(has_image=has_image, enable_tools=enable_tools)
    
    # 4. EXECUTE TASK
    result = sub_agent.invoke(
        {"messages": messages},  # type: ignore
        config={"recursion_limit": 10}
    )
    
    # Extract response
    output_messages = result.get("messages", [])
    if output_messages:
        return output_messages[-1].content
    else:
        raise ValueError("No response from sub-agent")


# Helper functions

def _build_task_messages(
    prompt: str,
    data_id: str | None,
    data_text: str | None,
    image_path: str | None,
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState],
) -> list[HumanMessage]:
    """Build message list for sub-agent based on input types.
    
    Supports text-only, multimodal, and combined inputs.
    """
    
    # 1. Build prompt text with data
    data_to_process = ""
    
    if data_id:
        data = _load_and_format_data(runtime, data_id)
        data_to_process = data
    elif data_text:
        data_to_process = data_text

    messages = [
        HumanMessage(content=prompt),
        HumanMessage(content=data_to_process),
    ]

    # 2. Add image if provided
    if image_path:
        image_data = load_image_as_base64(image_path)
        messages.append(HumanMessage(content={
            "type": "image_url",
            "image_url": {
                "url": f"data:{image_data['mime_type']};base64,{image_data['base64_data']}"
            }
        }))
    
    return messages

def _load_and_format_data(runtime: ToolRuntime[HyperfocusContext, HyperfocusState], data_id: str) -> str:
    """Load stored data and format it appropriately based on type.
    
    Handles:
    - csv_query_result → JSON rows
    - csv_table → metadata summary
    - markdown → raw markdown
    - task_result → previous task output
    - text → raw text
    """
    if not data_exists(runtime, data_id):
        raise ValueError(f"Data ID '{data_id}' not found")
    
    data = retrieve_data(runtime, data_id)
    if not data:
        raise ValueError(f"Data ID '{data_id}' could not be retrieved")

    content = data["content"]
    data_type = data["data_type"]
    metadata = data["metadata"]
    
    # Format based on data type
    if data_type == "csv_query_result":
        # CSV query result with rows and columns
        if isinstance(content, dict):
            rows = content.get("rows", [])
            columns = content.get("columns", [])
            return _format_csv_rows(columns, rows)
        return json.dumps(content, indent=2)
    
    elif data_type == "csv_table":
        # CSV table metadata (don't load full table)
        return (
            f"CSV Table Summary:\n"
            f"Path: {metadata.get('path', 'unknown')}\n"
            f"Rows: {metadata.get('rows', 0):,}\n"
            f"Columns: {', '.join(metadata.get('column_names', []))}\n"
            f"Note: Use query_csv_sql to extract specific data before processing."
        )
    
    elif data_type in ("markdown", "text", "task_result"):
        # Return as-is
        return str(content)
    
    else:
        # Generic fallback: try JSON, then string
        if isinstance(content, dict):
            return json.dumps(content, indent=2)
        return str(content)


def _format_csv_rows(columns: list[str], rows: list[dict]) -> str:
    """Format CSV rows as JSON for LLM prompt."""
    if not rows:
        return "(no rows)"
    
    try:
        return json.dumps(rows, indent=2)
    except (TypeError, ValueError):
        return repr(rows)


def _create_sub_agent(
    has_image: bool = False,
    enable_tools: bool = False,
):
    """Create sub-agent with appropriate model and tools.
    
    Args:
        has_image: Whether task includes image (use multimodal model)
        enable_tools: Whether to give sub-agent access to tools
    """
    config = ModelConfig.from_environment()
    
    # Select model based on input type
    if has_image and config.multimodal:
        # Create non-streaming multimodal model
        sub_llm = ChatOpenAI(
            model=config.multimodal.model_name,  # type: ignore
            api_key=config.multimodal.openai_api_key,  # type: ignore
            base_url=config.multimodal.openai_api_base,  # type: ignore
            temperature=0,
            streaming=False,
        )
        model_name = "multimodal"
    else:
        sub_llm = config.create_non_streaming_local()
        model_name = "local"
    
    # Select tools
    tools = []
    if enable_tools:
        tools = [*DIRECTORY_TOOLS, *FILE_TOOLS]
    
    # Build system prompt
    system_prompt = _get_task_system_prompt(has_image, enable_tools)
    
    print(f"→ [Sub-Agent] Using {model_name.upper()} model, tools={'enabled' if enable_tools else 'disabled'}")
    
    return create_agent(
        model=sub_llm,
        tools=tools,
        system_prompt=system_prompt,
        state_schema=None,
        context_schema=None,
        middleware=[],
        checkpointer=None,
    )


def _get_task_system_prompt(has_image: bool, enable_tools: bool) -> str:
    """Generate system prompt for sub-agent based on capabilities."""
    base = (
        "You are a focused data processing assistant. "
        "Process the provided data according to the user's instructions. "
        "Be concise and structured in your output."
    )
    
    if has_image:
        base += " You have vision capabilities and can analyze images."
    
    if enable_tools:
        base += " You have access to file and directory tools to gather additional context if needed."
    
    return base


def _hash_string(text: str) -> str:
    """Hash text for unique ID generation."""
    return hashlib.md5(text.encode()).hexdigest()


def _error_command(
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState], 
    message: str
) -> Command:
    """Helper to return error as Command."""
    return Command(
        update={
            "messages": [
                ToolMessage(content=message, tool_call_id=runtime.tool_call_id)
            ]
        }
    )


# Export tools as a list for easy import
TASK_TOOLS = [
    run_task,
    run_task_on_stored_row_data,
]
