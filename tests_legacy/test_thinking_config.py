"""Test thinking mode configuration."""

import pytest

from gptase.models.providers import OpenAIProvider
from gptase.models.types import ModelConfig


def test_default_config_thinking_enabled():
    """Test Default Config (enable_thinking=True by default)"""
    config = ModelConfig(model_name="Qwen3-235B-A22B",
                         api_key="test-key",
                         base_url="https://test.com")
    provider = OpenAIProvider(config)
    params = provider._build_request_params([{"role": "user", "content": "test"}])

    # enable_thinking defaults to True, so extra_body should be present
    assert "extra_body" in params, "extra_body should be in params when thinking is enabled by default"
    assert params["extra_body"]["enable_thinking"] is True


def test_thinking_explicitly_disabled():
    """Test enable_thinking=False explicitly disables thinking"""
    config = ModelConfig(model_name="Qwen3-235B-A22B",
                         api_key="test-key",
                         base_url="https://test.com",
                         enable_thinking=False)
    provider = OpenAIProvider(config)
    params = provider._build_request_params([{"role": "user", "content": "test"}])

    assert "extra_body" not in params, "extra_body should not be in params when thinking is explicitly disabled"


def test_thinking_enabled():
    """Test Thinking Enabled (enable_thinking=True)"""
    config = ModelConfig(model_name="Qwen3-235B-A22B",
                         api_key="test-key",
                         base_url="https://test.com",
                         enable_thinking=True)
    provider = OpenAIProvider(config)
    params = provider._build_request_params([{"role": "user", "content": "test"}])

    assert "extra_body" in params, "extra_body should be in params when enable_thinking=True"
    assert params["extra_body"][
        "enable_thinking"] is True, "extra_body should have enable_thinking=True"


def test_thinking_with_stream():
    """Test Thinking with stream enabled"""
    config = ModelConfig(model_name="Qwen3-235B-A22B",
                         api_key="test-key",
                         base_url="https://test.com",
                         enable_thinking=True,
                         stream=True)
    provider = OpenAIProvider(config)
    params = provider._build_request_params([{"role": "user", "content": "test"}])

    assert params["extra_body"][
        "enable_thinking"] is True, "extra_body should be preserved"
    assert params["stream"] is True, "stream should be True"


def test_provider_routing_without_thinking():
    """Test provider routing is passed through even when thinking is disabled."""
    config = ModelConfig(model_name="Qwen3-235B-A22B",
                         api_key="test-key",
                         base_url="https://test.com",
                         enable_thinking=False,
                         provider={"sort": "input_length"})
    provider = OpenAIProvider(config)
    params = provider._build_request_params([{"role": "user", "content": "test"}])

    assert params["extra_body"]["provider"] == {"sort": "input_length"}
    assert "enable_thinking" not in params["extra_body"]


def test_provider_routing_merges_with_thinking():
    """Test provider routing coexists with thinking mode in extra_body."""
    config = ModelConfig(model_name="Qwen3-235B-A22B",
                         api_key="test-key",
                         base_url="https://test.com",
                         enable_thinking=True,
                         provider={"sort": "input_length"})
    provider = OpenAIProvider(config)
    params = provider._build_request_params([{"role": "user", "content": "test"}])

    assert params["extra_body"]["enable_thinking"] is True
    assert params["extra_body"]["provider"] == {"sort": "input_length"}
