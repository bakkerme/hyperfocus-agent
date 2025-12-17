import json
import os

import pytest

from benchmarks.lib.config import load_config
from hyperfocus_agent.langchain_tools.web_tools import (
    web_load_web_page,
    web_get_markdown_view,
    web_extract_with_xpath,
    web_lookup_with_grep,
)
from hyperfocus_agent.langchain_tools.file_tools import FILE_TOOLS
from hyperfocus_agent.trajectory.runner import plan_agent_trajectory

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "llm: mark test as requiring LLM access"
    )

def _configure_model_environment() -> None:
    """Load model config from model-config.yml and apply it to the environment.

    The model name can be overridden with HF_LLM_MODEL; otherwise the first
    configured model is used. For tests, we mirror the local model settings
    into the remote slots so that hyperfocus_agent.model_config.ModelConfig
    can initialize without separate remote credentials.
    """
    config = load_config()

    # Allow overriding the model used for tests
    model_name = os.getenv("HF_LLM_MODEL")
    if not model_name:
        raise ValueError("HF_LLM_MODEL environment variable must be set for LLM tests")

    model = config.get_model(model_name)

    # Mirror local into remote if remote is not configured
    if not model.remote_base_url:
        model.remote_base_url = model.base_url
        model.remote_model = model.model
        model.remote_api_key = model.api_key

    env = model.to_environment()
    os.environ.update(env)


def _get_pokemon_task_prompt() -> str:
    """Return the benchmark task prompt used for Japanese Pokémon card CSV."""
    return (
        "I need a list of the main, subsets and promotional sets of japanese "
        "pokemon card sets from this site, in csv format. "
        "Use the following column names: "
        "'Set,Era,Set No.,Symbol,Japanese Name,English Equivalent,No. of Cards,Release Date'. "
        "Write to /workspace/test_area/jp_cards_all.csv. "
        "You may use the xpath tool to help you figure out what you need to extract. "
        "Ignore anything with the class 'roundy' in the html when extracting. "
        "The site is http://asset-server:8080/pokemon.html"
    )


@pytest.mark.skipif(
    not os.getenv("HF_LLM_TESTS"),
    reason="Set HF_LLM_TESTS=1 to run LLM-based trajectory tests",
)
def test_pokemon_trajectory_llm_smoke():
    """Run the real trajectory planner for the Pokémon benchmark and validate basics.

    This test is intentionally light on strict expectations so it remains robust
    across prompt/model changes, but it still verifies:
    - We get at least one step
    - Each step has the expected fields
    - Some web tools are suggested
    - Clearly essential tools are not disabled
    It also prints the full trajectory JSON for manual inspection.
    """
    # Ensure LOCAL_*/REMOTE_* env vars are configured via model_config_loader
    _configure_model_environment()

    # Assemble a minimal but realistic tool set for this benchmark
    # Web tools used heavily by the benchmark
    web_tools = [
        web_load_web_page,
        web_get_markdown_view,
        web_extract_with_xpath,
        web_lookup_with_grep,
    ]

    # File tools, since the benchmark writes CSV to disk
    tools = [*web_tools, *FILE_TOOLS]

    task_prompt = _get_pokemon_task_prompt()

    trajectory = plan_agent_trajectory(task_prompt, tools)

    # Print result for manual inspection / debugging
    print("\n=== Pokémon Trajectory ===")
    print(json.dumps(trajectory, indent=2, ensure_ascii=False))
    print("=== End Trajectory ===\n")

    # Basic shape checks
    assert "steps" in trajectory
    assert "disabled_tools" in trajectory
    assert isinstance(trajectory["steps"], list)
    assert isinstance(trajectory["disabled_tools"], list)
    assert len(trajectory["steps"]) >= 1

    # Step field checks
    for step in trajectory["steps"]:
        assert "id" in step and isinstance(step["id"], str) and step["id"].strip()
        assert "description" in step and isinstance(step["description"], str)
        assert "rationale" in step and isinstance(step["rationale"], str)
        assert "suggested_tools" in step and isinstance(step["suggested_tools"], list)

    all_suggested = {tool for step in trajectory["steps"] for tool in step["suggested_tools"]}

    # Expect at least some web-related tools to be suggested
    assert "web_load_web_page" in all_suggested or "web_extract_with_xpath" in all_suggested

    # Essential web tools should not be disabled
    for essential in ["web_load_web_page", "web_extract_with_xpath"]:
        assert essential not in trajectory["disabled_tools"]

