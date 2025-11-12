import requests
import hashlib
from readability import Document
import html2text
from bs4 import BeautifulSoup, Tag
from mrkdwn_analysis import MarkdownAnalyzer

from .types import ChatCompletionToolParam, ToolResult
from .data_store import get_data_info, store_data, retrieve_data, data_exists


def readable_web_get(url: str) -> ToolResult:
    """
    Fetch and return the content of a web page in an LLM-readable format.

    Pipeline:
    1. Fetch raw HTML with requests
    2. Convert HTML to clean markdown with html2text
    3. Extract headings from markdown
    4. Store full markdown in data store
    5. Return only headings with data_id for subsequent section extraction

    Args:
        url: The URL to fetch

    Returns:
        ToolResult with headings list and data_id for extracting sections
    """
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
    headers = headers_dict.get('Header', [])

    # Step 4: Store markdown in data store
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    data_id = f"markdown_{url_hash}"

    store_data(
        data_id=data_id,
        content=markdown_content,
        data_type="markdown",
        metadata={"url": url, "size": len(markdown_content)}
    )

    # Step 5: Format headings for display
    heading_lines = []
    for heading in headers:
        indent = "  " * (heading['level'] - 1)
        heading_lines.append(f"{indent}{'#' * heading['level']} {heading['text']} (line {heading['line']})")

    headings_text = "\n".join(heading_lines) if heading_lines else "(No headings found)"

    message = f"""✓ Fetched and converted page to markdown
URL: {url}
Data ID: {data_id}
Markdown size: {len(markdown_content)} characters

Found {len(headers)} heading(s):
{headings_text}

To extract a specific section, use:
get_readable_web_section(data_id="{data_id}", heading_query="heading text to search for")

This will return the full content from that heading until the next heading of the same or higher level."""

    return {
        "data": message,
        "include_in_context": True
    }


def get_readable_web_section(data_id: str, heading_query: str) -> ToolResult:
    """
    Extract a section of markdown content based on a heading query.

    Finds the heading that matches the query (case-insensitive) and extracts
    all content from that heading until the next heading of the same or higher level.

    Args:
        data_id: The data ID from readable_web_get
        heading_query: The heading text to search for (case-insensitive, partial match)

    Returns:
        ToolResult with the markdown content from the matched heading to the next same-level heading

    Raises:
        ValueError: If data_id not found or no matching heading found
    """
    # Retrieve the stored markdown
    if not data_exists(data_id):
        return {
            "data": f"Error: No data found with ID '{data_id}'. Use readable_web_get first.",
            "include_in_context": True
        }

    markdown_text = retrieve_data(data_id)

    if not isinstance(markdown_text, str):
        return {
            "data": f"Error: '{data_id}' is not markdown text.",
            "include_in_context": True
        }

    # Extract all headings
    doc = MarkdownAnalyzer.from_string(markdown_text)
    headers_dict = doc.identify_headers()
    headers = headers_dict.get('Header', [])

    if not headers:
        return {
            "data": "Error: No headings found in markdown content",
            "include_in_context": True
        }

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
        return {
            "data": error_msg,
            "include_in_context": True
        }

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


    metadata = get_data_info(data_id)

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

    return {
        "data": result_message,
        "include_in_context": False,
        "stub_message": f"[Web section '{matched_heading['text']}' extracted - stored as {store_data_id}]",
        "context_guidance": f"""Why excluded: The extracted markdown section is large and has been stored for efficient access.

How to retrieve: Use retrieve_stored_readable_web_section(data_id="{store_data_id}") to get the full content again."""
    }

def retrieve_stored_readable_web_section(data_id: str) -> ToolResult:
    data = retrieve_data(data_id)
    return {
            "data": data,
            "include_in_context": False,
            "stub_message": f"[Previously extracted web section retrieved - data_id: {data_id}]",
            "context_guidance": f"""Why excluded: The extracted markdown section is large and has been stored for efficient access.

    How to retrieve: Use retrieve_stored_readable_web_section(data_id="{data_id}") to get the full content again."""
        }

WEB_TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "readable_web_get",
            "description": "Fetches a web page, converts it to markdown, extracts headings, and stores the full markdown for later extraction. Returns a list of headings and a data_id. Use this as the first step when extracting information from a web page. Then use get_readable_web_section to extract specific sections by heading.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the web page to fetch"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_readable_web_section",
            "description": "Extract a specific section from previously fetched markdown content. Searches for a heading (case-insensitive partial match) and returns all content from that heading until the next heading of the same or higher level. Must be used after readable_web_get.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_id": {
                        "type": "string",
                        "description": "The data_id returned from readable_web_get"
                    },
                    "heading_query": {
                        "type": "string",
                        "description": "The heading text to search for (case-insensitive, supports partial matches)"
                    }
                },
                "required": ["data_id", "heading_query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_stored_readable_web_section",
            "description": "Retrieve a previously extracted markdown section by its data_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_id": {
                        "type": "string",
                        "description": "The data_id of the stored markdown section to retrieve"
                    }
                },
                "required": ["data_id"]
            }
        }
    }
]