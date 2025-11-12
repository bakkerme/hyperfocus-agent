"""Generic in-memory data store for maintaining state across tool calls.

This module provides a centralized storage system that allows tools to persist
data across multiple LLM interactions. This is useful for:
- Storing parsed HTML/DOM for multi-step web scraping
- Keeping large data for task-based processing
- Maintaining BeautifulSoup objects for XPath/CSS queries
- Any other stateful operations across tool calls
"""

from typing import Any, TypedDict
from datetime import datetime


class DataEntry(TypedDict):
    """Metadata and content for a stored data entry."""
    data_id: str
    data_type: str  # e.g., "text", "html", "soup", "json"
    content: Any
    created_at: str
    metadata: dict[str, Any]


# In-memory storage for data that persists across tool calls
# Key: data_id, Value: DataEntry
_data_store: dict[str, DataEntry] = {}


def store_data(
    data_id: str,
    content: Any,
    data_type: str = "text",
    metadata: dict[str, Any] | None = None
) -> str:
    """
    Store data in memory with metadata.

    Args:
        data_id: Unique identifier for this data
        content: The data to store (can be any type)
        data_type: Type hint for the data (e.g., "text", "html", "soup", "json")
        metadata: Optional metadata dict (e.g., {"url": "...", "size": 1234})

    Returns:
        Confirmation message with storage details
    """
    entry: DataEntry = {
        "data_id": data_id,
        "data_type": data_type,
        "content": content,
        "created_at": datetime.now().isoformat(),
        "metadata": metadata or {}
    }

    _data_store[data_id] = entry

    # Create a helpful confirmation message
    size_info = ""
    if data_type == "text" and isinstance(content, str):
        size_info = f" ({len(content)} characters)"
    elif data_type == "soup":
        size_info = " (BeautifulSoup object)"

    metadata_info = ""
    if metadata:
        metadata_str = ", ".join(f"{k}={v}" for k, v in list(metadata.items())[:3])
        if len(metadata) > 3:
            metadata_str += ", ..."
        metadata_info = f"\nMetadata: {metadata_str}"

    return f"✓ Stored '{data_id}' (type: {data_type}){size_info}{metadata_info}"


def retrieve_data(data_id: str) -> Any:
    """
    Retrieve data from the store.

    Args:
        data_id: The identifier for the data to retrieve

    Returns:
        The stored content

    Raises:
        KeyError: If data_id is not found
    """
    if data_id not in _data_store:
        available = list(_data_store.keys())
        raise KeyError(
            f"Data ID '{data_id}' not found. "
            f"Available IDs: {available if available else 'None'}"
        )

    return _data_store[data_id]["content"]


def get_data_info(data_id: str) -> dict[str, Any]:
    """
    Get metadata about stored data without retrieving the content.

    Args:
        data_id: The identifier for the data

    Returns:
        Dictionary with metadata (data_id, data_type, created_at, metadata, size_info)

    Raises:
        KeyError: If data_id is not found
    """
    if data_id not in _data_store:
        available = list(_data_store.keys())
        raise KeyError(
            f"Data ID '{data_id}' not found. "
            f"Available IDs: {available if available else 'None'}"
        )

    entry = _data_store[data_id]

    # Calculate size info based on type
    size_info = None
    content = entry["content"]
    if isinstance(content, str):
        size_info = f"{len(content)} characters"
    elif isinstance(content, (list, dict)):
        size_info = f"{len(content)} items"

    return {
        "data_id": entry["data_id"],
        "data_type": entry["data_type"],
        "created_at": entry["created_at"],
        "metadata": entry["metadata"],
        "size_info": size_info
    }


def list_stored_data() -> list[dict[str, Any]]:
    """
    List all stored data with their metadata.

    Returns:
        List of metadata dictionaries for all stored data
    """
    return [get_data_info(data_id) for data_id in _data_store.keys()]


def delete_data(data_id: str) -> str:
    """
    Delete data from the store.

    Args:
        data_id: The identifier for the data to delete

    Returns:
        Confirmation message

    Raises:
        KeyError: If data_id is not found
    """
    if data_id not in _data_store:
        available = list(_data_store.keys())
        raise KeyError(
            f"Data ID '{data_id}' not found. "
            f"Available IDs: {available if available else 'None'}"
        )

    entry = _data_store.pop(data_id)
    return f"✓ Deleted '{data_id}' (type: {entry['data_type']})"


def clear_all_data() -> str:
    """
    Clear all data from the store.

    Returns:
        Confirmation message with count of deleted entries
    """
    count = len(_data_store)
    _data_store.clear()
    return f"✓ Cleared {count} entries from data store"


def data_exists(data_id: str) -> bool:
    """
    Check if data with the given ID exists.

    Args:
        data_id: The identifier to check

    Returns:
        True if data exists, False otherwise
    """
    return data_id in _data_store
