# Pick which LLM to use, local or remote
import os
import sys
from typing import List
from openai import OpenAI, Stream
from openai.types.chat import ChatCompletionMessageParam, ChatCompletion, ChatCompletionChunk


class LLMRouter:
    """Routes LLM requests between local and remote clients based on message length."""

    def __init__(self, local_client: OpenAI, remote_client: OpenAI, local_model: str, remote_model: str, multimodal_client: OpenAI | None = None, multimodal_model: str | None = None):
        """
        Initialize the LLM router.

        Args:
            local_client: OpenAI client for local LLM
            remote_client: OpenAI client for remote LLM
            local_model: Model name for local LLM
            remote_model: Model name for remote LLM
            multimodal_client: Optional OpenAI client for multi-modal (vision) LLM
            multimodal_model: Optional model name for multi-modal LLM
        """
        self.local_client = local_client
        self.remote_client = remote_client
        self.local_model = local_model
        self.remote_model = remote_model
        self.multimodal_client = multimodal_client
        self.multimodal_model = multimodal_model

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
    
    def _has_image_content(self, messages: List[ChatCompletionMessageParam]) -> bool:
        """Check if any message contains image content."""
        for message in messages:
            content = message.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        return True
        return False

    def complete(
        self,
        messages: List[ChatCompletionMessageParam],
        tools: list | None = None,
        stream: bool = False,
        force_multimodal: bool = False
    ) -> ChatCompletion:
        """
        Route the completion request to local or remote LLM based on message length.

        Args:
            messages: List of chat messages
            tools: Optional list of tool definitions
            stream: Whether to stream the response (default: False)
            force_multimodal: Force use of multi-modal model (for image analysis)

        Returns:
            ChatCompletion response from the selected LLM (assembled from stream if streaming)
        """
        # Check if we should use the multi-modal model
        if force_multimodal or self._has_image_content(messages):
            if self.multimodal_client is None or self.multimodal_model is None:
                raise ValueError("Multi-modal model requested but not configured. Set MULTIMODAL_OPENAI_BASE_URL, MULTIMODAL_OPENAI_API_KEY, and MULTIMODAL_OPENAI_MODEL environment variables.")
            client = self.multimodal_client
            model = self.multimodal_model
            print(f"→ Using MULTIMODAL LLM (image content detected)")
        else:
            total_length = self._calculate_total_message_length(messages)

            if total_length > self.message_length_threshold:
                client = self.remote_client
                model = self.remote_model
                print(f"→ Using REMOTE LLM (message length: {total_length} > {self.message_length_threshold})")
            else:
                client = self.local_client
                model = self.local_model
                print(f"→ Using LOCAL LLM (message length: {total_length} ≤ {self.message_length_threshold})")

        kwargs = {"model": model, "messages": messages, "stream": stream}
        if tools is not None:
            kwargs["tools"] = tools

        if stream:
            # Stream the response and assemble the final completion
            return self._handle_streaming_response(client.chat.completions.create(**kwargs))
        else:
            return client.chat.completions.create(**kwargs)

    def _handle_streaming_response(self, stream: Stream[ChatCompletionChunk]) -> ChatCompletion:
        """
        Handle a streaming response, outputting tokens as they arrive and assembling the final response.

        Args:
            stream: The streaming response from the API

        Returns:
            ChatCompletion assembled from the stream
        """
        # Collect chunks to assemble the final response
        chunks = []
        content_parts = []
        tool_calls_parts = {}

        for chunk in stream:
            chunks.append(chunk)

            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta

                # Stream content to stdout
                if delta.content is not None:
                    sys.stdout.write(delta.content)
                    sys.stdout.flush()
                    content_parts.append(delta.content)

                # Collect tool calls
                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        idx = tool_call.index
                        if idx not in tool_calls_parts:
                            tool_calls_parts[idx] = {
                                'id': tool_call.id or '',
                                'type': tool_call.type or 'function',
                                'function': {
                                    'name': tool_call.function.name if tool_call.function else '',
                                    'arguments': ''
                                }
                            }

                        if tool_call.id:
                            tool_calls_parts[idx]['id'] = tool_call.id
                        if tool_call.function and tool_call.function.name:
                            tool_calls_parts[idx]['function']['name'] = tool_call.function.name
                        if tool_call.function and tool_call.function.arguments:
                            tool_calls_parts[idx]['function']['arguments'] += tool_call.function.arguments

        # Print newline after streaming content
        if content_parts:
            print()

        # Assemble the final ChatCompletion from chunks
        # Use the last chunk as template and fill in the assembled data
        if not chunks:
            raise ValueError("No chunks received from stream")

        last_chunk = chunks[-1]

        # Import the types we need for assembling the completion
        from openai.types.chat import ChatCompletionMessage
        from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function

        assembled_tool_calls = None
        if tool_calls_parts:
            assembled_tool_calls = [
                ChatCompletionMessageToolCall(
                    id=tc['id'],
                    type=tc['type'],
                    function=Function(
                        name=tc['function']['name'],
                        arguments=tc['function']['arguments']
                    )
                )
                for tc in sorted(tool_calls_parts.values(), key=lambda x: list(tool_calls_parts.keys()).index(next(k for k, v in tool_calls_parts.items() if v == x)))
            ]

        final_message = ChatCompletionMessage(
            role='assistant',
            content=''.join(content_parts) if content_parts else None,
            tool_calls=assembled_tool_calls
        )

        # Create a proper ChatCompletion object
        from openai.types.chat import ChatCompletion as CC
        from openai.types.chat.chat_completion import Choice
        from openai.types.completion_usage import CompletionUsage

        completion = CC(
            id=last_chunk.id,
            choices=[
                Choice(
                    finish_reason=chunks[-1].choices[0].finish_reason if chunks[-1].choices else 'stop',
                    index=0,
                    message=final_message,
                    logprobs=None
                )
            ],
            created=last_chunk.created,
            model=last_chunk.model,
            object='chat.completion',
            usage=CompletionUsage(
                completion_tokens=0,
                prompt_tokens=0,
                total_tokens=0
            ) if not hasattr(last_chunk, 'usage') or last_chunk.usage is None else last_chunk.usage
        )

        return completion


