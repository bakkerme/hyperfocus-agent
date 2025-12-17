"""Benchmark configuration loader that can be shared across tools."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    name: str
    base_url: str
    api_key: str


@dataclass
class ModelConfig:
    """Configuration for a model to benchmark."""

    name: str  # Friendly name (e.g., "grok41fast")
    model: str  # Actual model ID (e.g., "x-ai/grok-4.1-fast")
    provider_name: str
    base_url: str
    api_key: str

    # Optional overrides for remote/multimodal
    remote_base_url: str = ""
    remote_model: str = ""
    remote_api_key: str = ""
    multimodal_base_url: str = ""
    multimodal_model: str = ""
    multimodal_api_key: str = ""

    # Extra environment variables from config
    extra_env: dict[str, str] = field(default_factory=dict)

    def to_environment(self) -> dict[str, str]:
        """Convert to environment variables for Docker container."""
        env = {
            "LOCAL_OPENAI_BASE_URL": self.base_url,
            "LOCAL_OPENAI_API_KEY": self.api_key,
            "LOCAL_OPENAI_MODEL": self.model,
        }

        if self.remote_base_url:
            env.update(
                {
                    "REMOTE_OPENAI_BASE_URL": self.remote_base_url,
                    "REMOTE_OPENAI_API_KEY": self.remote_api_key,
                    "REMOTE_OPENAI_MODEL": self.remote_model,
                }
            )
        else:
            env.update(
                {
                    "REMOTE_OPENAI_BASE_URL": "",
                    "REMOTE_OPENAI_API_KEY": "",
                    "REMOTE_OPENAI_MODEL": "",
                }
            )

        if self.multimodal_base_url:
            env.update(
                {
                    "MULTIMODAL_OPENAI_BASE_URL": self.multimodal_base_url,
                    "MULTIMODAL_OPENAI_API_KEY": self.multimodal_api_key,
                    "MULTIMODAL_OPENAI_MODEL": self.multimodal_model,
                }
            )
        else:
            env.update(
                {
                    "MULTIMODAL_OPENAI_BASE_URL": "",
                    "MULTIMODAL_OPENAI_API_KEY": "",
                    "MULTIMODAL_OPENAI_MODEL": "",
                }
            )

        if self.extra_env:
            env.update(self.extra_env)

        return env


@dataclass
class BenchmarkConfig:
    """Complete benchmark configuration."""

    providers: dict[str, ProviderConfig]
    models: dict[str, ModelConfig]
    extra_env: dict[str, str]

    @classmethod
    def from_yaml(cls, path: Path) -> "BenchmarkConfig":
        """Load configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        providers: dict[str, ProviderConfig] = {}
        for name, provider_data in data.get("providers", {}).items():
            providers[name] = ProviderConfig(
                name=name,
                base_url=provider_data.get("baseURL", ""),
                api_key=provider_data.get("apiKey", ""),
            )

        models: dict[str, ModelConfig] = {}
        for name, model_data in data.get("models", {}).items():
            provider_name = model_data.get("provider", "")
            provider = providers.get(provider_name)

            if not provider:
                raise ValueError(
                    f"Model '{name}' references unknown provider '{provider_name}'"
                )

            models[name] = ModelConfig(
                name=name,
                model=model_data.get("name", ""),
                base_url=provider.base_url,
                api_key=provider.api_key,
                provider_name=provider_name,
            )

        extra_env: dict[str, str] = {}
        config_section = data.get("config", {})
        if "env" in config_section:
            extra_env = {k: str(v) for k, v in config_section["env"].items()}

        return cls(providers=providers, models=models, extra_env=extra_env)

    def get_model(self, name: str) -> ModelConfig:
        """Return a model configuration by name with shared extras applied."""
        if name not in self.models:
            available = ", ".join(sorted(self.models.keys()))
            raise ValueError(f"Unknown model '{name}'. Available: {available}")

        model = self.models[name]
        return ModelConfig(
            name=model.name,
            model=model.model,
            provider_name=model.provider_name,
            base_url=model.base_url,
            api_key=model.api_key,
            remote_base_url=model.remote_base_url,
            remote_model=model.remote_model,
            remote_api_key=model.remote_api_key,
            multimodal_base_url=model.multimodal_base_url,
            multimodal_model=model.multimodal_model,
            multimodal_api_key=model.multimodal_api_key,
            extra_env=self.extra_env.copy(),
        )

    def list_models(self) -> list[str]:
        """List all available model names."""
        return sorted(self.models.keys())

    def with_remote(self, model: ModelConfig, remote_name: str) -> ModelConfig:
        """Create a copy of model with remote settings from another model."""
        remote = self.get_model(remote_name)
        return ModelConfig(
            name=model.name,
            model=model.model,
            provider_name=model.provider_name,
            base_url=model.base_url,
            api_key=model.api_key,
            remote_base_url=remote.base_url,
            remote_model=remote.model,
            remote_api_key=remote.api_key,
            multimodal_base_url=model.multimodal_base_url,
            multimodal_model=model.multimodal_model,
            multimodal_api_key=model.multimodal_api_key,
            extra_env=model.extra_env,
        )

    def with_multimodal(self, model: ModelConfig, multimodal_name: str) -> ModelConfig:
        """Create a copy of model with multimodal settings from another model."""
        multimodal = self.get_model(multimodal_name)
        return ModelConfig(
            name=model.name,
            model=model.model,
            provider_name=model.provider_name,
            base_url=model.base_url,
            api_key=model.api_key,
            remote_base_url=model.remote_base_url,
            remote_model=model.remote_model,
            remote_api_key=model.remote_api_key,
            multimodal_base_url=multimodal.base_url,
            multimodal_model=multimodal.model,
            multimodal_api_key=multimodal.api_key,
            extra_env=model.extra_env,
        )


def load_config(config_path: Path | None = None) -> BenchmarkConfig:
    """Load benchmark configuration, trying common locations."""
    if config_path:
        return BenchmarkConfig.from_yaml(config_path)

    search_paths = [
        Path.cwd() / "model-config.yml",
        Path.cwd().parent / "model-config.yml",
        Path.cwd().parent.parent / "model-config.yml",
        Path(__file__).parents[2] / "model-config.yml",
    ]

    for path in search_paths:
        if path.exists():
            return BenchmarkConfig.from_yaml(path)

    raise FileNotFoundError(
        "model-config.yml not found. Searched: "
        + ", ".join(str(p) for p in search_paths)
    )
