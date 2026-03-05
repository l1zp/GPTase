"""Tests for agent task processing and markdown agent format."""

import pytest

from gptase.agents.agent import Agent
from gptase.agents.loader import AgentDefinition
from gptase.agents.loader import AgentParser
from gptase.agents.loader import MarkdownAgentFactory

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
        model="sonnet",
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
        assert basic_definition.model == "sonnet"
        assert basic_definition.system_prompt == "You are a test agent."

    def test_agent_id_property(self, basic_definition):
        """Test that agent_id is an alias for name."""
        assert basic_definition.agent_id == basic_definition.name


# ============================================================================
# AgentParser Tests
# ============================================================================


class TestAgentParser:
    """Tests for AgentParser."""

    def test_parse_content_with_frontmatter(self):
        """Test parsing markdown with YAML frontmatter."""
        content = """---
name: my-agent
description: My test agent
tools: Read, Grep, Bash
model: opus
color: blue
---

You are a helpful assistant.
"""
        parser = AgentParser()
        definition = parser.parse_content(content, "default")

        assert definition.name == "my-agent"
        assert definition.description == "My test agent"
        assert definition.tools == ["Read", "Grep", "Bash"]
        assert definition.model == "opus"
        assert definition.color == "blue"
        assert "You are a helpful assistant." in definition.system_prompt

    def test_parse_content_minimal(self):
        """Test parsing minimal markdown."""
        content = """---
name: minimal
---
Just a prompt.
"""
        parser = AgentParser()
        definition = parser.parse_content(content, "default")

        assert definition.name == "minimal"
        assert definition.description == ""
        assert definition.tools == []
        assert definition.model == "sonnet"  # default

    def test_parse_content_invalid_frontmatter(self):
        """Test that invalid frontmatter raises error."""
        content = """---
invalid yaml: [unclosed
---
Content here.
"""
        parser = AgentParser()

        with pytest.raises(ValueError, match="Invalid YAML"):
            parser.parse_content(content, "default")


# ============================================================================
# MarkdownAgent Tests
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
# MarkdownAgentFactory Tests
# ============================================================================


class TestMarkdownAgentFactory:
    """Tests for MarkdownAgentFactory."""

    def test_list_available_agents(self):
        """Test listing available agents."""
        factory = MarkdownAgentFactory()
        agents = factory.list_available_agents()

        # Should find agents in .claude/agents/
        assert len(agents) > 0

    def test_load_definition(self):
        """Test loading an agent definition."""
        factory = MarkdownAgentFactory()

        # Load code-analyzer (converted from code_analyzer)
        definition = factory.load_definition("code-analyzer")

        assert definition.name == "code-analyzer"
        assert "Read" in definition.tools
        assert definition.model == "opus"
