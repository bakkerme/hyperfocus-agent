#!/usr/bin/env python3
"""Test script to demonstrate the compact DOM skeleton feature"""

from src.hyperfocus_agent.langchain_tools.web_tools import create_dom_skeleton

def test_compact_skeleton():
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

    _, skeleton_compact = create_dom_skeleton(html_sample, compact_threshold=3)
    _, skeleton_full = create_dom_skeleton(html_sample, compact_threshold=999)

    # Assertions
    assert len(skeleton_compact) < len(skeleton_full), "Compact skeleton should be smaller"
    assert skeleton_compact.count(chr(10)) < skeleton_full.count(chr(10)), "Compact skeleton should have fewer lines"
    
    # Check for expected compact markers
    # The output format uses "× N" to indicate repetition
    assert "×" in skeleton_compact or "..." in skeleton_compact, "Should contain compaction markers"
