"""Task execution system for running isolated LLM calls without chat history."""
import os
import requests
import json
from typing import Any, Dict, List
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam


class TaskExecutor:
    """
    Executes isolated LLM tasks without maintaining conversation history.

    Each task is a single LLM call with:
    - A system prompt describing the task
    - Data to process
    - No access to the main agent's conversation history
    """

    def __init__(self, llm_router):
        """
        Initialize the task executor.

        Args:
            llm_router: The LLMRouter instance to use for completions
        """
        self.llm_router = llm_router

        # Jina AI configuration
        self.jina_api_key = os.getenv("JINA_API_KEY", "")
        self.jina_api_url = "https://api.jina.ai/v1/segment"
        self.use_jina_segmenter = bool(self.jina_api_key)

    def execute_task(self, task_prompt: str, data: str) -> str:
        """
        Execute a single task with the given prompt and data.

        Args:
            task_prompt: Instructions for what the LLM should do with the data
            data: The data to process

        Returns:
            The LLM's response as a string
        """
        # Create a fresh message context with just the task
        messages: List[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "You are a task executor. Process the data according to the user's instructions. Provide clear, concise and terse results, intended to be processed further."
            },
            {
                "role": "user",
                "content": f"{task_prompt}\n\nData to process:\n{data}"
            }
        ]

        print(f"\n Sending task prompt to model {task_prompt}")
        # Execute without tools, streaming disabled for simpler result extraction
        response = self.llm_router.complete(
            messages=messages,
            tools=None,
            stream=False
        )

        # Extract the content from the response
        content = response.choices[0].message.content
        # print(f"\n {content}")
        return content if content else ""

    def execute_task_with_paging(
        self,
        task_prompt: str,
        data: str,
        page_size: int = 2000,
        aggregation_strategy: str = "concatenate"
    ) -> str:
        """
        Execute a task on data that's too large to fit in context by processing it in pages.

        Args:
            task_prompt: Instructions for what the LLM should do with each page
            data: The full data to process
            page_size: Maximum characters per page (default: 15000 ~= 3.75k tokens)
            aggregation_strategy: How to combine results - "concatenate" or "summarize"

        Returns:
            Aggregated results from processing all pages
        """
        # Split data into pages
        pages = self._split_into_pages(data, page_size)

        print(f"→ Task executor: Processing {len(pages)} pages of data")

        # Process each page
        page_results = []
        for i, page in enumerate(pages, 1):
            print(f"→ Processing page {i}/{len(pages)}...")

            # Add page context to the prompt
            page_prompt = f"{task_prompt}\n\n[Processing page {i} of {len(pages)}]"

            result = self.execute_task(page_prompt, page)
            page_results.append(result)

        # Aggregate results
        if aggregation_strategy == "concatenate":
            return self._concatenate_results(page_results)
        elif aggregation_strategy == "summarize":
            return self._summarize_results(task_prompt, page_results)
        else:
            raise ValueError(f"Unknown aggregation strategy: {aggregation_strategy}")

    def _split_into_pages(self, data: str, page_size: int) -> List[str]:
        """
        Split data into pages using Jina AI's semantic segmenter API or fallback to simple splitting.

        Args:
            data: The text to split into pages
            page_size: Maximum characters per page

        Returns:
            List of text chunks
        """
        if len(data) <= page_size:
            return [data]

        # Try using Jina AI segmenter if configured. Jina Segmenter has a 64k character limit.
        if self.use_jina_segmenter and len(data) < 64000: 
            try:
                return self._split_with_jina(data, page_size)
            except Exception as e:
                print(f"⚠️  Jina segmenter failed ({e}), falling back to simple splitting")
                # Fall through to simple splitting

        # Fallback: Simple line-based splitting
        return self._split_simple(data, page_size)

    def _split_with_jina(self, data: str, max_chunk_length: int) -> List[str]:
        """
        Use Jina AI's segmenter API to intelligently split text into semantic chunks.

        Args:
            data: The text to segment
            max_chunk_length: Maximum length per chunk

        Returns:
            List of semantically meaningful text chunks
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.jina_api_key}'
        }

        payload = {
            "content": data,
            "return_tokens": False,  # We don't need token info
            "return_chunks": True,   # We want the chunks
            "max_chunk_length": max_chunk_length
        }

        print(payload)

        print(f"→ Using Jina AI segmenter (max chunk length: {max_chunk_length})")

        response = requests.post(
            self.jina_api_url,
            headers=headers,
            data=json.dumps(payload),
            timeout=30
        )

        response.raise_for_status()
        result = response.json()

        # Extract chunks from the response
        chunks = result.get("chunks", [])

        if not chunks:
            raise ValueError("Jina API returned no chunks")

        print(f"→ Jina segmented into {len(chunks)} semantic chunks")

        return chunks

    def _split_simple(self, data: str, page_size: int) -> List[str]:
        """
        Simple fallback splitting that tries to split on newlines.

        Args:
            data: The text to split
            page_size: Maximum characters per page

        Returns:
            List of text chunks
        """
        pages = []
        lines = data.split('\n')
        current_page = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1  # +1 for the newline

            # If adding this line would exceed page_size, start a new page
            if current_size + line_size > page_size and current_page:
                pages.append('\n'.join(current_page))
                current_page = [line]
                current_size = line_size
            else:
                current_page.append(line)
                current_size += line_size

        # Add the last page if it has content
        if current_page:
            pages.append('\n'.join(current_page))

        return pages

    def _concatenate_results(self, page_results: List[str]) -> str:
        """Concatenate all page results with separators."""
        separator = "\n\n--- Page Break ---\n\n"
        return separator.join(page_results)

    def _summarize_results(self, original_task: str, page_results: List[str]) -> str:
        """
        Use the LLM to create a final summary of all page results.
        This is useful when you want a cohesive answer rather than separate page results.
        """
        # Combine all page results
        combined = self._concatenate_results(page_results)

        # Ask the LLM to synthesize a final answer
        summary_prompt = f"""The following are results from processing multiple pages of data for this task:
{original_task}

Please synthesize these results into a single, cohesive response."""

        print("→ Creating final summary of all pages...")
        return self.execute_task(summary_prompt, combined)


# Global task executor instance (will be initialized in main.py)
_task_executor_instance = None


def initialize_task_executor(llm_router):
    """Initialize the global task executor with the LLM router."""
    global _task_executor_instance
    _task_executor_instance = TaskExecutor(llm_router)


def get_task_executor() -> TaskExecutor:
    """Get the global task executor instance."""
    if _task_executor_instance is None:
        raise RuntimeError("Task executor not initialized. Call initialize_task_executor first.")
    return _task_executor_instance
