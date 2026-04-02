"""Tests for the unified Agent class with multimodal support."""

import base64
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from gptase.agents import Agent
from gptase.agents.runtime_types import InteractiveRuntimeResult
from gptase.agents.runtime_types import InteractiveRuntimeSnapshot
from gptase.agents.runtime_types import PlanHandoffProposal
from gptase.agents.runtime_types import RuntimeStopReason
from gptase.models.types import ImageUrlContent
from gptase.models.types import ModelConfig
from gptase.models.types import TextContent


@pytest.fixture
def mock_model_config():
    """Provide a mock model config for testing."""
    return ModelConfig(
        use_mock=True,
        model_name="test-model",
        api_key="test-key",
    )


@pytest.fixture
def sample_image_path(tmp_path):
    """Create a sample image file for testing."""
    # Create a minimal valid PNG (1x1 pixel)
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    image_path = tmp_path / "test_image.png"
    image_path.write_bytes(png_data)
    return str(image_path)


class TestAgentInitialization:
    """Test Agent initialization."""

    def test_init_basic(self):
        """Test basic agent initialization."""
        agent = Agent(system_prompt="You are a helper.")
        assert agent.system_prompt == "You are a helper."
        assert agent.model_config is None

    def test_init_with_config(self, mock_model_config):
        """Test agent initialization with model config."""
        agent = Agent(
            system_prompt="You are a helper.",
            model_config=mock_model_config,
        )
        assert agent.system_prompt == "You are a helper."
        assert agent.model_config == mock_model_config

    def test_model_name_from_config(self, mock_model_config):
        """Test model name resolution from config."""
        agent = Agent(
            system_prompt="Test",
            model_config=mock_model_config,
        )
        assert agent.model_name == "test-model"

    def test_model_name_explicit(self, mock_model_config):
        """Test explicit model name override."""
        agent = Agent(
            system_prompt="Test",
            model_config=mock_model_config,
            model_name="override-model",
        )
        assert agent.model_name == "override-model"

    def test_is_claude_model(self):
        """Test Claude model detection."""
        claude_agent = Agent(
            system_prompt="Test",
            model_name="claude-3-opus-20240229",
        )
        assert claude_agent.is_claude_model() is True

        non_claude_agent = Agent(
            system_prompt="Test",
            model_name="gpt-4",
        )
        assert non_claude_agent.is_claude_model() is False


class TestMultimodalContent:
    """Test multimodal content types."""

    def test_text_content(self):
        """Test TextContent creation."""
        content = TextContent(text="Hello world")
        assert content.type == "text"
        assert content.text == "Hello world"

    def test_image_url_content(self):
        """Test ImageUrlContent creation."""
        content = ImageUrlContent(image_url={"url": "data:image/png;base64,abc123"})
        assert content.type == "image_url"
        assert content.image_url["url"] == "data:image/png;base64,abc123"


class TestImageLoading:
    """Test image loading functionality."""

    def test_load_image_png(self, sample_image_path):
        """Test loading PNG image."""
        agent = Agent(system_prompt="Test")
        result = agent._load_image_as_content(sample_image_path)

        assert result is not None
        assert result["type"] == "image_url"
        assert "url" in result["image_url"]
        assert result["image_url"]["url"].startswith("data:image/png;base64,")

    def test_load_image_jpeg(self, tmp_path):
        """Test loading JPEG image."""
        # Create a minimal valid JPEG (simple 1x1 red pixel)
        # This is a valid JPEG file in hex: FFD8 FFE0 0010 4A46 4946 00 0101 0000 01 0001 0000
        # FFD8 is JPEG SOI (Start of Image), FFD9 is EOI (End of Image)
        jpeg_hex = (
            "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c"
            "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27"
            "393d38323c2e333432ffc00011080001000103012200021101031101ffc4001f0000010501010101"
            "0100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d"
            "010203000411050521310612410713227108142832a109233344153b243550619125d13362728290a"
            "07161a283f044582b1c1d1e2f20655578392a2b3c3d3e4f45667778994a5b6c7d8e9f0a1b2c3d4e5f"
            "ffc4001f0100030101010101010101010000000000000102030405060708090a0bffc400b511000201"
            "020404030407050404000102770001020311040521310612410713225108143291a109233344153b2"
            "43550619125d13362728290a07161a283f044582b1c1d1e2f20655578392a2b3c3d3e4f4566777899"
            "4a5b6c7d8e9f0a1b2c3d4e5f0a14ffd9")
        jpeg_data = bytes.fromhex(jpeg_hex)
        image_path = tmp_path / "test.jpg"
        image_path.write_bytes(jpeg_data)

        agent = Agent(system_prompt="Test")
        result = agent._load_image_as_content(str(image_path))

        assert result is not None
        assert result["type"] == "image_url"
        assert result["image_url"]["url"].startswith("data:image/jpeg;base64,")

    def test_load_image_not_found(self):
        """Test handling of non-existent image."""
        agent = Agent(system_prompt="Test")
        result = agent._load_image_as_content("/nonexistent/image.png")

        assert result is None

    def test_load_image_invalid_path(self):
        """Test handling of invalid path."""
        agent = Agent(system_prompt="Test")
        # Pass a directory path instead of file
        result = agent._load_image_as_content("/tmp")

        # Should return None or handle gracefully
        assert result is None or isinstance(result, dict)


class TestRunWithImagePaths:
    """Test run() method with image_paths parameter."""

    @pytest.mark.asyncio
    async def test_run_with_single_image(self, sample_image_path):
        """Test run with image_paths builds multimodal message correctly."""
        agent = Agent(
            system_prompt="You are a vision analyst.",
            model_config=ModelConfig(use_mock=True),
        )

        # Mock _run_with_llm to capture the message
        captured_content = None

        async def mock_run_with_llm(task, **kwargs):
            nonlocal captured_content
            captured_content = task
            return {"status": "success", "data": {"content": "test"}}

        agent._run_with_llm = mock_run_with_llm

        result = await agent.run(
            content="Analyze this image",
            image_paths=[sample_image_path],
        )

        # Verify multimodal content was built
        assert captured_content is not None
        assert isinstance(captured_content, list)

        # Should have image content and text content
        types = [c.get("type") for c in captured_content]
        assert "image_url" in types
        assert "text" in types

    @pytest.mark.asyncio
    async def test_run_with_multiple_images(self, sample_image_path, tmp_path):
        """Test run with multiple images."""
        # Create second image
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        image_path2 = tmp_path / "test_image2.png"
        image_path2.write_bytes(png_data)

        agent = Agent(
            system_prompt="Test",
            model_config=ModelConfig(use_mock=True),
        )

        captured_content = None

        async def mock_run_with_llm(task, **kwargs):
            nonlocal captured_content
            captured_content = task
            return {"status": "success", "data": {"content": "test"}}

        agent._run_with_llm = mock_run_with_llm

        await agent.run(
            content="Compare these images",
            image_paths=[sample_image_path, str(image_path2)],
        )

        # Count image_url entries
        image_count = sum(1 for c in captured_content if c.get("type") == "image_url")
        assert image_count == 2

    @pytest.mark.asyncio
    async def test_run_without_images(self):
        """Test run without image_paths uses string task."""
        agent = Agent(
            system_prompt="Test",
            model_config=ModelConfig(use_mock=True),
        )

        captured_content = None

        async def mock_run_with_llm(task, **kwargs):
            nonlocal captured_content
            captured_content = task
            return {"status": "success", "data": {"content": "test"}}

        agent._run_with_llm = mock_run_with_llm

        await agent.run(content="Simple text task")

        # Should be a string, not a list
        assert isinstance(captured_content, str)
        assert captured_content == "Simple text task"

    async def test_run_with_llm_surfaces_plan_handoff_trace(self, mock_model_config):
        """LLM path should treat needs_plan as a successful, structured stop."""
        agent = Agent(
            system_prompt="Test",
            model_config=mock_model_config,
        )
        mocked_result = InteractiveRuntimeResult(
            content="Need a plan",
            reasoning="",
            stop_reason=RuntimeStopReason.NEEDS_PLAN,
            turn_count=1,
            turns=[],
            usage={},
            snapshot=InteractiveRuntimeSnapshot(),
            steps=[],
            plan_handoff=PlanHandoffProposal(
                reason="Need a DAG",
                goal="Ship feature",
                planning_context="Found multiple dependent steps",
                evidence_summary="Need staged execution",
                suggested_next_step="Create a plan",
            ),
        )

        with patch("gptase.agents.runtime.AgentRuntime.run",
                   new=AsyncMock(return_value=mocked_result)):
            result = await agent._run_with_llm(
                "Ship feature",
                allow_plan_handoff=True,
                handoff_description="Ship feature",
            )

        assert result["status"] == "success"
        assert result["trace"]["runtime"]["stop_reason"] == "needs_plan"
        assert result["trace"]["runtime"]["plan_handoff"]["reason"] == "Need a DAG"
