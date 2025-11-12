"""LangChain tool implementations.

This package contains migrated tools using the @tool decorator pattern.
Tools are organized by domain (file ops, directory ops, etc.)

Phase 2 Status: Basic implementations complete.
Phase 3+: Full feature parity with original tools.
"""

from .file_tools import FILE_TOOLS
from .directory_tools import DIRECTORY_TOOLS
from .shell_tools import SHELL_TOOLS
from .web_tools import WEB_TOOLS
from .image_tools import IMAGE_TOOLS
from .task_tools import TASK_TOOLS

# Aggregate all tools into a single list for easy import
ALL_TOOLS = (
    FILE_TOOLS +
    DIRECTORY_TOOLS +
    SHELL_TOOLS +
    WEB_TOOLS +
    IMAGE_TOOLS +
    TASK_TOOLS
)

__all__ = [
    'ALL_TOOLS',
    'FILE_TOOLS',
    'DIRECTORY_TOOLS',
    'SHELL_TOOLS',
    'WEB_TOOLS',
    'IMAGE_TOOLS',
    'TASK_TOOLS',
]
