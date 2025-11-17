import html2text
import xxhash
import hashlib
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

def get_markdown_outline_from_html(html_content):
    """
    Generate a markdown outline from HTML content based on header tags.
    
    Args:
        html_content (str): Raw HTML content
    Returns:
        str: Markdown outline
    """

    # Step 2: Convert to markdown
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
