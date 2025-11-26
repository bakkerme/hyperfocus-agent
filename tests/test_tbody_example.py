#!/usr/bin/env python3
"""Test the specific tbody example from the user's question"""

from src.hyperfocus_agent.langchain_tools.web_tools import create_dom_skeleton

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

print("COMPACT VERSION (threshold=3):")
print("=" * 60)
_, skeleton = create_dom_skeleton(html, compact_threshold=3)
print(skeleton)

print("\n\nORIGINAL VERSION (no compacting):")
print("=" * 60)
_, skeleton_full = create_dom_skeleton(html, compact_threshold=999)
print(skeleton_full)
