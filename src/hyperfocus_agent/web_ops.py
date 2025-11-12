import requests
import hashlib
from readability import Document
import html2text
from bs4 import BeautifulSoup, Tag
from lxml import etree, html as lxml_html
from mrkdwn_analysis import MarkdownAnalyzer

from .types import ChatCompletionToolParam
from .data_store import store_data, retrieve_data, data_exists


def readable_web_get(url: str) -> str:
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
        Message with headings list and data_id for extracting sections
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

    return f"""✓ Fetched and converted page to markdown
URL: {url}
Data ID: {data_id}
Markdown size: {len(markdown_content)} characters

Found {len(headers)} heading(s):
{headings_text}

To extract a specific section, use:
get_readable_web_section(data_id="{data_id}", heading_query="heading text to search for")

This will return the full content from that heading until the next heading of the same or higher level."""


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


def load_page_for_navigation(url: str, page_id: str | None = None) -> str:
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
    # Generate page_id if not provided
    if page_id is None:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        page_id = f"page_{url_hash}"

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

    # Parse with BeautifulSoup
    soup = BeautifulSoup(response.text, 'lxml')

    # Store the soup object for later queries
    store_data(
        data_id=page_id,
        content=soup,
        data_type="soup",
        metadata={"url": url, "html_size": len(response.text)}
    )

    # Generate a skeleton for the LLM to reason about
    skeleton_id = f"{page_id}_skeleton"

    # We'll reuse the skeleton generation logic inline here for efficiency
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

    def traverse(element: Tag, depth: int = 0, prefix: str = "", max_depth: int = 10) -> None:
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
            traverse(child, depth + 1, child_prefix, max_depth)

    traverse(soup.html if soup.html else soup)
    skeleton = "\n".join(lines)

    print(skeleton)

    # Store skeleton as text
    store_data(
        data_id=skeleton_id,
        content=skeleton,
        data_type="text",
        metadata={"url": url, "parent_page_id": page_id}
    )

    return f"""✓ Loaded page into memory
Page ID: {page_id}
URL: {url}
HTML size: {len(response.text)} characters

DOM Skeleton (use this to design your CSS/XPath queries):
{skeleton}

To extract data from this page, use:
- extract_with_css(page_id="{page_id}", selector="your css selector")
- extract_with_xpath(page_id="{page_id}", xpath="your xpath query")
"""


def extract_with_css(page_id: str, selector: str, extract_type: str = "text") -> str:
    """
    Extract data from a stored page using a CSS selector.

    Args:
        page_id: ID of the page stored with load_page_for_navigation
        selector: CSS selector query (e.g., "div.content h2", "#main-article")
        extract_type: What to extract - "text" (text content), "html" (outer HTML), or "attrs" (all attributes)

    Returns:
        Extracted data as text (may be JSON for attrs)
    """
    if not data_exists(page_id):
        return f"Error: No page found with ID '{page_id}'. Use load_page_for_navigation first."

    soup = retrieve_data(page_id)

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


def extract_with_xpath(page_id: str, xpath: str, extract_type: str = "text") -> str:
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
    if not data_exists(page_id):
        return f"Error: No page found with ID '{page_id}'. Use load_page_for_navigation first."

    soup = retrieve_data(page_id)

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


# def raw_web_get(url: str) -> str:
#     """Fetch and return the raw content of a web page."""
#     response = requests.get(url)
#     response.raise_for_status()
#     return response.text

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
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "load_page_for_navigation",
    #         "description": "Fetches a web page and returns a hyper-condensed DOM tree skeleton overview. This shows the hierarchical structure with element tags, IDs, classes, heading text (h1-h6), and child counts. Use this to understand page structure before designing XPath or CSS selector queries for targeted data extraction. The skeleton is compact and designed for reasoning about DOM navigation strategies.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "url": {
    #                     "type": "string",
    #                     "description": "The URL of the web page to load"
    #                 },
    #                 "page_id": {
    #                     "type": "string",
    #                     "description": "Optional identifier for this page. If not provided, one will be generated automatically."
    #                 }
    #             },
    #             "required": ["url"]
    #         }
    #     }
    # },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "extract_with_css",
    #         "description": "Extract data from a previously loaded page using CSS selectors. The page must first be loaded with load_page_for_navigation. This allows precise extraction of specific elements based on the DOM skeleton.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "page_id": {
    #                     "type": "string",
    #                     "description": "ID of the page loaded with load_page_for_navigation"
    #                 },
    #                 "selector": {
    #                     "type": "string",
    #                     "description": "CSS selector query (e.g., 'div.content h2', '#main-article', 'tr.athing td.title a')"
    #                 },
    #                 "extract_type": {
    #                     "type": "string",
    #                     "enum": ["text", "html", "attrs"],
    #                     "description": "What to extract: 'text' for text content (default), 'html' for full HTML, 'attrs' for all attributes"
    #                 }
    #             },
    #             "required": ["page_id", "selector"]
    #         }
    #     }
    # },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "extract_with_xpath",
    #         "description": "Extract data from a previously loaded page using XPath queries. The page must first be loaded with load_page_for_navigation. XPath provides more powerful querying capabilities than CSS selectors.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "page_id": {
    #                     "type": "string",
    #                     "description": "ID of the page loaded with load_page_for_navigation"
    #                 },
    #                 "xpath": {
    #                     "type": "string",
    #                     "description": "XPath query (e.g., '//div[@class=\"content\"]//h2', '//article[@id=\"main\"]//p')"
    #                 },
    #                 "extract_type": {
    #                     "type": "string",
    #                     "enum": ["text", "html"],
    #                     "description": "What to extract: 'text' for text content (default) or 'html' for full HTML"
    #                 }
    #             },
    #             "required": ["page_id", "xpath"]
    #         }
    #     }
    # },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "raw_web_get",
    #         "description": "Fetches and returns the raw content of a web page. Do not use this function unless the user specifically requests raw HTML content, or wants to act upon the HTML structure of a page.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "url": {
    #                     "type": "string",
    #                     "description": "The URL of the web page to fetch"
    #                 }
    #             },
    #             "required": ["url"]
    #         }
    #     }
    # }
]