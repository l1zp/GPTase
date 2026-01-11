"""
Tests for the model management system
"""

import asyncio
import json
import os
from pathlib import Path

import pytest

from src.models.model import Model
from src.models.types import ModelConfig, ModelProvider, ModelResponse, ModelRole


@pytest.mark.asyncio
async def test_model_manager_initialization():
    """Test model manager initialization."""
    config = ModelConfig(provider=ModelProvider.LOCAL)
    manager = Model(config)

    assert len(manager.providers) == 3
    assert manager.default_config.provider == ModelProvider.LOCAL.value


@pytest.mark.asyncio
async def test_mock_provider():
    """Test mock provider for testing."""
    config = ModelConfig(provider=ModelProvider.LOCAL)
    manager = Model(config)

    messages = [{"role": "user", "content": "Hello"}]
    response = await manager.generate(messages)

    assert isinstance(response, ModelResponse)
    assert "LocalProvider mock response" in response.content
    assert response.provider == ModelProvider.LOCAL.value


@pytest.mark.asyncio
async def test_role_configuration():
    """Test role-specific model configuration."""
    default_config = ModelConfig(provider=ModelProvider.LOCAL)
    planner_config = ModelConfig(
        provider=ModelProvider.LOCAL, model_name="planner-model"
    )

    manager = Model(default_config)
    manager.set_role_config(ModelRole.PLANNER, planner_config)

    # Test getting role-specific config
    planner_model_config = manager.get_role_config(ModelRole.PLANNER)
    assert planner_model_config.model_name == "planner-model"

    # Test fallback to default
    executor_config = manager.get_role_config(ModelRole.EXECUTOR)
    assert executor_config.model_name == default_config.model_name


@pytest.mark.asyncio
async def test_list_available_models():
    """Test listing available models."""
    config = ModelConfig(provider=ModelProvider.OPENAI)
    manager = Model(config)

    models = await manager.list_available_models(ModelProvider.OPENAI.value)
    assert isinstance(models, list)
    assert len(models) > 0


@pytest.mark.asyncio
async def test_health_check():
    """Test health check functionality."""
    config = ModelConfig(provider=ModelProvider.LOCAL)
    manager = Model(config)

    health = await manager.health_check(ModelProvider.LOCAL.value)
    assert health["status"] == "healthy"
    assert health["provider"] == ModelProvider.LOCAL.value


@pytest.mark.asyncio
async def test_usage_stats():
    """Test usage statistics."""
    config = ModelConfig(provider=ModelProvider.LOCAL)
    manager = Model(config)

    stats = manager.get_usage_stats()
    assert "total_providers" in stats
    assert "default_provider" in stats
    assert stats["total_providers"] == 3


def test_llm_config_validation():
    """Test that LLM configuration template has valid structure"""
    config_path = Path(__file__).parent.parent / "config" / "llm_config.template.json"
    assert config_path.exists(), f"Config file not found at {config_path}"

    with open(config_path, "r") as f:
        config = json.load(f)

    # Verify required fields exist
    required_fields = ["model_name", "api_key", "temperature", "max_tokens"]
    for field in required_fields:
        assert field in config, f"Missing required field: {field}"

    # Verify field types
    assert isinstance(config["temperature"], (int, float)), "temperature must be number"
    assert isinstance(config["max_tokens"], int), "max_tokens must be integer"
    assert config["max_tokens"] > 0, "max_tokens must be positive"


@pytest.mark.asyncio
async def test_chat_completions_create_response():
    """Test that chat completions create returns a valid response"""
    config_path = Path(__file__).parent.parent / "config" / "llm_config.template.json"
    with open(config_path, "r") as f:
        config_data = json.load(f)

    config = ModelConfig(
        provider=ModelProvider.LOCAL,
        model_name=config_data["model_name"],
        api_key=config_data.get("api_key"),
        temperature=config_data.get("temperature"),
        max_tokens=config_data.get("max_tokens"),
        base_url=config_data.get("base_url"),
    )
    manager = Model(config)

    messages = [{"role": "user", "content": "Hello World"}]
    response = await manager.generate(messages)

    # Print the response content
    print("LLM Response:", response.content)

    assert isinstance(response, ModelResponse)
    assert response.content is not None
    assert len(response.content) > 0
