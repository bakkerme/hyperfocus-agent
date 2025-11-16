"""Web scraping tools"""
import requests
import hashlib
import html2text
from langchain.tools import tool, ToolRuntime
from mrkdwn_analysis import MarkdownAnalyzer
from datetime import datetime
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from bs4 import BeautifulSoup, Tag
from lxml import etree, html as lxml_html

from ..langchain_state import DataEntry, HyperfocusState, HyperfocusContext, data_exists, retrieve_data


def create_dom_skeleton(html_content: str, max_depth: int = 10) -> tuple[BeautifulSoup, str]:
    """
    Parse HTML and generate a DOM skeleton for reasoning about structure.
    
    Args:
        html_content: Raw HTML string to parse
        max_depth: Maximum depth to traverse in the DOM tree
        
    Returns:
        Tuple of (BeautifulSoup object, skeleton string)
    """
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Generate skeleton
    lines = []

    def get_element_signature(tag: Tag) -> str:
        sig = tag.name
        if tag.get('id'):
            sig += f"#{tag.get('id')}"
        classes = tag.get('class')
        if classes and isinstance(classes, list):
            class_str = '.'.join(classes[:2])
            sig += f".{class_str}"
            if len(classes) > 2:
                sig += f"(+{len(classes)-2})"
        notable_attrs = []
        for attr in ['data-testid', 'data-id', 'role', 'aria-label']:
            if tag.get(attr):
                notable_attrs.append(f"{attr}=\"{tag.get(attr)}\"")
        if notable_attrs:
            sig += f" [{', '.join(notable_attrs[:2])}]"
        return sig

    def traverse(element: Tag, depth: int = 0, prefix: str = "") -> None:
        if depth > max_depth:
            return
        if element.name in ['script', 'style', 'meta', 'link', 'noscript']:
            return
        sig = get_element_signature(element)
        children = [
            child for child in element.children
            if isinstance(child, Tag) and child.name not in ['script', 'style', 'meta', 'link', 'noscript']
        ]
        child_count = len(children)
        indent = "  " * depth
        line = f"{indent}{prefix}{sig}"
        if child_count > 0:
            line += f" ({child_count} children)"
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            heading_text = element.get_text(strip=True)[:80]
            if heading_text:
                line += f' → "{heading_text}"'
        lines.append(line)
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            child_prefix = "└── " if is_last else "├── "
            traverse(child, depth + 1, child_prefix)

    traverse(soup.html if soup.html else soup)
    skeleton = "\n".join(lines)
    
    return soup, skeleton

@tool
def readable_web_get(url: str, runtime: ToolRuntime) -> Command:
    """Fetch and store a web page as markdown.

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

The full content is too large to display here.
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
    """Extract a section of markdown content by providing the heading.

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

        data = retrieve_data(runtime, data_id)
        if not isinstance(data, dict) or 'content' not in data:
            return f"Error: '{data_id}' is not markdown text."

        markdown_text = data["content"]

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

        result_message = f"""✓ Extracted section: {matched_heading['text']}
Level: {matched_heading['level']}
Lines: {start_line} to {end_line if end_line else 'end'}
Content length: {len(extracted_content)} characters

{extracted_content}"""

        return result_message

    except KeyError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error extracting section: {str(e)}"

# @tool
# def retrieve_stored_readable_web_section(data_id: str, runtime: ToolRuntime[HyperfocusContext, HyperfocusState]) -> str:
#     """Retrieve a previously extracted markdown section by its data_id.

#     Args:
#         data_id: The data_id of the stored markdown section to retrieve

#     Returns:
#         The stored markdown content
#     """
#     try:
#         if not data_exists(runtime, data_id):
#             return f"Error: No data found with ID '{data_id}'."

#         data = retrieve_data(runtime, data_id)
#         if not isinstance(data, dict) or 'content' not in data:
#             return f"Error: Data with ID '{data_id}' is not valid."

#         return data["content"]

#     except KeyError as e:
#         return f"Error: {str(e)}"
#     except Exception as e:
#         return f"Error retrieving data: {str(e)}"

def get_readable_web_section(data_id: str, heading_query: str) -> str:
    """
    Extract a section of markdown content based on a heading query.

    Finds the heading that matches the query (case-insensitive) and extracts
    all content from that heading until the next heading of the same or higher level.

    Args:
        data_id: The data ID from readable_web_get
        heading_query: The heading text to search for (case-insensitive, partial match)

    Returns:
        The markdown content from the matched heading to the next same-level heading

    Raises:
        ValueError: If data_id not found or no matching heading found
    """
    # Retrieve the stored markdown
    if not data_exists(data_id):
        return f"Error: No data found with ID '{data_id}'. Use readable_web_get first."

    markdown_text = retrieve_data(data_id)

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
        return f"Error: No heading found matching '{heading_query}'.\n\nAvailable headings:\n{available_headings}"

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

    return f"""✓ Extracted section: {matched_heading['text']}
Level: {matched_heading['level']}
Lines: {start_line} to {end_line if end_line else 'end'}
Content length: {len(extracted_content)} characters

{extracted_content}"""


@tool
def load_page_for_navigation(url: str, runtime: ToolRuntime) -> Command:
    """
    Fetch a web page and store it in memory for subsequent navigation and extraction.

    This function fetches a page, parses it with BeautifulSoup, generates a DOM skeleton,
    and stores both the skeleton and the parsed page for later XPath/CSS queries.

    Args:
        url: The URL to fetch
        page_id: Optional identifier for this page. If not provided, generates one from URL hash.

    Returns:
        A message with the page_id and DOM skeleton for reasoning about extraction
    """
    page_id = f"page_{hashlib.md5(url.encode()).hexdigest()[:8]}"

    # Fetch the page
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    # Fix encoding issues - requests often defaults to ISO-8859-1 when it shouldn't
    # If encoding is the default fallback, try apparent_encoding (chardet-based)
    if response.encoding and response.encoding.lower() in ['iso-8859-1', 'latin-1', 'windows-1252']:
        # These are fallback encodings, trust chardet's detection instead
        detected_encoding = response.apparent_encoding
        if detected_encoding:
            response.encoding = detected_encoding

    # Parse HTML and generate DOM skeleton
    soup, skeleton = create_dom_skeleton(response.text)
    skeleton_id = f"{page_id}_skeleton"

    print(skeleton)

    message = f"""✓ Loaded page into memory
Page ID: {page_id}
URL: {url}
HTML size: {len(response.text)} characters

DOM Skeleton (use this to design your CSS/XPath queries):
{skeleton}

To extract data from this page, use:
- extract_with_css(page_id="{page_id}", selector="your css selector")
- extract_with_xpath(page_id="{page_id}", xpath="your xpath query")
"""
    return Command(update={
        "stored_data": {
            page_id: {
                "data_id": page_id,
                "data_type": "soup",
                "content": soup,
                "created_at": datetime.now().isoformat(),
                "metadata": {"url": url, "html_size": len(response.text)}
            },
            skeleton_id: {
                "data_id": skeleton_id,
                "data_type": "text",
                "content": skeleton,
                "created_at": datetime.now().isoformat(),
                "metadata": {"url": url, "parent_page_id": page_id}
            }
        },
        "messages": [
            ToolMessage(
                content=message,
                tool_call_id=runtime.tool_call_id
            )
        ]
    })


@tool
def extract_with_css(page_id: str, selector: str, extract_type: str, runtime: ToolRuntime) -> str:
    """
    Extract data from a stored page using a CSS selector.

    Args:
        page_id: ID of the page stored with load_page_for_navigation
        selector: CSS selector query (e.g., "div.content h2", "#main-article")
        extract_type: What to extract - "text" (text content), "html" (outer HTML), or "attrs" (all attributes)

    Returns:
        Extracted data as text (may be JSON for attrs)
    """
    if not data_exists(runtime, page_id):
        return f"Error: No page found with ID '{page_id}'. Use load_page_for_navigation first."

    data = retrieve_data(runtime, page_id)
    if not isinstance(data, dict) or "content" not in data:
        return f"Error: '{page_id}' is not a valid page object."
    soup = data["content"]

    if not isinstance(soup, BeautifulSoup):
        return f"Error: '{page_id}' is not a BeautifulSoup page object."

    # Find elements matching the selector
    elements = soup.select(selector)

    if not elements:
        return f"No elements found matching selector: {selector}"

    results = []
    for i, elem in enumerate(elements):
        if extract_type == "text":
            # Use separator to preserve spaces between elements
            text = elem.get_text(separator=" ", strip=True)
            results.append(f"[{i}] {text}")
        elif extract_type == "html":
            results.append(f"[{i}] {str(elem)}")
        elif extract_type == "attrs":
            attrs = dict(elem.attrs)
            results.append(f"[{i}] {attrs}")
        else:
            return f"Error: Unknown extract_type '{extract_type}'. Use 'text', 'html', or 'attrs'."

    result_text = "\n".join(results)
    return f"Found {len(elements)} element(s) matching '{selector}':\n\n{result_text}"


@tool
def extract_with_xpath(page_id: str, xpath: str, extract_type: str, runtime: ToolRuntime) -> str:
    """
    Extract data from a stored page using an XPath query.

    Note: BeautifulSoup uses CSS selectors internally, so complex XPath may not work.
    For full XPath support, this uses lxml's xpath capabilities.

    Args:
        page_id: ID of the page stored with load_page_for_navigation
        xpath: XPath query (e.g., "//div[@class='content']//h2", "//article[@id='main']")
        extract_type: What to extract - "text" (text content) or "html" (outer HTML)

    Returns:
        Extracted data as text
    """
    if not data_exists(runtime, page_id):
        return f"Error: No page found with ID '{page_id}'. Use load_page_for_navigation first."

    data = retrieve_data(runtime, page_id)
    if not isinstance(data, dict) or "content" not in data:
        return f"Error: '{page_id}' is not a valid page object."
    soup = data["content"]

    if not isinstance(soup, BeautifulSoup):
        return f"Error: '{page_id}' is not a BeautifulSoup page object."

    # Convert to lxml for XPath support
    try:

        # Convert soup to lxml, preserving encoding
        html_string = str(soup)
        # Parse with proper encoding
        tree = lxml_html.fromstring(html_string)

        # Execute XPath
        elements = tree.xpath(xpath)

        if not elements:
            return f"No elements found matching XPath: {xpath}"

        results = []
        for i, elem in enumerate(elements):
            if extract_type == "text":
                # Get text content with proper spacing between block elements
                if hasattr(elem, 'itertext'):
                    # itertext() yields text from all text nodes
                    # Join with spaces to ensure separation between elements
                    text_parts = [t.strip() for t in elem.itertext() if t.strip()]
                    text = ' '.join(text_parts)
                elif hasattr(elem, 'text_content'):
                    # Fallback: normalize whitespace
                    text = ' '.join(elem.text_content().split())
                else:
                    text = str(elem).strip()
                results.append(f"[{i}] {text}")
            elif extract_type == "html":
                html_str = etree.tostring(elem, encoding='unicode', method='html')
                results.append(f"[{i}] {html_str}")
            else:
                return f"Error: Unknown extract_type '{extract_type}'. Use 'text' or 'html'."

        result_text = "\n".join(results)
        return f"Found {len(elements)} element(s) matching '{xpath}':\n\n{result_text}"

    except Exception as e:
        return f"Error executing XPath query: {str(e)}"

@tool
def download_html_and_return_structure(url: str, runtime: ToolRuntime) -> str:
    """
    Fetch a web page and stores it to disk, presenting a DOM structure overview. 

    Args:
        url: The URL to fetch

    Returns:
        Path of the html file and DOM skeleton for reasoning about extraction
    """
    page_id = f"page_{hashlib.md5(url.encode()).hexdigest()[:8]}"

    # Fetch the page
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    # Fix encoding issues - requests often defaults to ISO-8859-1 when it shouldn't
    # If encoding is the default fallback, try apparent_encoding (chardet-based)
    if response.encoding and response.encoding.lower() in ['iso-8859-1', 'latin-1', 'windows-1252']:
        # These are fallback encodings, trust chardet's detection instead
        detected_encoding = response.apparent_encoding
        if detected_encoding:
            response.encoding = detected_encoding

    # Save the HTML content to a file
    file_path = f"{page_id}.html"
    with open(file_path, 'w', encoding=response.encoding) as f:
        f.write(response.text)

    # Parse HTML and generate DOM skeleton
    _, skeleton = create_dom_skeleton(response.text)

    print(skeleton)

    message = f"""✓ Page downloaded and stored as {file_path}
HTML size: {len(response.text)} characters

DOM Skeleton
{skeleton}

You may now operate on the file on disk at path '{file_path}' using your local tools, including create_python_script.
"""
    return message




# LangChain tools list - all tools decorated with @tool
WEB_TOOLS = [
    # readable_web_get,
    # get_readable_web_section,
    # retrieve_stored_readable_web_section
    # load_page_for_navigation,
    # extract_with_css,
    # extract_with_xpath,
    download_html_and_return_structure
]
