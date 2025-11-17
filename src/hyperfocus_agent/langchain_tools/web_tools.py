"""Web scraping tools - unified data source architecture"""
from os import path
import requests
import hashlib
import html2text
from langchain.tools import tool, ToolRuntime
from mrkdwn_analysis import MarkdownAnalyzer
from datetime import datetime
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from bs4 import BeautifulSoup
from lxml import etree, html as lxml_html
from ..utils.html_utils import preprocess_html_for_schema, get_markdown_outline_from_html, create_dom_skeleton

from ..langchain_state import DataEntry, HyperfocusState, HyperfocusContext, data_exists, retrieve_data

@tool
def load_web_page(url: str, runtime: ToolRuntime) -> Command:
    """Load a web page and store it for multiple extraction methods.

    This is the unified entry point for web scraping. It fetches the HTML once
    and provides both structural overview (DOM skeleton + markdown outline) to help
    you decide which extraction method to use.

    After loading, you can use:
    - get_markdown_view() - Get full markdown conversion
    - extract_markdown_section() - Extract specific markdown section
    - extract_with_css() - Query with CSS selectors
    - extract_with_xpath() - Query with XPath expressions

    Args:
        url: The URL to fetch

    Returns:
        Page ID, DOM skeleton, and markdown outline for reasoning about extraction
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

        # Step 2: Parse HTML and create DOM skeleton
        soup, skeleton = create_dom_skeleton(response.text)

        # Step 3: Get markdown outline (headings with XPath references)
        markdown_outline = get_markdown_outline_from_html(response.text)

        # Step 4: Store the parsed page (raw HTML only - parse on demand to avoid serialization issues)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        page_id = f"page_{url_hash}"


        # write html direct to disk to allow for grep use
        cwd = path.abspath(path.curdir)
        full_path = f"{cwd}/{page_id}.html"
        with open(full_path, "w", encoding=response.encoding) as f:
            f.write(response.text)
        


        page_entry: DataEntry = {
            "data_id": page_id,
            "data_type": "html_page",
            "content": response.text,  # Store only raw HTML - BeautifulSoup is not serializable
            "created_at": datetime.now().isoformat(),
            "metadata": {
                "url": url,
                "html_size": len(response.text),
                "encoding": response.encoding,
                "skeleton": skeleton,
                "markdown_outline": markdown_outline
            }
        }

        message = f"""✓ Loaded web page
Page ID: {page_id}
URL: {url}
HTML size: {len(response.text)} characters

DOM Skeleton (structural overview):
{skeleton}

Markdown Outline (content headings):
{markdown_outline}

Available extraction methods:
- get_markdown_view(page_id="{page_id}") - Full markdown conversion
- extract_markdown_section(page_id="{page_id}", heading_query="...") - Specific section
- extract_with_css(page_id="{page_id}", selector="...", extract_type="text|html|attrs")
- extract_with_xpath(page_id="{page_id}", xpath="...", extract_type="text|html|attrs")

Also available on disk as '{full_path}' for local file processing using grep or python scripts.
"""

        return Command(update={
            "stored_data": {page_id: page_entry},
            "messages": [
                ToolMessage(
                    content=message,
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
def get_markdown_view(page_id: str, runtime: ToolRuntime) -> str:
    """Convert a loaded web page to markdown format.

    This provides a readable, text-based view of the page content.
    The markdown is generated on-demand from the stored HTML.

    Args:
        page_id: The page ID from load_web_page

    Returns:
        Markdown-formatted content with heading structure
    """
    try:
        if not data_exists(runtime, page_id):
            return f"Error: No page found with ID '{page_id}'. Use load_web_page first."

        data = retrieve_data(runtime, page_id)
        if not isinstance(data, dict) or 'content' not in data:
            return f"Error: '{page_id}' is not a valid page object."

        raw_html = data["content"]

        if not isinstance(raw_html, str):
            return f"Error: '{page_id}' does not contain HTML content."

        # Convert to markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.unicode_snob = True
        h.body_width = 0  # Don't wrap lines

        markdown_content = h.handle(raw_html)

        # Extract headings from markdown
        doc = MarkdownAnalyzer.from_string(markdown_content)
        headers_dict = doc.identify_headers()
        headers_list = headers_dict.get('Header', [])

        # Format headings for display
        heading_lines = []
        for heading in headers_list[:20]:  # Show first 20 headings
            indent = "  " * (heading['level'] - 1)
            heading_lines.append(f"{indent}{'#' * heading['level']} {heading['text']} (line {heading['line']})")

        headings_text = "\n".join(heading_lines) if heading_lines else "(No headings found)"
        if len(headers_list) > 20:
            headings_text += f"\n  ... and {len(headers_list) - 20} more headings"

        url = data["metadata"].get("url", "unknown")

        if len(markdown_content) > 10000:
            markdown_content = markdown_content[:10000] + "\n\n...(truncated due to max length)..."

        return f"""✓ Markdown view of {url}
Size: {len(markdown_content)} characters

Headings structure:
{headings_text}

Full markdown content:
{markdown_content}

To extract a specific section, use:
extract_markdown_section(page_id="{page_id}", heading_query="heading text")"""

    except Exception as e:
        return f"Error generating markdown view: {str(e)}"


@tool
def extract_markdown_section(page_id: str, heading_query: str, runtime: ToolRuntime) -> str:
    """Extract a specific section from a loaded page's markdown view.

    Args:
        page_id: The page ID from load_web_page
        heading_query: The heading text to search for (case-insensitive, partial match)

    Returns:
        Markdown content from the matched heading to the next same-level heading
    """
    try:
        # Retrieve the stored page
        if not data_exists(runtime, page_id):
            return f"Error: No page found with ID '{page_id}'. Use load_web_page first."

        data = retrieve_data(runtime, page_id)
        if not isinstance(data, dict) or 'content' not in data:
            return f"Error: '{page_id}' is not a valid page object."

        raw_html = data["content"]

        if not isinstance(raw_html, str):
            return f"Error: '{page_id}' does not contain HTML content."

        # Convert to markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.unicode_snob = True
        h.body_width = 0  # Don't wrap lines

        markdown_text = h.handle(raw_html)

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
            extracted_lines = lines[start_line - 1:end_line - 1]
        else:
            extracted_lines = lines[start_line - 1:]

        extracted_content = '\n'.join(extracted_lines)

        result_message = f"""✓ Extracted section: {matched_heading['text']}
Level: {matched_heading['level']}
Lines: {start_line} to {end_line if end_line else 'end'}
Content length: {len(extracted_content)} characters

{extracted_content}"""

        return result_message

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



# @tool
def extract_with_css(page_id: str, selector: str, extract_type: str, runtime: ToolRuntime) -> str:
    """Extract data from a loaded page using CSS selectors.

    Use the DOM skeleton from load_web_page to design your selectors.

    Args:
        page_id: ID of the page from load_web_page
        selector: CSS selector query (e.g., "div.content h2", "#main-article")
        extract_type: What to extract - "text" (text content), "html" (outer HTML), or "attrs" (all attributes)

    Returns:
        Extracted data as text (may be JSON for attrs)
    """
    if not data_exists(runtime, page_id):
        return f"Error: No page found with ID '{page_id}'. Use load_web_page first."

    data = retrieve_data(runtime, page_id)
    if not isinstance(data, dict) or "content" not in data:
        return f"Error: '{page_id}' is not a valid page object."

    raw_html = data["content"]

    if not isinstance(raw_html, str):
        return f"Error: '{page_id}' does not contain HTML content."

    # Parse HTML on-demand with BeautifulSoup
    soup = BeautifulSoup(raw_html, 'lxml')

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
    """Extract data from a loaded page using XPath queries.

    Use the markdown outline from load_web_page to find XPath expressions,
    or design your own based on the DOM skeleton.

    Args:
        page_id: ID of the page from load_web_page
        xpath: XPath query (e.g., "//div[@class='content']//h2", "//article[@id='main']")
        extract_type: What to extract - "text" (text content), "html" (outer HTML), or "attrs" (all attributes)

    Returns:
        Extracted data as text
    """
    if not data_exists(runtime, page_id):
        return f"Error: No page found with ID '{page_id}'. Use load_web_page first."

    data = retrieve_data(runtime, page_id)
    if not isinstance(data, dict) or "content" not in data:
        return f"Error: '{page_id}' is not a valid page object."

    raw_html = data["content"]

    if not isinstance(raw_html, str):
        return f"Error: '{page_id}' does not contain HTML content."

    # Parse with lxml for full XPath support
    try:
        tree = lxml_html.fromstring(raw_html)

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
            elif extract_type == "attrs":
                if hasattr(elem, 'attrib'):
                    attrs = dict(elem.attrib)
                    results.append(f"[{i}] {attrs}")
                else:
                    results.append(f"[{i}] (no attributes)")
            else:
                return f"Error: Unknown extract_type '{extract_type}'. Use 'text', 'html', or 'attrs'."

        result_text = "\n".join(results)
        return f"Found {len(elements)} element(s) matching '{xpath}':\n\n{result_text}"

    except Exception as e:
        return f"Error executing XPath query: {str(e)}"

@tool
def lookup_with_grep(query: str, page_id: str, runtime: ToolRuntime) -> str:
    """Perform a grep search on the web page HTML file.

    This allows for quick text-based searches using regular expressions.

    Args:
        query: The grep query (regular expression)
        page_id: The page ID from load_web_page
    Returns:
        Matching lines from the HTML file
    """
    file_path = f"{page_id}.html"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        import re
        pattern = re.compile(query, re.IGNORECASE)

        matches = []
        for i, line in enumerate(lines):
            if pattern.search(line):
                matches.append(f"[{i+1}] {line.strip()}")

        if not matches:
            return f"No matches found for query: {query}"

        result_text = "\n".join(matches)
        return f"Found {len(matches)} matching line(s) for query '{query}':\n\n{result_text}"

    except FileNotFoundError:
        return f"Error: HTML file '{file_path}' not found. Ensure the page has been loaded."
    except re.error as e:
        return f"Error: Invalid regular expression '{query}': {str(e)}"
    except Exception as e:
        return f"Error performing grep search: {str(e)}"
    
# @tool
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

    html = preprocess_html_for_schema(response.text)

    # Save the HTML content to a file
    file_path = f"{page_id}.html"
    with open(file_path, 'w', encoding=response.encoding) as f:
        f.write(response.text)

    # Parse HTML and generate DOM skeleton
    # _, skeleton = create_dom_skeleton(response.text)
    # print(skeleton)

    markdown_outline = get_markdown_outline_from_html(response.text)
    print(markdown_outline)

    message = f"""✓ Page downloaded and stored as {file_path}
HTML size: {len(response.text)} characters

Document Outline in Markdown:
{markdown_outline}

You may now operate on the file on disk at path '{file_path}' using your local tools, including create_python_script.
"""
# DOM Skeleton
# {skeleton}
    return message

# LangChain tools list - all tools decorated with @tool
WEB_TOOLS = [
    # Unified web scraping architecture
    load_web_page,              # Main entry point - loads HTML once
    get_markdown_view,          # Markdown view of loaded page
    extract_markdown_section,   # Extract specific markdown section
    # extract_with_css,           # Query with CSS selectors
    extract_with_xpath,         # Query with XPath expressions

    # Additional utility
    # download_html_and_return_structure  # Download to disk for script processing
]
