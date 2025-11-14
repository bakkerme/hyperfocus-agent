"""Web scraping tools migrated to LangChain @tool decorator pattern.

This module replaces web_ops.py with LangChain-compatible tools.
Full implementation with data store integration and section extraction.
"""
import requests
import hashlib
import html2text
from langchain.tools import tool, ToolRuntime
from mrkdwn_analysis import MarkdownAnalyzer
from datetime import datetime
from langgraph.types import Command
from langchain_core.messages import ToolMessage

from ..data_store import get_data_info, store_data, retrieve_data, data_exists
from ..langchain_state import DataEntry, HyperfocusState, HyperfocusContext 

@tool
def readable_web_get(url: str, runtime: ToolRuntime) -> Command:
    """Fetch and return the content of a web page in an LLM-readable format.

    Pipeline:
    1. Fetch raw HTML with requests
    2. Convert HTML to clean markdown with html2text
    3. Extract headings from markdown
    4. Store full markdown in data store
    5. Return only headings with data_id for subsequent section extraction

    Args:
        url: The URL to fetch

    Returns:
        String with headings list and data_id for extracting sections
    """
    try:
        # Step 1: Fetch raw HTML
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Fix encoding: requests defaults to ISO-8859-1 when no charset is in Content-Type header
        # Force UTF-8 if the apparent encoding is UTF-8 and the declared encoding is not
        if (response.encoding and response.encoding.lower() in ('iso-8859-1', 'windows-1252')
            and response.apparent_encoding and 'utf' in response.apparent_encoding.lower()):
            response.encoding = 'utf-8'

        # Step 2: Convert to markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.unicode_snob = True
        h.body_width = 0  # Don't wrap lines

        markdown_content = h.handle(response.text)

        # Step 3: Extract headings from markdown
        doc = MarkdownAnalyzer.from_string(markdown_content)
        headers_dict = doc.identify_headers()
        headers_list = headers_dict.get('Header', [])

        # Step 4: Store markdown in data store
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        data_id = f"markdown_{url_hash}"

        entry: DataEntry = {
            "data_id": data_id,
            "data_type": "markdown",
            "content": markdown_content,
            "created_at": datetime.now().isoformat(),
            "metadata": {"url": url, "size": len(markdown_content)}
        }

        # Step 5: Format headings for display
        heading_lines = []
        for heading in headers_list:
            indent = "  " * (heading['level'] - 1)
            heading_lines.append(f"{indent}{'#' * heading['level']} {heading['text']} (line {heading['line']})")

        headings_text = "\n".join(heading_lines) if heading_lines else "(No headings found)"

        message = f"""✓ Fetched and converted page to markdown
URL: {url}
Data ID: {data_id}
Markdown size: {len(markdown_content)} characters

Found {len(headers_list)} heading(s):
{headings_text}

To extract a specific section, use:
get_readable_web_section(data_id="{data_id}", heading_query="heading text to search for")

This will return the full content from that heading until the next heading of the same or higher level."""

        return Command(update={
            "stored_data": {data_id: entry},
             "messages": [
                ToolMessage(
                    content=message,  # This is what the model sees
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })

    except requests.RequestException as e:
        message = f"Error fetching URL: {str(e)}"
        return Command(update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })
        
    except Exception as e:
        message = f"Error processing page: {str(e)}"
        return Command(update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })

@tool
def get_readable_web_section(data_id: str, heading_query: str, runtime: ToolRuntime[HyperfocusContext, HyperfocusState]) -> str:
    """Extract a section of markdown content based on a heading query.

    Finds the heading that matches the query (case-insensitive) and extracts
    all content from that heading until the next heading of the same or higher level.

    Args:
        data_id: The data ID from readable_web_get
        heading_query: The heading text to search for (case-insensitive, partial match)

    Returns:
        String with the markdown content from the matched heading to the next same-level heading
    """
    try:
        # Retrieve the stored markdown
        if not data_exists(runtime, data_id):
            return f"Error: No data found with ID '{data_id}'. Use readable_web_get first."

        markdown_text = retrieve_data(runtime, data_id)
        if not isinstance(markdown_text, str):
            return f"Error: '{data_id}' is not markdown text."

        # Extract all headings
        doc = MarkdownAnalyzer.from_string(markdown_text)
        headers_dict = doc.identify_headers()
        headers = headers_dict.get('Header', [])

        if not headers:
            return "Error: No headings found in markdown content"

        # Find the matching heading (case-insensitive partial match)
        query_lower = heading_query.lower()
        matched_heading = None
        matched_index = -1

        for i, heading in enumerate(headers):
            if query_lower in heading['text'].lower():
                matched_heading = heading
                matched_index = i
                break

        if not matched_heading:
            available_headings = "\n".join([f"  - {h['text']}" for h in headers[:10]])
            if len(headers) > 10:
                available_headings += f"\n  ... and {len(headers) - 10} more"
            error_msg = f"Error: No heading found matching '{heading_query}'.\n\nAvailable headings:\n{available_headings}"
            return error_msg

        # Find the end line (next heading of same or higher level)
        start_line = matched_heading['line']
        start_level = matched_heading['level']
        end_line = None

        for i in range(matched_index + 1, len(headers)):
            next_heading = headers[i]
            if next_heading['level'] <= start_level:
                end_line = next_heading['line']
                break

        # Split markdown into lines
        lines = markdown_text.split('\n')

        # Extract the section (line numbers are 1-indexed)
        if end_line is not None:
            # Extract from start_line to end_line (exclusive)
            extracted_lines = lines[start_line - 1:end_line - 1]
        else:
            # Extract from start_line to end of document
            extracted_lines = lines[start_line - 1:]

        extracted_content = '\n'.join(extracted_lines)

        metadata = get_data_info(runtime, data_id)

        store_data_id = f"markdown_section_{hashlib.md5((data_id + heading_query).encode()).hexdigest()[:8]}"
        store_data(
            data_id=store_data_id,
            content=extracted_content,
            data_type="markdown",
            metadata={"url": metadata.get("url", ""), "size": len(extracted_content)}
        )

        result_message = f"""✓ Extracted section: {matched_heading['text']}
Level: {matched_heading['level']}
Lines: {start_line} to {end_line if end_line else 'end'}
Content length: {len(extracted_content)} characters
Stored with data_id: {store_data_id}
To retrieve this section later, use tool retrieve_stored_readable_web_section data_id: {store_data_id}

{extracted_content}"""

        return result_message

    except KeyError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error extracting section: {str(e)}"


@tool
def retrieve_stored_readable_web_section(data_id: str, runtime: ToolRuntime[HyperfocusContext, HyperfocusState]) -> str:
    """Retrieve a previously extracted markdown section by its data_id.

    Args:
        data_id: The data_id of the stored markdown section to retrieve

    Returns:
        The stored markdown content
    """
    try:
        if not data_exists(runtime, data_id):
            return f"Error: No data found with ID '{data_id}'."

        data = retrieve_data(runtime, data_id)
        return data

    except KeyError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error retrieving data: {str(e)}"


# LangChain tools list - all tools decorated with @tool
WEB_TOOLS = [
    readable_web_get,
    get_readable_web_section,
    retrieve_stored_readable_web_section
]
