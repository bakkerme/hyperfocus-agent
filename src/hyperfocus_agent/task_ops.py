from .types import ChatCompletionToolParam
from .task_executor import get_task_executor

# In-memory storage for data that tasks will process
# Key: data_id, Value: data content
_data_store: dict[str, str] = {}


def store_data_for_task(data_id: str, data: str) -> str:
    """
    Store data in memory to be processed by a task later.
    This allows the LLM to load large data (e.g., from a file) and then
    process it with a separate task call.

    Args:
        data_id: Unique identifier for this data
        data: The data to store

    Returns:
        Confirmation message
    """
    _data_store[data_id] = data
    data_size = len(data)
    return f"Stored {data_size} characters of data with ID '{data_id}'. You can now run a task on this data."


def execute_simple_task(task_prompt: str, data: str) -> str:
    """
    Execute a simple task on the provided data without paging.
    The task runs in an isolated LLM context without chat history.

    Args:
        task_prompt: Instructions for what to do with the data
        data: The data to process (must fit in context window)

    Returns:
        The result from the task execution
    """
    executor = get_task_executor()
    result = executor.execute_task(task_prompt, data)
    return result


def task_orientated_paging(data_id: str, task: str, page_size: int = 15000, aggregation_strategy: str = "concatenate") -> str:
    """
    Execute a task on stored data using paging for large datasets.
    The data is split into pages and processed separately, then results are aggregated.

    Args:
        data_id: ID of the data previously stored with store_data_for_task
        task: Instructions for what to do with the data
        page_size: Maximum characters per page (default: 15000)
        aggregation_strategy: How to combine results - "concatenate" or "summarize"

    Returns:
        The aggregated result from processing all pages
    """
    # Retrieve the data
    if data_id not in _data_store:
        return f"Error: No data found with ID '{data_id}'. Use store_data_for_task first."

    data = _data_store[data_id]

    # Execute the task with paging
    executor = get_task_executor()
    result = executor.execute_task_with_paging(
        task_prompt=task,
        data=data,
        page_size=page_size,
        aggregation_strategy=aggregation_strategy
    )

    return result


# Tool definitions for task operations
TASK_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "store_data_for_task",
            "description": "Store data in memory to be processed by a task later. Use this when you have large data (like file contents) that you want to process with a separate task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_id": {
                        "type": "string",
                        "description": "Unique identifier for this data (e.g., 'file_contents_readme', 'csv_data_sales')"
                    },
                    "data": {
                        "type": "string",
                        "description": "The data to store (can be very large)"
                    }
                },
                "required": ["data_id", "data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_simple_task",
            "description": "Execute a task on provided data in an isolated LLM context. Use this for processing data without maintaining chat history. The data must fit in the context window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_prompt": {
                        "type": "string",
                        "description": "Clear instructions for what the task should accomplish with the data (e.g., 'Summarize this text', 'Extract all email addresses', 'Count the number of errors')"
                    },
                    "data": {
                        "type": "string",
                        "description": "The data to process"
                    }
                },
                "required": ["task_prompt", "data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_orientated_paging",
            "description": "Execute a task on large stored data by processing it in pages. Use this when data is too large for the context window. The data is split into pages, each page is processed with the same task, then results are aggregated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_id": {
                        "type": "string",
                        "description": "ID of the data previously stored with store_data_for_task"
                    },
                    "task": {
                        "type": "string",
                        "description": "Instructions for what to do with each page of data (e.g., 'Extract all function names', 'Count error messages', 'Summarize key points')"
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Maximum characters per page (default: 15000). Adjust based on task complexity."
                    },
                    "aggregation_strategy": {
                        "type": "string",
                        "enum": ["concatenate", "summarize"],
                        "description": "How to combine page results: 'concatenate' (join all results) or 'summarize' (use LLM to create cohesive summary)"
                    }
                },
                "required": ["data_id", "task"]
            }
        }
    }
]