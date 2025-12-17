"""Task execution tools migrated to LangChain @tool decorator pattern.

This module provides flexible sub-agent task execution with support for:
1. Multiple input types (stored data, direct text, images)
2. Isolated execution without main conversation history
3. Optional tool access for sub-agents
4. Multimodal processing when images are present
"""
import json
from pathlib import Path

from langchain.tools import tool, ToolRuntime
from ..langchain_state import  HyperfocusContext, HyperfocusState, data_exists, retrieve_data, get_data_info

from ..task.task import execute_task as execute_task

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
) -> str:
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
        Summary of task execution and results as a string
        
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
        # Resolve data to process based on inputs (runtime-dependent parts handled here)
        data_to_process: str | None = None
        input_summary: list[str] = []

        if data_id:
            if not data_exists(runtime, data_id):
                return f"Error: No data found with ID '{data_id}'"
            data_to_process = _load_and_format_data(runtime, data_id)
            input_summary.append(f"data_id: {data_id}")
        elif data_text:
            data_to_process = data_text
            input_summary.append(f"text: {len(data_text)} chars")

        if image_path:
            input_summary.append(f"image: {Path(image_path).name}")

        if not data_to_process and not image_path:
            return "Error: Must provide at least one of: data_id, data_text, or image_path"

        # Execute using core logic (runtime-free)
        final_response = execute_task(
            prompt=prompt,
            data_text=data_to_process,
            image_path=image_path,
            enable_tools=enable_tools,
        )

        summary = (
            f"✓ Task completed\n"
            f"Input: {', '.join(input_summary) if input_summary else 'n/a'}\n"
            f"Output length: {len(final_response):,} characters\n\n"
            f"{final_response}"
        )

        return summary

    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Task execution failed: {e}"


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
        String containing the sub-agent's response or an error message
        
    Example:
        After running query_csv_sql and getting result ID 'csv_query_abc123':
        run_task_on_stored_row_data(
            'csv_query_abc123',
            'Categorize each transaction and extract key entities'
        )
    """
    try:
        # Validate it's CSV data with row limits
        if not data_exists(runtime, data_id):
            return f"Error: No data found with ID '{data_id}'"

        info = get_data_info(runtime, data_id)
        if not info or info.get("data_type") != "csv_query_result":
            return f"Error: Data ID '{data_id}' is not of type 'csv_query_result'."

        metadata = info["metadata"]
        row_count = metadata.get("row_count", 0)

        if row_count > MAX_ROWS_PER_TASK:
            return (
                f"Error: Too many rows ({row_count}). Maximum {MAX_ROWS_PER_TASK} rows allowed.\n"
                f"Consider filtering data with query_csv_sql before running task."
            )
    except Exception:
        # If we can't get metadata, let run_task handle it
        pass

    # Load and format data, then delegate to core executor
    try:
        formatted_data = _load_and_format_data(runtime, data_id)
    except ValueError as e:
        return f"Error: {e}"

    return execute_task(
        prompt=prompt,
        data_text=formatted_data,
        enable_tools=True,
    )

# Helper functions
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

# Export tools as a list for easy import
TASK_TOOLS = [
    run_task,
    run_task_on_stored_row_data,
]
