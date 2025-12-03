"""Tests for the get_xpath_list tool"""
import pytest
from unittest.mock import MagicMock, patch
from hyperfocus_agent.langchain_state import DataEntry


# Sample HTML for testing
SAMPLE_HTML = """
<html>
<head><title>Test Product Page</title></head>
<body>
    <div class="products">
        <div class="product" id="prod1">
            <h2 class="product-name">Widget A</h2>
            <span class="price">$19.99</span>
            <p class="description">A great widget</p>
        </div>
        <div class="product" id="prod2">
            <h2 class="product-name">Widget B</h2>
            <span class="price">$29.99</span>
            <p class="description">An even better widget</p>
        </div>
        <div class="product" id="prod3">
            <h2 class="product-name">Widget C</h2>
            <span class="price">$39.99</span>
            <p class="description">The best widget</p>
        </div>
    </div>
</body>
</html>
"""


@pytest.fixture
def mock_runtime():
    """Create a mock runtime with sample page data"""
    runtime = MagicMock()
    runtime.tool_call_id = "test_call_123"
    
    # Mock the stored page data
    page_entry: DataEntry = {
        "data_id": "page_test123",
        "data_type": "html_page",
        "content": SAMPLE_HTML,
        "created_at": "2025-11-27T00:00:00",
        "metadata": {
            "url": "https://example.com/products",
            "html_size": len(SAMPLE_HTML),
            "encoding": "utf-8",
            "skeleton": "mock skeleton",
            "markdown_outline": "mock outline"
        }
    }
    
    # Setup the runtime to return our test data via runtime.state
    runtime.state = {"stored_data": {"page_test123": page_entry}}
    
    return runtime


# Import the actual function (not the wrapped tool)
# We'll need to test the underlying function directly since ToolRuntime injection
# is complex to mock properly
from hyperfocus_agent.langchain_tools import web_tools


def test_get_xpath_list_page_not_found(mock_runtime):
    """Test error handling when page_id doesn't exist"""
    mock_runtime.state = {"stored_data": {}}
    
    # Call the actual function wrapped by @tool decorator
    # The function is accessible via the tool's func attribute
    result = web_tools.get_xpath_list.func(
        page_id="page_nonexistent",
        user_query="all prices",
        runtime=mock_runtime
    )
    
    assert "Error: No page found" in result
    assert "page_nonexistent" in result


def test_get_xpath_list_invalid_page_data(mock_runtime):
    """Test error handling when stored data is malformed"""
    mock_runtime.state = {
        "stored_data": {"page_test123": {"invalid": "data"}}  # Missing 'content'
    }
    
    result = web_tools.get_xpath_list.func(
        page_id="page_test123",
        user_query="all prices",
        runtime=mock_runtime
    )
    
    assert "Error:" in result
    assert "not a valid page object" in result


def test_get_xpath_list_non_html_content(mock_runtime):
    """Test error handling when content is not HTML string"""
    mock_runtime.state["stored_data"]["page_test123"]["content"] = 12345  # Not a string
    
    result = web_tools.get_xpath_list.func(
        page_id="page_test123",
        user_query="all prices",
        runtime=mock_runtime
    )
    
    assert "Error:" in result
    assert "does not contain HTML content" in result


@patch("hyperfocus_agent.langchain_tools.task_tools.execute_task")
def test_get_xpath_list_success(mock_execute_task, mock_runtime):
    """Test successful XPath list generation"""
    # Mock the sub-agent response
    mock_execute_task.return_value = """| Section | XPath Expression |
|---------|------------------|
| Product names | //h2[@class='product-name']/text() |
| Product prices | //span[@class='price']/text() |
| Product descriptions | //p[@class='description']/text() |"""
    
    result = web_tools.get_xpath_list.func(
        page_id="page_test123",
        user_query="all product information",
        runtime=mock_runtime
    )
    
    # Verify execute_task was called with correct parameters
    assert mock_execute_task.called
    call_args = mock_execute_task.call_args
    assert call_args.kwargs["runtime"] == mock_runtime
    assert "all product information" in call_args.kwargs["prompt"]
    assert call_args.kwargs["data_text"] == SAMPLE_HTML
    assert call_args.kwargs["enable_tools"] is False
    
    # Verify result format
    assert "✓ XPath search completed" in result
    assert "https://example.com/products" in result
    assert "all product information" in result
    assert "Product names" in result
    assert "//h2[@class='product-name']" in result
    assert "web_extract_with_xpath()" in result


@patch("hyperfocus_agent.langchain_tools.task_tools.execute_task")
def test_get_xpath_list_task_exception(mock_execute_task, mock_runtime):
    """Test error handling when sub-agent task fails"""
    mock_execute_task.side_effect = Exception("Task execution failed")
    
    result = web_tools.get_xpath_list.func(
        page_id="page_test123",
        user_query="all prices",
        runtime=mock_runtime
    )
    
    assert "Error searching for XPath expressions" in result
    assert "Task execution failed" in result


@patch("hyperfocus_agent.langchain_tools.task_tools.execute_task")
def test_get_xpath_list_prompt_construction(mock_execute_task, mock_runtime):
    """Test that the prompt is constructed correctly"""
    mock_execute_task.return_value = "| Section | XPath |\n|---------|-------|"
    
    web_tools.get_xpath_list.func(
        page_id="page_test123",
        user_query="specific data query",
        runtime=mock_runtime
    )
    
    # Extract the prompt that was passed to execute_task
    call_args = mock_execute_task.call_args
    prompt = call_args.kwargs["prompt"]
    
    # Verify prompt structure
    assert "HTML processing agent" in prompt
    assert "specific data query" in prompt
    assert "XPath expressions" in prompt
    assert "markdown table" in prompt
    assert "| Section | XPath Expression |" in prompt
    assert "Do not include any additional commentary" in prompt


@patch("hyperfocus_agent.langchain_tools.task_tools.execute_task")
def test_get_xpath_list_with_complex_query(mock_execute_task, mock_runtime):
    """Test with a more complex user query"""
    mock_execute_task.return_value = """| Section | XPath Expression |
|---------|------------------|
| All product containers | //div[@class='product'] |
| Products with price over $25 | //div[@class='product'][.//span[@class='price'][contains(text(), '$2') or contains(text(), '$3')]] |"""
    
    result = web_tools.get_xpath_list.func(
        page_id="page_test123",
        user_query="all products and filter for ones with prices over $25",
        runtime=mock_runtime
    )
    
    assert "✓ XPath search completed" in result
    assert "all products and filter" in result
    assert "//div[@class='product']" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
