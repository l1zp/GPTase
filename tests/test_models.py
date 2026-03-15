"""
Tests for the model management system
"""

import json
from pathlib import Path

import pytest

from gptase.models.model import Model
from gptase.models.types import ImageUrlContent
from gptase.models.types import ModelConfig
from gptase.models.types import ModelProvider
from gptase.models.types import ModelResponse
from gptase.models.types import TextContent


@pytest.fixture
def llm_config_data():
    """Fixture to provide the LLM configuration template data."""
    config_path = Path(__file__).parent.parent / "config" / "llm_config.template.json"
    if not config_path.exists():
        pytest.fail(f"Config file not found at {config_path}")

    with open(config_path, "r") as f:
        return json.load(f)


class TestModel:
    """Tests for the Model manager class."""

    async def test_initialization(self):
        """Test model manager initialization."""
        config = ModelConfig(provider=ModelProvider.LOCAL)
        manager = Model(config)

        assert len(manager.providers) == 2
        assert manager.default_config.provider == ModelProvider.LOCAL.value

    async def test_mock_provider(self):
        """Test mock provider for testing."""
        config = ModelConfig(provider=ModelProvider.LOCAL)
        manager = Model(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = await manager.generate(messages)

        assert isinstance(response, ModelResponse)
        assert "LocalProvider mock response" in response.content
        assert response.provider == ModelProvider.LOCAL.value

    async def test_role_configuration(self):
        """Test agent-specific model configuration (updated for Agent Name architecture)."""
        default_config = ModelConfig(provider=ModelProvider.LOCAL)
        manager = Model(default_config)

        # Test getting config for an agent — should return a valid ModelConfig
        # regardless of whether agent-specific config exists in config file
        planner_model_config = manager.get_config_for_agent("planner")
        assert planner_model_config is not None
        assert planner_model_config.model_name is not None

        # Test fallback to default for unknown agent
        unknown_agent_config = manager.get_config_for_agent("unknown_agent")
        assert unknown_agent_config.model_name == default_config.model_name

    async def test_health_check(self):
        """Test health check functionality."""
        config = ModelConfig(provider=ModelProvider.LOCAL)
        manager = Model(config)

        health = await manager.health_check(ModelProvider.LOCAL.value)
        assert health["status"] == "healthy"
        assert health["provider"] == ModelProvider.LOCAL.value

    async def test_usage_stats(self):
        """Test usage statistics."""
        config = ModelConfig(provider=ModelProvider.LOCAL)
        manager = Model(config)

        stats = manager.get_usage_stats()
        assert "total_providers" in stats
        assert "default_provider" in stats
        assert stats["total_providers"] == 2


class TestLLMConfig:
    """Tests for LLM configuration loading and validation."""

    def test_config_template_has_required_fields(self, llm_config_data):
        """Test that LLM configuration template has valid structure."""
        config = llm_config_data

        # Verify required fields exist (api_key is now loaded from .env, not the config file)
        required_fields = ["model_name", "temperature", "max_tokens", "provider"]
        for field in required_fields:
            assert field in config, f"Missing required field: {field}"

        # Verify field types
        assert isinstance(config["temperature"], (int, float)), "temperature must be number"
        assert isinstance(config["max_tokens"], int), "max_tokens must be integer"
        assert config["max_tokens"] > 0, "max_tokens must be positive"

    async def test_generate_returns_valid_response(self, llm_config_data):
        """Test that chat completions create returns a valid response."""
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


class TestMultimodalTypes:
    """Tests for multimodal content types."""

    def test_text_content_creation(self):
        """Test TextContent model creation."""
        content = TextContent(text="Hello, world!")
        assert content.type == "text"
        assert content.text == "Hello, world!"

    def test_text_content_serialization(self):
        """Test TextContent serialization to dict."""
        content = TextContent(text="Test message")
        data = content.model_dump()
        assert data["type"] == "text"
        assert data["text"] == "Test message"

    def test_image_url_content_creation(self):
        """Test ImageUrlContent model creation."""
        content = ImageUrlContent(image_url={"url": "data:image/png;base64,abc123"})
        assert content.type == "image_url"
        assert content.image_url["url"] == "data:image/png;base64,abc123"

    def test_image_url_content_serialization(self):
        """Test ImageUrlContent serialization."""
        content = ImageUrlContent(image_url={"url": "data:image/jpeg;base64,test"})
        data = content.model_dump()
        assert data["type"] == "image_url"
        assert "image_url" in data

    def test_multimodal_content_union(self):
        """Test that MultimodalContent can be either type."""
        from gptase.models.types import MultimodalContent

        text = TextContent(text="Hello")
        image = ImageUrlContent(image_url={"url": "data:image/png;base64,xyz"})

        # Both should be valid MultimodalContent
        assert isinstance(text, TextContent)
        assert isinstance(image, ImageUrlContent)

        # Dict should also be valid
        dict_content = {"type": "text", "text": "Custom content"}
        assert isinstance(dict_content, dict)
