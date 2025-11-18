"""Web scraping tools - unified data source architecture"""
from os import path
import os
import requests
import hashlib
import html2text
import tempfile
import re
from langchain.tools import tool, ToolRuntime
from mrkdwn_analysis import MarkdownAnalyzer
from datetime import datetime
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from bs4 import BeautifulSoup
from lxml import etree, html as lxml_html
from ripgrepy import Ripgrepy, RipGrepNotFound
from ..utils.html_utils import preprocess_html_for_schema, get_markdown_outline_from_html, create_dom_skeleton

from ..langchain_state import DataEntry, HyperfocusState, HyperfocusContext, data_exists, retrieve_data

@tool
def web_load_web_page(url: str, runtime: ToolRuntime) -> Command:
    """Load a web page and store it for multiple extraction methods.

    This is the unified entry point for web scraping. It fetches the HTML once
    and provides both structural overview (DOM skeleton + markdown outline) to help
    you decide which extraction method to use.

    After loading, you can use:
    - web_paged_markdown_find() - Semantic search through markdown with sub-agents
    - web_get_markdown_view() - Get full markdown conversion
    - web_extract_markdown_section() - Extract specific markdown section
    - web_extract_with_css() - Query with CSS selectors
    - web_extract_with_xpath() - Query with XPath expressions

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

        print(skeleton)
        print(markdown_outline)

        message = f"""✓ Loaded web page
Page ID: {page_id}
URL: {url}
HTML size: {len(response.text)} characters

DOM Skeleton (structural overview):
{skeleton}


Available extraction methods:
- web_get_markdown_view(page_id="{page_id}") - Full markdown conversion
- web_lookup_with_grep(page_id="{page_id}", query="...", context_lines=3) - Grep search on saved HTML
- web_extract_with_css(page_id="{page_id}", selector="...", extract_type="text|html|attrs")
- web_extract_with_xpath(page_id="{page_id}", xpath="...", extract_type="text|html|attrs")

Also available on disk as '{full_path}' for local file processing using grep or python scripts.
"""
# - web_extract_markdown_section(page_id="{page_id}", heading_query="...") - Specific section
# Markdown Outline (content headings):
# {markdown_outline}

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
def web_get_markdown_view(page_id: str, runtime: ToolRuntime) -> str:
    """Convert a loaded web page to markdown format. This is useful for finding strings
    or reasoning about content structure.

    This provides a readable, text-based view of the page content.
    The markdown is generated on-demand from the stored HTML.

    Args:
        page_id: The page ID from web_load_web_page

    Returns:
        Markdown-formatted content with heading structure
    """
    try:
        if not data_exists(runtime, page_id):
            return f"Error: No page found with ID '{page_id}'. Use web_load_web_page first."

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
web_extract_markdown_section(page_id="{page_id}", heading_query="heading text")
or
web_paged_markdown_find(page_id="{page_id}", lookup_prompt="your query here")
"""

    except Exception as e:
        return f"Error generating markdown view: {str(e)}"


# @tool
def web_extract_markdown_section(page_id: str, heading_query: str, runtime: ToolRuntime) -> str:
    """Extract a specific section from a loaded page's markdown view.

    Args:
        page_id: The page ID from web_load_web_page
        heading_query: The heading text to search for (case-insensitive, partial match)

    Returns:
        Markdown content from the matched heading to the next same-level heading
    """
    try:
        # Retrieve the stored page
        if not data_exists(runtime, page_id):
            return f"Error: No page found with ID '{page_id}'. Use web_load_web_page first."

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
def web_extract_with_css(page_id: str, selector: str, extract_type: str, runtime: ToolRuntime) -> str:
    """Extract data from a loaded page using CSS selectors.

    Use the DOM skeleton from web_load_web_page to design your selectors.

    Args:
        page_id: ID of the page from web_load_web_page
        selector: CSS selector query (e.g., "div.content h2", "#main-article")
        extract_type: What to extract - "text" (text content), "html" (outer HTML), or "attrs" (all attributes)

    Returns:
        Extracted data as text (may be JSON for attrs)
    """
    if not data_exists(runtime, page_id):
        return f"Error: No page found with ID '{page_id}'. Use web_load_web_page first."

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
def web_extract_with_xpath(page_id: str, xpath: str, extract_type: str, runtime: ToolRuntime) -> str:
    """Extract data from a loaded page using XPath queries.

    Use the markdown outline from web_load_web_page to find XPath expressions,
    or design your own based on the DOM skeleton.

    Args:
        page_id: ID of the page from web_load_web_page
        xpath: XPath query (e.g., "//div[@class='content']//h2", "//article[@id='main']")
        extract_type: What to extract - "markdown" (markdown content), "html" (outer HTML), or "attrs" (all attributes)

    Returns:
        Extracted data as a string
    """
    if not data_exists(runtime, page_id):
        return f"Error: No page found with ID '{page_id}'. Use web_load_web_page first."

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
            if extract_type == "markdown":
                html = etree.tostring(elem, encoding='unicode', method='html')

                # Convert to markdown
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.ignore_images = False
                h.ignore_emphasis = False
                h.unicode_snob = True
                h.body_width = 0  # Don't wrap lines

                markdown_content = h.handle(html)
                 
                results.append(f"[{i}] {markdown_content}")
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
def web_lookup_with_grep(
    runtime: ToolRuntime,
    query: str,
    page_id: str,
    context_lines: int = 3,
) -> str:
    """Perform a ripgrep search against stored HTML content with optional context.

    Args:
        query: Regular expression to search for
        page_id: The page ID from web_load_web_page
        context_lines: Number of lines to include before and after each match

    Returns:
        Matching lines (with context) from the HTML content
    """

    if context_lines < 0:
        return "Error: context_lines must be zero or greater."

    if not data_exists(runtime, page_id):
        return f"Error: No page found with ID '{page_id}'. Use web_load_web_page first."

    data = retrieve_data(runtime, page_id)
    if not isinstance(data, dict) or "content" not in data:
        return f"Error: '{page_id}' is not a valid page object."

    raw_html = data["content"]
    if not isinstance(raw_html, str):
        return f"Error: '{page_id}' does not contain HTML content."

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".html") as tmp:
            tmp.write(raw_html)
            temp_path = tmp.name

        rg = Ripgrepy(query, temp_path, rg_path="/usr/bin/rg")
        rg = rg.line_number().ignore_case()
        if context_lines > 0:
            rg = rg.context(context_lines)

        result = rg.run()
        output = (result.as_string or "").strip()

        if not output:
            return f"No matches found for query '{query}'."

        context_desc = "no context" if context_lines == 0 else f"±{context_lines} line(s) context"
        return (
            f"Found matches for '{query}' ({context_desc}):\n\n"
            f"{output}"
        )

    except re.error as exc:
        return f"Error: Invalid regular expression '{query}': {str(exc)}"
    except Exception as exc:
        return f"Error performing grep search: {str(exc)}"
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# @tool
def web_paged_markdown_find(
    page_id: str,
    lookup_prompt: str,
    runtime: ToolRuntime,
    chunk_size: int = 15000,
) -> Command:
    """Search through web page markdown content using chunked sub-agent processing.

    This tool converts a loaded web page to markdown, chunks it into manageable pieces,
    and runs a sub-agent task on each chunk sequentially to find relevant information.
    Use this when you need to perform semantic searches or complex queries across
    large web pages that exceed context limits.

    Args:
        page_id: The page ID from web_load_web_page
        lookup_prompt: Natural language prompt describing what to find (e.g., "Find all pricing information", "Extract product specifications")
        chunk_size: Size of each markdown chunk in characters (default: 15000)

    Returns:
        Command with aggregated results from all chunks

    Example:
        # First load a page
        web_load_web_page("https://example.com/docs")

        # Then search through it with a semantic query
        web_paged_markdown_find(
            page_id="page_abc123",
            lookup_prompt="Find all API endpoint descriptions and their parameters"
        )
    """
    from .task_tools import execute_task

    try:
        # 1. Validate page exists
        if not data_exists(runtime, page_id):
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=f"Error: No page found with ID '{page_id}'. Use web_load_web_page first.",
                        tool_call_id=runtime.tool_call_id
                    )
                ]
            })

        data = retrieve_data(runtime, page_id)
        if not isinstance(data, dict) or 'content' not in data:
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=f"Error: '{page_id}' is not a valid page object.",
                        tool_call_id=runtime.tool_call_id
                    )
                ]
            })

        raw_html = data["content"]
        if not isinstance(raw_html, str):
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=f"Error: '{page_id}' does not contain HTML content.",
                        tool_call_id=runtime.tool_call_id
                    )
                ]
            })

        # 2. Convert to markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.unicode_snob = True
        h.body_width = 0  # Don't wrap lines

        markdown_content = h.handle(raw_html)
        total_length = len(markdown_content)

        # 3. Chunk the markdown
        chunks = []
        current_pos = 0

        while current_pos < total_length:
            end_pos = min(current_pos + chunk_size, total_length)

            # Try to break at a newline to avoid cutting mid-sentence
            if end_pos < total_length:
                # Look back up to 200 chars for a newline
                newline_search_start = max(end_pos - 200, current_pos)
                newline_pos = markdown_content.rfind('\n', newline_search_start, end_pos)

                if newline_pos != -1 and newline_pos > current_pos:
                    end_pos = newline_pos + 1  # Include the newline

            chunk_text = markdown_content[current_pos:end_pos]
            chunks.append({
                'text': chunk_text,
                'start': current_pos,
                'end': end_pos,
                'size': len(chunk_text)
            })

            current_pos = end_pos

        num_chunks = len(chunks)
        url = data["metadata"].get("url", "unknown")

        # 4. Process each chunk sequentially with sub-agents
        all_results = []

        for i, chunk in enumerate(chunks):
            chunk_num = i + 1
            print(f"→ [Paged Find] Processing chunk {chunk_num}/{num_chunks} ({chunk['size']} chars)")

            # Build task prompt for this chunk
            task_prompt = f"""You are searching through a section of a web page (chunk {chunk_num} of {num_chunks}).

Your task: {lookup_prompt}

Instructions:
- Search through the content below carefully
- Extract any relevant information that matches the lookup task
- If you find nothing relevant, respond with "No relevant information found in this chunk"
- Do not make assumptions about what specific content means
- Be specific and include context when you find matches
- Format your findings clearly
"""

            try:
                # Execute task on this chunk
                chunk_result = execute_task(
                    runtime=runtime,
                    prompt=task_prompt,
                    data_text=chunk['text'],
                    enable_tools=False,  # No tools needed for simple search
                )

                print(f"→ [Paged Find] Chunk {chunk_num} result:\n{chunk_result}\n")

                all_results.append({
                    'chunk_num': chunk_num,
                    'result': chunk_result,
                    'char_range': f"{chunk['start']}-{chunk['end']}"
                })

            except Exception as e:
                all_results.append({
                    'chunk_num': chunk_num,
                    'result': f"Error processing chunk: {str(e)}",
                    'char_range': f"{chunk['start']}-{chunk['end']}"
                })

        # 5. Aggregate results
        results_text = []
        for res in all_results:
            # Filter out chunks that found nothing
            if "no relevant information found" not in res['result'].lower():
                results_text.append(
                    f"=== Chunk {res['chunk_num']} (chars {res['char_range']}) ===\n"
                    f"{res['result']}\n"
                )

        if not results_text:
            final_message = f"""✓ Paged markdown search completed
URL: {url}
Chunks processed: {num_chunks}
Total size: {total_length:,} characters

No relevant information found matching: "{lookup_prompt}"
"""
        else:
            final_message = f"""✓ Paged markdown search completed
URL: {url}
Chunks processed: {num_chunks}
Total size: {total_length:,} characters
Chunks with results: {len(results_text)}

Results:

{''.join(results_text)}"""

        return Command(update={
            "messages": [
                ToolMessage(
                    content=final_message,
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })

    except Exception as e:
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"Error in paged markdown find: {str(e)}",
                    tool_call_id=runtime.tool_call_id
                )
            ]
        })
    
# @tool
def web_download_html_and_return_structure(url: str, runtime: ToolRuntime) -> str:
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
    web_load_web_page,              # Main entry point - loads HTML once
    web_get_markdown_view,          # Markdown view of loaded page
    # web_extract_markdown_section,   # Extract specific markdown section
    # web_extract_with_css,           # Query with CSS selectors
    web_extract_with_xpath,         # Query with XPath expressions

    web_lookup_with_grep,           # Grep search on saved HTML file

    # Semantic search tools
    # web_paged_markdown_find,        # Chunked semantic search through markdown with sub-agents

    # Additional utility
    # web_download_html_and_return_structure  # Download to disk for script processing
]
