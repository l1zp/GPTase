"""
Tests for the model management system
"""

import asyncio
import json
from pathlib import Path

import pytest

from src.models.model import Model
from src.models.types import ModelConfig
from src.models.types import ModelProvider
from src.models.types import ModelResponse
from src.models.types import ModelRole


@pytest.fixture
def llm_config_data():
    """Fixture to provide the LLM configuration template data."""
    config_path = Path(__file__).parent.parent / "config" / "llm_config.template.json"
    if not config_path.exists():
        pytest.fail(f"Config file not found at {config_path}")

    with open(config_path, "r") as f:
        return json.load(f)


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
    """Test agent-specific model configuration (updated for Agent Name architecture)."""
    default_config = ModelConfig(provider=ModelProvider.LOCAL)

    manager = Model(default_config)

    # Test getting agent-specific config
    # Uses FrameworkConfig to get agent-specific models
    planner_model_config = manager.get_config_for_agent("planner")
    assert planner_model_config is not None
    assert planner_model_config.provider == ModelProvider.LOCAL

    # Test fallback to default for unknown agent
    unknown_agent_config = manager.get_config_for_agent("unknown_agent")
    assert unknown_agent_config.model_name == default_config.model_name


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


def test_llm_config_validation(llm_config_data):
    """Test that LLM configuration template has valid structure"""
    config = llm_config_data

    # Verify required fields exist
    required_fields = ["model_name", "api_key", "temperature", "max_tokens"]
    for field in required_fields:
        assert field in config, f"Missing required field: {field}"

    # Verify field types
    assert isinstance(config["temperature"], (int, float)), "temperature must be number"
    assert isinstance(config["max_tokens"], int), "max_tokens must be integer"
    assert config["max_tokens"] > 0, "max_tokens must be positive"


@pytest.mark.asyncio
async def test_chat_completions_create_response(llm_config_data):
    """Test that chat completions create returns a valid response"""
    config_data = llm_config_data

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

    assert isinstance(response, ModelResponse)
    assert response.content is not None
    assert len(response.content) > 0
