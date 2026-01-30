"""Test thinking mode configuration."""

import pytest

from src.models.providers import OpenAIProvider
from src.models.types import ModelConfig


def test_default_config_thinking_disabled():
    """Test Default Config (enable_thinking=False)"""
    config = ModelConfig(model_name="Qwen3-235B-A22B",
                         api_key="test-key",
                         base_url="https://test.com")
    provider = OpenAIProvider(config)
    params = provider._build_request_params([{"role": "user", "content": "test"}])

    assert "extra_body" in params, "extra_body should be in params (explicitly disabled)"
    assert params["extra_body"][
        "enable_thinking"] is False, "enable_thinking should be False"


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


def test_thinking_with_provider_config():
    """Test Thinking with provider_config"""
    config = ModelConfig(model_name="Qwen3-235B-A22B",
                         api_key="test-key",
                         base_url="https://test.com",
                         enable_thinking=True,
                         provider_config={
                             "stream": True,
                             "custom_param": "value"
                         })
    provider = OpenAIProvider(config)
    params = provider._build_request_params([{"role": "user", "content": "test"}])

    assert params["extra_body"][
        "enable_thinking"] is True, "extra_body should be preserved"
    assert params["stream"] is True, "provider_config should be merged"
    assert params[
        "custom_param"] == "value", "custom provider_config should be preserved"
