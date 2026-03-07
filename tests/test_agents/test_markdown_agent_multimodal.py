"""Tests for agent task processing and markdown agent parsing."""

import pytest

from gptase.agents.base import Agent
from gptase.agents.base import AgentDefinition

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def basic_definition():
    """Basic agent definition for testing."""
    return AgentDefinition(
        name="test-agent",
        description="Test agent for unit tests",
        tools=["Read", "Grep"],
        system_prompt="You are a test agent.",
    )


# ============================================================================
# AgentDefinition Tests
# ============================================================================


class TestAgentDefinition:
    """Tests for AgentDefinition dataclass."""

    def test_basic_definition(self, basic_definition):
        """Test basic agent definition creation."""
        assert basic_definition.name == "test-agent"
        assert basic_definition.description == "Test agent for unit tests"
        assert basic_definition.tools == ["Read", "Grep"]
        assert basic_definition.system_prompt == "You are a test agent."

    def test_agent_id_property(self, basic_definition):
        """Test that agent_id is an alias for name."""
        assert basic_definition.agent_id == basic_definition.name


# ============================================================================
# Agent._parse_markdown Tests
# ============================================================================


class TestParseMarkdown:
    """Tests for Agent._parse_markdown."""

    def test_parse_content_with_frontmatter(self):
        """Test parsing markdown with YAML frontmatter."""
        content = """---
name: my-agent
description: My test agent
tools: Read, Grep, Bash
---

You are a helpful assistant.
"""
        definition = Agent._parse_markdown(content, "default")

        assert definition.name == "my-agent"
        assert definition.description == "My test agent"
        assert definition.tools == ["Read", "Grep", "Bash"]
        assert "You are a helpful assistant." in definition.system_prompt

    def test_parse_content_minimal(self):
        """Test parsing minimal markdown."""
        content = """---
name: minimal
---
Just a prompt.
"""
        definition = Agent._parse_markdown(content, "default")

        assert definition.name == "minimal"
        assert definition.description == ""
        assert definition.tools == []

    def test_parse_content_invalid_frontmatter(self):
        """Test that invalid frontmatter raises error."""
        content = """---
invalid yaml: [unclosed
---
Content here.
"""
        with pytest.raises(ValueError, match="Invalid YAML"):
            Agent._parse_markdown(content, "default")


# ============================================================================
# Agent Task Processing Tests
# ============================================================================


class TestAgentTaskProcessing:
    """Tests for Agent task dict processing methods."""

    def test_initialization_from_definition(self, basic_definition):
        """Test agent creation from an AgentDefinition."""
        agent = Agent(
            system_prompt=basic_definition.system_prompt,
            agent_id=basic_definition.name,
        )
        assert agent.agent_id == basic_definition.name
        assert agent.system_prompt == basic_definition.system_prompt

    def test_extract_image_paths_single(self):
        """Test extraction of single image path."""
        agent = Agent(system_prompt="Test")
        task = {
            "description": "Analyze image",
            "image_path": "/path/to/image.png",
        }
        paths = agent._extract_image_paths(task)
        assert paths == ["/path/to/image.png"]

    def test_extract_image_paths_multiple(self):
        """Test extraction of multiple image paths."""
        agent = Agent(system_prompt="Test")
        task = {
            "description": "Analyze images",
            "image_paths": ["/path/to/image1.png", "/path/to/image2.jpg"],
        }
        paths = agent._extract_image_paths(task)
        assert paths == ["/path/to/image1.png", "/path/to/image2.jpg"]

    def test_extract_image_paths_deduplication(self):
        """Test that duplicate paths are removed."""
        agent = Agent(system_prompt="Test")
        task = {
            "image_path": "/path/to/image.png",
            "image_paths": ["/path/to/image.png", "/path/to/other.png"],
        }
        paths = agent._extract_image_paths(task)
        assert paths == ["/path/to/image.png", "/path/to/other.png"]

    def test_build_user_prompt_basic(self):
        """Test basic prompt building."""
        agent = Agent(system_prompt="Test")
        task = {"description": "Do something", "data": "test data"}
        prompt = agent._build_user_prompt(task)
        assert "Do something" in prompt
        assert "test data" in prompt

    def test_build_user_prompt_excludes_images(self):
        """Test that images are excluded from prompt when include_images=False."""
        agent = Agent(system_prompt="Test")
        task = {
            "description": "Analyze image",
            "image_path": "/path/to/image.png",
            "data": "test data",
        }
        prompt = agent._build_user_prompt(task, include_images=False)
        assert "Analyze image" in prompt
        assert "test data" in prompt
        assert "image_path" not in prompt

    def test_build_user_prompt_includes_images_when_enabled(self):
        """Test that images are included in prompt when include_images=True."""
        agent = Agent(system_prompt="Test")
        task = {
            "description": "Analyze image",
            "image_path": "/path/to/image.png",
        }
        prompt = agent._build_user_prompt(task, include_images=True)
        assert "Images:" in prompt
        assert "/path/to/image.png" in prompt


# ============================================================================
# Agent.from_markdown Tests
# ============================================================================


class TestFromMarkdown:
    """Tests for Agent.from_markdown."""

    def test_from_markdown_by_name(self):
        """Test creating agent by name via from_markdown."""
        agent = Agent.from_markdown("code-analyzer")

        assert agent.agent_id == "code-analyzer"
        assert "Read" in agent.tools
        assert len(agent.system_prompt) > 0

    def test_discover_agents(self):
        """Test discovering available agents."""
        agents = Agent.discover_agents()

        # Should find agents in .claude/agents/
        assert len(agents) > 0
