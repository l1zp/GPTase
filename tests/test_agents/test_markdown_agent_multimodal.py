"""Tests for MarkdownAgent multimodal functionality."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from gptase.agents.markdown_agent import AgentDefinition
from gptase.agents.markdown_agent import MarkdownAgent


@pytest.fixture
def mock_model_manager():
    """Provide a mock model manager for testing."""
    mock = MagicMock()
    mock.get_config_for_agent = MagicMock(return_value=MagicMock())
    return mock


@pytest.fixture
def basic_definition():
    """Provide a basic agent definition for testing."""
    return AgentDefinition(
        agent_id="test_agent",
        capabilities=["test_capability"],
        requires_model=True,
        model_role="general",
        tools=[],
        description="Test agent for unit tests",
        system_prompt="You are a test agent.",
        task_processing="Process the task.",
        output_format="JSON",
        examples=None,
        temperature=0.1,
        max_tokens=1000,
        timeout=60,
    )


@pytest.fixture
def definition_no_model():
    """Provide an agent definition that doesn't require a model."""
    return AgentDefinition(
        agent_id="test_agent_no_model",
        capabilities=["test_capability"],
        requires_model=False,
        model_role="general",
        tools=[],
        description="Test agent without model requirement",
        system_prompt="You are a test agent.",
        task_processing="Process the task.",
        output_format="JSON",
        examples=None,
        temperature=0.1,
        max_tokens=1000,
        timeout=60,
    )


class TestExtractImagePaths:
    """Test _extract_image_paths method."""

    def test_single_image_path(self, definition_no_model):
        """Test extraction of single image path."""
        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=MagicMock(),
        )

        task = {
            "description": "Analyze image",
            "image_path": "/path/to/image.png",
        }

        paths = agent._extract_image_paths(task)
        assert paths == ["/path/to/image.png"]

    def test_multiple_image_paths(self, definition_no_model):
        """Test extraction of multiple image paths."""
        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=MagicMock(),
        )

        task = {
            "description": "Analyze images",
            "image_paths": ["/path/to/image1.png", "/path/to/image2.jpg"],
        }

        paths = agent._extract_image_paths(task)
        assert paths == ["/path/to/image1.png", "/path/to/image2.jpg"]

    def test_images_list(self, definition_no_model):
        """Test extraction from images list."""
        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=MagicMock(),
        )

        task = {
            "description": "Analyze images",
            "images": [
                "/path/to/image1.png",
                {
                    "path": "/path/to/image2.jpg"
                },
            ],
        }

        paths = agent._extract_image_paths(task)
        assert paths == ["/path/to/image1.png", "/path/to/image2.jpg"]

    def test_combined_sources(self, definition_no_model):
        """Test extraction from combined sources."""
        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=MagicMock(),
        )

        task = {
            "description": "Analyze",
            "image_path": "/single.png",
            "image_paths": ["/multi1.png", "/multi2.png"],
            "images": ["/list1.png"],
        }

        paths = agent._extract_image_paths(task)
        # Should deduplicate while preserving order
        assert "/single.png" in paths
        assert "/multi1.png" in paths
        assert "/multi2.png" in paths
        assert "/list1.png" in paths

    def test_no_images(self, definition_no_model):
        """Test task without images."""
        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=MagicMock(),
        )

        task = {
            "description": "Text only task",
        }

        paths = agent._extract_image_paths(task)
        assert paths == []

    def test_deduplication(self, definition_no_model):
        """Test that duplicate paths are removed."""
        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=MagicMock(),
        )

        task = {
            "image_path": "/same.png",
            "image_paths": ["/same.png", "/other.png"],
        }

        paths = agent._extract_image_paths(task)
        assert paths.count("/same.png") == 1
        assert "/other.png" in paths


class TestBuildUserPrompt:
    """Test _build_user_prompt method."""

    def test_basic_prompt(self, definition_no_model):
        """Test basic prompt building."""
        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=MagicMock(),
        )

        task = {
            "description": "Test task",
            "data": "some data",
        }

        prompt = agent._build_user_prompt(task)
        assert "Test task" in prompt
        assert "some data" in prompt

    def test_prompt_excludes_images(self, definition_no_model):
        """Test that images are excluded from prompt text when include_images=False."""
        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=MagicMock(),
        )

        task = {
            "description": "Analyze image",
            "image_path": "/path/to/image.png",
            "data": "test data",
        }

        prompt = agent._build_user_prompt(task, include_images=False)

        # Should include description and data
        assert "Analyze image" in prompt
        assert "test data" in prompt
        # Should NOT include image path in JSON
        assert "image_path" not in prompt

    def test_prompt_includes_images_when_enabled(self, definition_no_model):
        """Test that images are included in prompt when include_images=True."""
        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=MagicMock(),
        )

        task = {
            "description": "Analyze image",
            "image_path": "/path/to/image.png",
        }

        prompt = agent._build_user_prompt(task, include_images=True)

        assert "Images:" in prompt
        assert "/path/to/image.png" in prompt

    def test_prompt_with_examples(self, definition_no_model):
        """Test prompt building with examples."""
        definition_with_examples = AgentDefinition(
            agent_id="test_agent",
            capabilities=["test"],
            requires_model=False,
            model_role="general",
            tools=[],
            description="Test",
            system_prompt="Test prompt",
            task_processing="Process",
            output_format="JSON",
            examples="[TASK]\nTest task\n[RESPONSE]\nTest response",
            temperature=0.1,
            max_tokens=1000,
            timeout=60,
        )

        agent = MarkdownAgent(
            definition=definition_with_examples,
            memory_manager=MagicMock(),
        )

        task = {"description": "Test"}
        prompt = agent._build_user_prompt(task)

        assert "Examples:" in prompt
        assert "Test task" in prompt


class TestMarkdownAgentIntegration:
    """Integration tests for MarkdownAgent with multimodal support."""

    @pytest.mark.asyncio
    async def test_process_task_text_only(self, definition_no_model):
        """Test processing text-only task."""
        from unittest.mock import AsyncMock

        mock_memory = MagicMock()
        mock_memory.update_agent_status = AsyncMock()

        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=mock_memory,
        )

        # Mock the Agent class (imported in process_task)
        with patch("gptase.agents.agent.Agent") as MockAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value={
                "status": "success",
                "data": {
                    "content": "Test response"
                },
            })
            MockAgent.return_value = mock_agent_instance

            task = {"description": "Text task"}
            result = await agent.process_task(task)

            assert result["status"] == "success"
            # Should call run(), not run_with_images()
            mock_agent_instance.run.assert_called_once()
            mock_agent_instance.run_with_images.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_task_with_images(self, definition_no_model):
        """Test processing task with images triggers multimodal path."""
        from unittest.mock import AsyncMock

        mock_memory = MagicMock()
        mock_memory.update_agent_status = AsyncMock()

        agent = MarkdownAgent(
            definition=definition_no_model,
            memory_manager=mock_memory,
        )

        with patch("gptase.agents.agent.Agent") as MockAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run_with_images = AsyncMock(return_value={
                "status": "success",
                "data": {
                    "content": "Image analysis"
                },
            })
            MockAgent.return_value = mock_agent_instance

            task = {
                "description": "Analyze image",
                "image_path": "/path/to/image.png",
            }
            result = await agent.process_task(task)

            assert result["status"] == "success"
            # Should call run_with_images(), not run()
            mock_agent_instance.run_with_images.assert_called_once()
            mock_agent_instance.run.assert_not_called()
