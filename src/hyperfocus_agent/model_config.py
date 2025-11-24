"""Model configuration factory for Hyperfocus Agent.

Centralizes LLM credential loading and ChatOpenAI instantiation.
"""
import os
from dataclasses import dataclass
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.callbacks.streaming_stdout import StreamingStdOutCallbackHandler


@dataclass
class ModelCredentials:
    """Credentials for an OpenAI-compatible endpoint."""
    base_url: str
    api_key: str
    model: str
    
    @classmethod
    def from_env(cls, prefix: str) -> Optional['ModelCredentials']:
        """Load credentials from environment variables with given prefix.
        
        Args:
            prefix: Environment variable prefix (LOCAL, REMOTE, or MULTIMODAL)
            
        Returns:
            ModelCredentials if all required vars present, None otherwise
        """
        base_url = os.getenv(f"{prefix}_OPENAI_BASE_URL")
        api_key = os.getenv(f"{prefix}_OPENAI_API_KEY")
        model = os.getenv(f"{prefix}_OPENAI_MODEL")
        
        if all([base_url, api_key, model]):
            return cls(base_url=base_url, api_key=api_key, model=model)
        return None
    
    def to_chat_model(
        self, 
        streaming: bool = True, 
        temperature: float = 0.5,
        callbacks: list | None = None
    ) -> ChatOpenAI:
        """Create a ChatOpenAI instance from these credentials.
        
        Args:
            streaming: Enable streaming output
            temperature: LLM temperature (0-1)
            callbacks: Optional callback handlers
            
        Returns:
            Configured ChatOpenAI instance
        """
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            # temperature=temperature,
            streaming=streaming,
            callbacks=callbacks or [],
            # reasoning_effort="medium",
        )


@dataclass
class ModelConfig:
    """Complete model configuration for Hyperfocus Agent."""
    local: ChatOpenAI
    remote: ChatOpenAI
    multimodal: ChatOpenAI | None
    router_threshold: int
    
    @classmethod
    def from_environment(cls, verbose: bool = True) -> 'ModelConfig':
        """Load all model configurations from environment variables.

        Args:
            verbose: Whether to print initialization messages (default: True)

        Raises:
            ValueError: If required credentials are missing

        Returns:
            Configured ModelConfig instance
        """
        # Load credentials
        local_creds = ModelCredentials.from_env("LOCAL")
        remote_creds = ModelCredentials.from_env("REMOTE")
        multimodal_creds = ModelCredentials.from_env("MULTIMODAL")

        # Validate required
        if not local_creds:
            raise ValueError(
                "LOCAL_OPENAI_BASE_URL, LOCAL_OPENAI_API_KEY, and LOCAL_OPENAI_MODEL "
                "environment variables must be set."
            )

        if not remote_creds:
            raise ValueError(
                "REMOTE_OPENAI_BASE_URL, REMOTE_OPENAI_API_KEY, and REMOTE_OPENAI_MODEL "
                "environment variables must be set."
            )

        # Parse router threshold
        router_threshold = 10000
        threshold_str = os.getenv("LLM_ROUTER_THRESHOLD")
        if threshold_str and threshold_str.isdigit():
            router_threshold = int(threshold_str)

        # Create models with streaming callback
        stream_handler = StreamingStdOutCallbackHandler()

        local_model = local_creds.to_chat_model(callbacks=[stream_handler])
        remote_model = remote_creds.to_chat_model(callbacks=[stream_handler])
        multimodal_model = (
            multimodal_creds.to_chat_model(callbacks=[stream_handler])
            if multimodal_creds
            else None
        )

        # Print configuration only if verbose
        if verbose:
            print(f"Initializing agent...")
            print(f"  Local: {local_creds.base_url} / {local_creds.model}")
            print(f"  Remote: {remote_creds.base_url} / {remote_creds.model}")
            if multimodal_creds:
                print(f"  Multimodal: {multimodal_creds.base_url} / {multimodal_creds.model}")

        return cls(
            local=local_model,
            remote=remote_model,
            multimodal=multimodal_model,
            router_threshold=router_threshold,
        )
    
    def create_non_streaming_local(self) -> ChatOpenAI:
        """Create a non-streaming copy of the local model.
        
        Useful for sub-agents that shouldn't pollute stdout.
        
        Returns:
            Non-streaming ChatOpenAI configured with local credentials
        """
        return ChatOpenAI(
            model=self.local.model_name,
            api_key=self.local.openai_api_key,
            base_url=self.local.openai_api_base,
            temperature=0,
            streaming=False,  # No streaming
        )
