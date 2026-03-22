"""Tests for provider routing config support."""

from gptase.utils.config import FrameworkConfig


def test_framework_config_maps_provider_routing_object():
    """Provider routing objects from JSON should map into llm_provider."""
    config = FrameworkConfig(
        model_name="Doubao-Seed-2.0-pro",
        provider={"sort": "input_length"},
    )

    assert config.llm_provider == {"sort": "input_length"}
    assert config.to_model_config().provider == {"sort": "input_length"}


def test_framework_config_ignores_legacy_scalar_provider():
    """Legacy non-object provider values should remain ignored for compatibility."""
    config = FrameworkConfig(
        model_name="Doubao-Seed-2.0-pro",
        provider="legacy-provider-name",
    )

    assert config.llm_provider is None
    assert config.to_model_config().provider is None


def test_agent_specific_provider_override():
    """Agent config should allow provider routing overrides."""
    config = FrameworkConfig(
        model_name="Doubao-Seed-2.0-pro",
        provider={"sort": "latency"},
        agent_models={
            "deep-research-eval-agent": {
                "provider": {
                    "sort": "input_length"
                }
            }
        },
    )

    agent_config = config.get_config_for_agent("deep-research-eval-agent")

    assert agent_config is not None
    assert agent_config.provider == {"sort": "input_length"}
