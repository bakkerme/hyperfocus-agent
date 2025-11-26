#!/usr/bin/env python3
"""Test the specific tbody example from the user's question"""

from src.hyperfocus_agent.langchain_tools.web_tools import create_dom_skeleton

def test_tbody_example():
    # Create HTML matching user's example: 28 tr children with varying child counts
    html = """
    <html>
    <body>
        <table>
            <tbody>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td></tr>
                <tr><td>1</td><td>2</td><td>3</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td></tr>
                <tr><td>1</td><td>2</td><td>3</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr>
                <tr><td>1</td><td>2</td><td>3</td></tr>
            </tbody>
        </table>
    </body>
    </html>
    """

    _, skeleton = create_dom_skeleton(html, compact_threshold=3)
    _, skeleton_full = create_dom_skeleton(html, compact_threshold=999)

    # Assertions
    assert len(skeleton) < len(skeleton_full), "Compact skeleton should be smaller"
    # The output format uses "× N" to indicate repetition
    assert "×" in skeleton or "..." in skeleton, "Should contain compaction markers"
