#!/usr/bin/env python3
"""Test script to demonstrate the compact DOM skeleton feature"""

from src.hyperfocus_agent.langchain_tools.web_tools import create_dom_skeleton

# Sample HTML with repetitive structure (like a table)
html_sample = """
<html>
<body>
    <h1>Sample Table</h1>
    <table id="main-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Age</th>
                <th>City</th>
            </tr>
        </thead>
        <tbody>
            <tr><td>Alice</td><td>30</td><td>NYC</td></tr>
            <tr><td>Bob</td><td>25</td><td>LA</td></tr>
            <tr><td>Charlie</td><td>35</td><td>SF</td></tr>
            <tr><td>David</td><td>28</td><td>Chicago</td></tr>
            <tr><td>Eve</td><td>32</td><td>Boston</td></tr>
            <tr><td>Frank</td><td>29</td><td>Seattle</td></tr>
            <tr><td>Grace</td><td>31</td><td>Denver</td></tr>
            <tr><td>Henry</td><td>27</td><td>Austin</td></tr>
        </tbody>
    </table>

    <div class="container">
        <div class="item">Item 1</div>
        <div class="item">Item 2</div>
        <div class="item">Item 3</div>
        <h2>Important Section</h2>
        <div class="item">Item 4</div>
        <div class="item">Item 5</div>
    </div>
</body>
</html>
"""

print("=" * 80)
print("COMPACT DOM SKELETON (compact_threshold=3)")
print("=" * 80)
_, skeleton_compact = create_dom_skeleton(html_sample, compact_threshold=3)
print(skeleton_compact)

print("\n" + "=" * 80)
print("NON-COMPACT DOM SKELETON (compact_threshold=999)")
print("=" * 80)
_, skeleton_full = create_dom_skeleton(html_sample, compact_threshold=999)
print(skeleton_full)

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Compact version: {len(skeleton_compact)} chars, {skeleton_compact.count(chr(10))+1} lines")
print(f"Full version: {len(skeleton_full)} chars, {skeleton_full.count(chr(10))+1} lines")
print(f"Reduction: {100 - (len(skeleton_compact)/len(skeleton_full)*100):.1f}% fewer characters")
print(f"           {skeleton_full.count(chr(10))+1 - (skeleton_compact.count(chr(10))+1)} fewer lines")
