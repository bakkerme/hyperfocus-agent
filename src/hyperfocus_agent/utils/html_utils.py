import html2text
import xxhash
from bs4 import BeautifulSoup, Tag
from mrkdwn_analysis import MarkdownAnalyzer
from lxml import etree, html as lhtml

def preprocess_html_for_schema(html_content, text_threshold=100, attr_value_threshold=200):
    """
    Preprocess HTML to reduce size while preserving structure for schema generation.
    
    Args:
        html_content (str): Raw HTML content
        text_threshold (int): Maximum length for text nodes before truncation
        attr_value_threshold (int): Maximum length for attribute values before truncation
        
    Returns:
        str: Preprocessed HTML content
    """
    try:
        # Parse HTML with error recovery
        parser = etree.HTMLParser(remove_comments=True, remove_blank_text=True)
        tree = lhtml.fromstring(html_content, parser=parser)
        
        # 1. Remove HEAD section (keep only BODY)
        head_elements = tree.xpath('//head')
        for head in head_elements:
            if head.getparent() is not None:
                head.getparent().remove(head)
        
        # 2. Define tags to remove completely
        tags_to_remove = [
            'script', 'style', 'noscript', 'iframe', 'canvas', 'svg',
            'video', 'audio', 'source', 'track', 'map', 'area'
        ]
        
        # Remove unwanted elements
        for tag in tags_to_remove:
            elements = tree.xpath(f'//{tag}')
            for element in elements:
                if element.getparent() is not None:
                    element.getparent().remove(element)
        
        # 3. Process remaining elements to clean attributes and truncate text
        for element in tree.iter():
            # Skip if we're at the root level
            if element.getparent() is None:
                continue
                
            # Clean non-essential attributes but preserve structural ones
            # attribs_to_keep = {'id', 'class', 'name', 'href', 'src', 'type', 'value', 'data-'}

            # This is more aggressive than the previous version
            attribs_to_keep = {'id', 'class', 'name', 'type', 'value'}

            # attributes_hates_truncate = ['id', 'class', "data-"]

            # This means, I don't care, if an attribute is too long, truncate it, go and find a better css selector to build a schema
            attributes_hates_truncate = []
            
            # Process each attribute
            for attrib in list(element.attrib.keys()):
                # Keep if it's essential or starts with data-
                if not (attrib in attribs_to_keep or attrib.startswith('data-')):
                    element.attrib.pop(attrib)
                # Truncate long attribute values except for selectors
                elif attrib not in attributes_hates_truncate and len(element.attrib[attrib]) > attr_value_threshold:
                    element.attrib[attrib] = element.attrib[attrib][:attr_value_threshold] + '...'
            
            # Truncate text content if it's too long
            if element.text and len(element.text.strip()) > text_threshold:
                element.text = element.text.strip()[:text_threshold] + '...'
                
            # Also truncate tail text if present
            if element.tail and len(element.tail.strip()) > text_threshold:
                element.tail = element.tail.strip()[:text_threshold] + '...'

        # 4. Detect duplicates and drop them in a single pass
        seen: dict[tuple, None] = {}
        for el in list(tree.xpath('//*[@class]')):          # snapshot once, XPath is fast
            parent = el.getparent()
            if parent is None:
                continue

            cls = el.get('class')
            if not cls:
                continue

            # ── build signature ───────────────────────────────────────────
            h = xxhash.xxh64()                              # stream, no big join()
            for txt in el.itertext():
                h.update(txt)
            sig = (el.tag, cls, h.intdigest())             # tuple cheaper & hashable

            # ── first seen? keep – else drop ─────────────
            if sig in seen and parent is not None:
                parent.remove(el)                           # duplicate
            else:
                seen[sig] = None
        
        # # 4. Find repeated patterns and keep only a few examples
        # # This is a simplistic approach - more sophisticated pattern detection could be implemented
        # pattern_elements = {}
        # for element in tree.xpath('//*[contains(@class, "")]'):
        #     parent = element.getparent()
        #     if parent is None:
        #         continue
                
        #     # Create a signature based on tag and classes
        #     classes = element.get('class', '')
        #     if not classes:
        #         continue
        #     innert_text = ''.join(element.xpath('.//text()'))
        #     innert_text_hash = xxhash.xxh64(innert_text.encode()).hexdigest()
        #     signature = f"{element.tag}.{classes}.{innert_text_hash}"
            
        #     if signature in pattern_elements:
        #         pattern_elements[signature].append(element)
        #     else:
        #         pattern_elements[signature] = [element]
        
        # # Keep only first examples of each repeating pattern
        # for signature, elements in pattern_elements.items():
        #     if len(elements) > 1:
        #         # Keep the first element and remove the rest
        #         for element in elements[1:]:
        #             if element.getparent() is not None:
        #                 element.getparent().remove(element)


        # # Keep only 3 examples of each repeating pattern
        # for signature, elements in pattern_elements.items():
        #     if len(elements) > 3:
        #         # Keep the first 2 and last elements
        #         for element in elements[2:-1]:
        #             if element.getparent() is not None:
        #                 element.getparent().remove(element)
        
        # 5. Convert back to string
        result = etree.tostring(tree, encoding='unicode', method='html')
        
        return result
    
    except Exception as e:
        # Fallback for parsing errors
        return html_content

def _build_xpath_for_element(element):
    """
    Build a unique XPath expression for an element.

    Args:
        element: lxml element

    Returns:
        str: XPath expression
    """
    components = []

    while element is not None and element.tag != 'html':
        parent = element.getparent()

        # Get element tag
        tag = element.tag

        # Check for id (makes xpath unique and simple)
        if element.get('id'):
            components.insert(0, f"{tag}[@id='{element.get('id')}']")
            break

        # Count position among siblings with same tag
        if parent is not None:
            siblings = [e for e in parent if isinstance(e.tag, str) and e.tag == tag]
            if len(siblings) > 1:
                index = siblings.index(element) + 1
                components.insert(0, f"{tag}[{index}]")
            else:
                components.insert(0, tag)
        else:
            components.insert(0, tag)

        element = parent

    # Add root
    components.insert(0, '')
    components.insert(0, '')

    return '/'.join(components)


def _build_css_selector_for_element(element):
    """
    Build a CSS selector for an element.

    Args:
        element: lxml element

    Returns:
        str: CSS selector
    """
    # If element has ID, that's the simplest selector
    if element.get('id'):
        return f"#{element.get('id')}"

    components = []
    current = element

    while current is not None and current.tag != 'html':
        parent = current.getparent()
        tag = current.tag

        # Build selector part for this element
        selector_part = tag

        # Add classes if present
        classes = current.get('class')
        if classes:
            # Take up to 2 most specific classes
            class_list = classes.split()[:2]
            selector_part += ''.join(f'.{cls}' for cls in class_list)

        # Add nth-child if needed to make it unique among siblings
        if parent is not None:
            siblings = [e for e in parent if isinstance(e.tag, str) and e.tag == tag]
            if len(siblings) > 1:
                # Check if classes make it unique
                if classes:
                    similar_siblings = [
                        e for e in siblings
                        if e.get('class') == classes
                    ]
                    if len(similar_siblings) > 1:
                        index = similar_siblings.index(current) + 1
                        selector_part += f':nth-of-type({index})'
                else:
                    index = siblings.index(current) + 1
                    selector_part += f':nth-of-type({index})'

        components.insert(0, selector_part)

        # Stop if we found an ID in the ancestry
        if current.get('id'):
            break

        current = parent

    return ' > '.join(components)


def get_markdown_outline_from_html(html_content):
    """
    Generate a markdown outline from HTML content based on header tags.
    Includes XPath expressions to locate each heading in the original HTML.

    Args:
        html_content (str): Raw HTML content
    Returns:
        str: Markdown outline with XPath references
    """
    try:
        # Parse HTML with lxml for XPath support
        parser = etree.HTMLParser()
        tree = lhtml.fromstring(html_content, parser=parser)

        # Find all heading elements
        headings = []
        for level in range(1, 7):
            for element in tree.xpath(f'//h{level}'):
                # Get text content
                text = ''.join(element.itertext()).strip()
                if not text:
                    continue

                # Build both XPath and CSS selector for this element
                xpath = _build_xpath_for_element(element)
                css_selector = _build_css_selector_for_element(element)

                headings.append({
                    'level': level,
                    'text': text,
                    'xpath': xpath,
                    'css': css_selector,
                    'element': element
                })

        # Sort by document order (position in tree)
        # This ensures headings appear in the order they appear in the document
        if headings:
            # Get document positions
            for heading in headings:
                # Find position in document by comparing with all elements
                all_elements = list(tree.iter())
                heading['_position'] = all_elements.index(heading['element'])

            headings.sort(key=lambda h: h['_position'])

        # Format headings for display
        heading_lines = []
        for heading in headings:
            indent = "  " * (heading['level'] - 1)
            heading_lines.append(
                f"{indent}{'#' * heading['level']} {heading['text']}\n"
                # f"{indent}   CSS:   {heading['css']}\n"
                f"{indent}   XPath: {heading['xpath']}"
            )

        headings_text = "\n".join(heading_lines) if heading_lines else "(No headings found)"

        return headings_text

    except Exception as e:
        # Fallback to markdown-based approach if parsing fails
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.unicode_snob = True
        h.body_width = 0  # Don't wrap lines

        markdown_content = h.handle(html_content)

        # Extract headings from markdown
        doc = MarkdownAnalyzer.from_string(markdown_content)
        headers_dict = doc.identify_headers()
        headers_list = headers_dict.get('Header', [])

        # Format headings for display
        heading_lines = []
        for heading in headers_list:
            indent = "  " * (heading['level'] - 1)
            heading_lines.append(f"{indent}{'#' * heading['level']} {heading['text']} (line {heading['line']})")

        headings_text = "\n".join(heading_lines) if heading_lines else "(No headings found)"

        return headings_text

def create_dom_skeleton(html_content: str, max_depth: int = 10, compact_threshold: int = 3) -> tuple[BeautifulSoup, str]:
    """
    Parse HTML and generate a DOM skeleton for reasoning about structure.

    Args:
        html_content: Raw HTML string to parse
        max_depth: Maximum depth to traverse in the DOM tree
        compact_threshold: Minimum number of consecutive identical siblings to group together

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

    def is_notable_element(tag: Tag) -> bool:
        """Check if element has notable attributes that make it worth showing separately"""
        return bool(tag.get('id')) or bool(tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

    def get_compact_signature(tag: Tag) -> str:
        """Get a simplified signature for grouping (name + child count, ignore other attrs)"""
        children = [
            child for child in tag.children
            if isinstance(child, Tag) and child.name not in ['script', 'style', 'meta', 'link', 'noscript']
        ]
        return f"{tag.name}:{len(children)}"

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

        # Group consecutive identical children for compact output
        i = 0
        while i < len(children):
            child = children[i]

            # Check if this child should be grouped with consecutive siblings
            if not is_notable_element(child):
                compact_sig = get_compact_signature(child)

                # Count consecutive identical siblings
                group_count = 1
                while (i + group_count < len(children) and
                       not is_notable_element(children[i + group_count]) and
                       get_compact_signature(children[i + group_count]) == compact_sig):
                    group_count += 1

                # If we have enough identical siblings, output a grouped line
                if group_count >= compact_threshold:
                    is_last = (i + group_count) >= len(children)
                    child_prefix = "└── " if is_last else "├── "
                    child_sig = get_element_signature(child)

                    # Get the child's children to show structure inline
                    grandchildren = [
                        gc for gc in child.children
                        if isinstance(gc, Tag) and gc.name not in ['script', 'style', 'meta', 'link', 'noscript']
                    ]

                    if grandchildren:
                        # Show child structure inline for grouped elements
                        # Check if all grandchildren are the same type
                        gc_sigs = [get_compact_signature(gc) for gc in grandchildren]
                        if len(set(gc_sigs)) == 1:
                            # All grandchildren are identical - show compactly
                            gc_name = grandchildren[0].name
                            grouped_line = f"{indent}  {child_prefix}{child_sig} [{len(grandchildren)} {gc_name}] × {group_count}"
                        else:
                            # Mixed grandchildren - just show count
                            grouped_line = f"{indent}  {child_prefix}{child_sig} × {group_count}"
                    else:
                        grouped_line = f"{indent}  {child_prefix}{child_sig} × {group_count}"

                    lines.append(grouped_line)

                    # Skip processing these grouped children individually
                    i += group_count
                    continue

            # Process child normally (not grouped)
            is_last = i == len(children) - 1
            child_prefix = "└── " if is_last else "├── "
            traverse(child, depth + 1, child_prefix)
            i += 1

    traverse(soup.html if soup.html else soup)
    skeleton = "\n".join(lines)

    return soup, skeleton

