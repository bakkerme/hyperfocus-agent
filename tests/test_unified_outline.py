#!/usr/bin/env python3
"""
Demonstrate how the unified markdown outline bridges semantic structure with HTML extraction.

This shows the power of having both:
1. Human-readable markdown outline (semantic)
2. Machine-executable selectors (technical)
"""

from src.hyperfocus_agent.utils.html_utils import get_markdown_outline_from_html
from lxml import html as lhtml
from lxml.cssselect import CSSSelector

# Complex news website structure
html_sample = """
<!DOCTYPE html>
<html>
<body>
    <nav id="main-nav">
        <h2>Navigation</h2>
    </nav>
    <main>
        <article class="featured-post">
            <h1 id="article-title">Breaking: AI Agents Now Write Their Own Documentation</h1>
            <section class="article-content">
                <h2>Overview</h2>
                <p>In a stunning development...</p>

                <h2>Key Points</h2>
                <div class="key-points">
                    <h3>Impact on Developers</h3>
                    <p>Developers are reporting...</p>
                    <h3>Industry Response</h3>
                    <p>Tech giants have responded...</p>
                </div>

                <h2>Technical Details</h2>
                <div class="technical-section">
                    <h3>Architecture</h3>
                    <h4>Component Design</h4>
                    <p>The system uses...</p>
                    <h4>Data Flow</h4>
                    <p>Information flows through...</p>
                </div>
            </section>
        </article>
        <aside class="related">
            <h2>Related Articles</h2>
            <article>
                <h3>Previous Breakthroughs</h3>
            </article>
        </aside>
    </main>
</body>
</html>
"""

print("="*70)
print("UNIFIED MARKDOWN OUTLINE WITH HTML SELECTORS")
print("="*70)
print()

outline = get_markdown_outline_from_html(html_sample)
print(outline)

print("\n" + "="*70)
print("DEMONSTRATING THE BRIDGE: SEMANTIC → TECHNICAL")
print("="*70)
print()

# Parse for extraction
tree = lhtml.fromstring(html_sample)

print("SCENARIO: Extract content from 'Technical Details' section")
print("-" * 70)
print()

# Using the CSS selector from the outline
css = "article.featured-post > section.article-content > h2:nth-of-type(3)"
print(f"1. From outline, we identified CSS selector:")
print(f"   {css}")
print()

# Extract the heading
heading = tree.cssselect(css)[0]
print(f"2. Extracted heading text: '{heading.text}'")
print()

# Now get all content under this heading
print("3. Extract all sub-headings in this section:")
# Find the parent section and get subsequent h3/h4 elements
xpath = "//h2[text()='Technical Details']/following-sibling::div[1]//h3 | //h2[text()='Technical Details']/following-sibling::div[1]//h4"
subheadings = tree.xpath(xpath)
for sh in subheadings:
    level = "   " if sh.tag == 'h4' else " "
    print(f"  {level}- {sh.text}")

print()
print("="*70)
print("WHY THIS MATTERS")
print("="*70)
print()
print("✓ SEMANTIC UNDERSTANDING:")
print("  The markdown outline shows document structure at a glance")
print("  Humans can quickly understand content hierarchy")
print()
print("✓ TECHNICAL PRECISION:")
print("  CSS/XPath selectors provide exact extraction paths")
print("  Agents can programmatically extract specific sections")
print()
print("✓ WORKFLOW OPTIMIZATION:")
print("  1. Agent reads outline → understands structure")
print("  2. User/Agent identifies needed section")
print("  3. Use provided selector to extract exact content")
print("  4. No trial-and-error with selector design")
print()
print("✓ BEST OF BOTH WORLDS:")
print("  Markdown = Human-friendly navigation")
print("  Selectors = Machine-executable extraction")
print("="*70)
