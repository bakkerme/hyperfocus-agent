# Pick which LLM to use, local or remote
import os
from typing import List
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletion


class LLMRouter:
    """Routes LLM requests between local and remote clients based on message length."""
    
    def __init__(self, local_client: OpenAI, remote_client: OpenAI, local_model: str, remote_model: str):
        """
        Initialize the LLM router.
        
        Args:
            local_client: OpenAI client for local LLM
            remote_client: OpenAI client for remote LLM
            local_model: Model name for local LLM
            remote_model: Model name for remote LLM
        """
        self.local_client = local_client
        self.remote_client = remote_client
        self.local_model = local_model
        self.remote_model = remote_model
        
        # Configurable threshold for switching to remote (in characters)
        # Default to 10,000 characters (~2,500 tokens roughly)
        self.message_length_threshold = int(os.getenv("LLM_ROUTER_THRESHOLD", "10000"))
    
    def _calculate_total_message_length(self, messages: List[ChatCompletionMessageParam]) -> int:
        """Calculate the total character count of all message content."""
        total_length = 0
        for message in messages:
            content = message.get("content")
            if content:
                if isinstance(content, str):
                    total_length += len(content)
                elif isinstance(content, list):
                    # Handle structured content (images, text blocks, etc.)
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            total_length += len(item.get("text", ""))
        return total_length
    
    def complete(
        self,
        messages: List[ChatCompletionMessageParam],
        tools: list | None = None
    ) -> ChatCompletion:
        """
        Route the completion request to local or remote LLM based on message length.
        
        Args:
            messages: List of chat messages
            tools: Optional list of tool definitions
            
        Returns:
            ChatCompletion response from the selected LLM
        """
        total_length = self._calculate_total_message_length(messages)
        
        if total_length > self.message_length_threshold:
            client = self.remote_client
            model = self.remote_model
            print(f"→ Using REMOTE LLM (message length: {total_length} > {self.message_length_threshold})")
        else:
            client = self.local_client
            model = self.local_model
            print(f"→ Using LOCAL LLM (message length: {total_length} ≤ {self.message_length_threshold})")
        
        kwargs = {"model": model, "messages": messages}
        if tools is not None:
            kwargs["tools"] = tools
        
        return client.chat.completions.create(**kwargs)


