"""Legacy shim for benchmark configs kept for backwards compatibility."""

from hyperfocus_agent.model_config_loader import BenchmarkConfig, ModelConfig, load_config

__all__ = ["BenchmarkConfig", "ModelConfig", "load_config"]
