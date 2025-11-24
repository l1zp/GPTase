"""
Tests for the model management system
"""

import pytest
import asyncio
from src.models.manager import ModelManager
from src.models.types import ModelConfig, ModelProvider, ModelResponse, ModelRole

@pytest.mark.asyncio
async def test_model_manager_initialization():
    """Test model manager initialization."""
    config = ModelConfig(provider=ModelProvider.CUSTOM)
    manager = ModelManager(config)
    
    assert len(manager.providers) == 4
    assert manager.default_config.provider == ModelProvider.CUSTOM

@pytest.mark.asyncio
async def test_mock_provider():
    """Test mock provider for testing."""
    config = ModelConfig(provider=ModelProvider.CUSTOM)
    manager = ModelManager(config)
    
    messages = [{"role": "user", "content": "Hello"}]
    response = await manager.generate(messages)
    
    assert isinstance(response, ModelResponse)
    assert "Mock response" in response.content
    assert response.provider == ModelProvider.CUSTOM

@pytest.mark.asyncio
async def test_role_configuration():
    """Test role-specific model configuration."""
    default_config = ModelConfig(provider=ModelProvider.CUSTOM)
    planner_config = ModelConfig(provider=ModelProvider.CUSTOM, model_name="planner-model")
    
    manager = ModelManager(default_config)
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
    manager = ModelManager(config)
    
    models = await manager.list_available_models(ModelProvider.OPENAI)
    assert isinstance(models, list)
    assert len(models) > 0

@pytest.mark.asyncio
async def test_health_check():
    """Test health check functionality."""
    config = ModelConfig(provider=ModelProvider.CUSTOM)
    manager = ModelManager(config)
    
    health = await manager.health_check(ModelProvider.CUSTOM)
    assert health["status"] == "healthy"
    assert health["provider"] == ModelProvider.CUSTOM

@pytest.mark.asyncio
async def test_usage_stats():
    """Test usage statistics."""
    config = ModelConfig(provider=ModelProvider.CUSTOM)
    manager = ModelManager(config)
    
    stats = manager.get_usage_stats()
    assert "total_providers" in stats
    assert "default_provider" in stats
    assert stats["total_providers"] == 4
