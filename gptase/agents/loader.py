"""Agent loader: parse .md definitions and create Agent instances.

This module provides utilities for loading agent definitions from markdown
files with YAML frontmatter (Claude Code Agent format) and instantiating
Agent objects from those definitions.
"""

from dataclasses import dataclass
from dataclasses import field
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

import yaml

from gptase.agents.agent import Agent
from gptase.core.exceptions import AgentInitializationError
from gptase.models.model import Model

logger = logging.getLogger(__name__)

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class AgentDefinition:
    """Parsed agent definition from Claude Code Agent format.

    Attributes:
        name: Unique identifier for the agent.
        description: Human-readable description of what the agent does.
        tools: List of tools the agent can use.
        model: Model to use (opus, sonnet, haiku).
        system_prompt: System prompt content (body of the markdown file).
    """

    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    model: str = "sonnet"
    system_prompt: str = ""

    @property
    def agent_id(self) -> str:
        """Alias for name, for backward compatibility."""
        return self.name


# ============================================================================
# Agent Parser
# ============================================================================


class AgentParser:
    """Parses agent definitions from markdown files with YAML frontmatter.

    Expected format:
    ---
    name: agent-name
    description: What this agent does
    tools: Tool1, Tool2
    model: opus|sonnet|haiku
    ---
    [System prompt content in markdown]
    """

    # Pattern for YAML frontmatter
    FRONTMATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the parser.

        Args:
            config_dir: Directory containing .md agent definitions.
                       Defaults to '.claude/agents/'
        """
        if config_dir is None:
            config_dir = Path(
                __file__).resolve().parent.parent.parent / ".claude" / "agents"
        self.config_dir = Path(config_dir)

    def parse_file(self, md_path: Path) -> AgentDefinition:
        """Parse a markdown file into AgentDefinition.

        Args:
            md_path: Path to markdown file.

        Returns:
            AgentDefinition instance.

        Raises:
            ValueError: If file cannot be parsed.
        """
        content = md_path.read_text()
        return self.parse_content(content, md_path.stem)

    def parse_content(self, content: str, default_name: str) -> AgentDefinition:
        """Parse markdown content into AgentDefinition.

        Args:
            content: Markdown content with YAML frontmatter.
            default_name: Default agent name if not specified in frontmatter.

        Returns:
            AgentDefinition instance.

        Raises:
            ValueError: If content is invalid.
        """
        # Extract frontmatter
        frontmatter_match = self.FRONTMATTER_PATTERN.match(content)
        if not frontmatter_match:
            raise ValueError(f"Invalid agent format: missing YAML frontmatter. "
                             f"Expected '---\\nname: ...\\n---'")

        frontmatter_text = frontmatter_match.group(1)
        body_content = content[frontmatter_match.end():].strip()

        # Parse YAML frontmatter
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}") from e

        if not isinstance(frontmatter, dict):
            raise ValueError("YAML frontmatter must be a dictionary")

        # Extract fields
        name = frontmatter.get("name", default_name)
        description = frontmatter.get("description", "")
        tools = frontmatter.get("tools", [])
        model = frontmatter.get("model", "sonnet")

        # Normalize tools to list
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",") if t.strip()]

        # Validate model
        valid_models = {"opus", "sonnet", "haiku"}
        if model.lower() not in valid_models:
            logger.warning(
                f"Invalid model '{model}' for agent '{name}', defaulting to 'sonnet'")
            model = "sonnet"

        return AgentDefinition(
            name=name,
            description=description,
            tools=tools,
            model=model.lower(),
            system_prompt=body_content,
        )

    def discover_agents(self) -> Dict[str, AgentDefinition]:
        """Discover and parse all .md agent files.

        Returns:
            Dictionary mapping agent name to AgentDefinition.
        """
        agents = {}
        if not self.config_dir.exists():
            logger.warning(f"Agent config directory not found: {self.config_dir}")
            return agents

        for md_file in self.config_dir.glob("*.md"):
            # Skip archived files
            if "_archived" in str(md_file):
                continue

            try:
                definition = self.parse_file(md_file)
                agents[definition.name] = definition
                logger.info(f"Discovered agent '{definition.name}' from {md_file}")
            except Exception as e:
                logger.warning(f"Failed to parse {md_file}: {e}")

        return agents

    def find_agent_file(self, name: str) -> Optional[Path]:
        """Find agent file by name.

        Supports both hyphenated and underscore formats.

        Args:
            name: Agent name (with hyphens or underscores).

        Returns:
            Path to agent file, or None if not found.
        """
        possible_names = [
            name,
            name.replace("_", "-"),
            name.replace("-", "_"),
        ]

        for n in possible_names:
            md_file = self.config_dir / f"{n}.md"
            if md_file.exists():
                return md_file

        return None


# ============================================================================
# Agent Factory
# ============================================================================


class MarkdownAgentFactory:
    """Factory for creating agents from markdown definitions."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize factory with config directory.

        Args:
            config_dir: Directory containing .md agent definitions.
                       Defaults to '.claude/agents/'
        """
        self.parser = AgentParser(config_dir)
        self._definitions_cache: Dict[str, AgentDefinition] = {}

    def load_definition(self, name: str) -> AgentDefinition:
        """Load agent definition from markdown file.

        Args:
            name: Agent name (supports hyphens or underscores).

        Returns:
            Parsed AgentDefinition.

        Raises:
            AgentInitializationError: If file not found or invalid.
        """
        # Normalize name for cache lookup
        normalized_name = name.replace("_", "-")

        if normalized_name in self._definitions_cache:
            return self._definitions_cache[normalized_name]

        # Find the agent file
        md_file = self.parser.find_agent_file(name)

        if not md_file:
            raise AgentInitializationError(
                f"Agent '{name}' not found in {self.parser.config_dir}")

        try:
            definition = self.parser.parse_file(md_file)
            self._definitions_cache[definition.name] = definition
            logger.info(
                f"Loaded agent definition for '{definition.name}' from {md_file}")
            return definition
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to parse agent definition for '{name}': {e}") from e

    def create_agent(
        self,
        name: str,
        memory_manager=None,
        model_manager: Optional[Model] = None,
        enable_delegation: bool = False,
    ) -> Agent:
        """Create agent instance from markdown definition.

        Args:
            name: Agent name.
            memory_manager: Unused; kept for API compatibility.
            model_manager: Optional Model instance.
            enable_delegation: Whether to enable Task tool for subagent delegation.

        Returns:
            Initialized Agent.

        Raises:
            AgentInitializationError: If creation fails.
        """
        definition = self.load_definition(name)

        # Add Task tool if delegation is enabled
        if enable_delegation and "Task" not in definition.tools:
            definition.tools.append("Task")
            logger.info(f"Enabled delegation for agent '{name}' - added Task tool")

        try:
            model_config = model_manager.get_config_for_agent(
                definition.name) if model_manager else None
            agent = Agent(
                system_prompt=definition.system_prompt,
                model_config=model_config,
                agent_id=definition.name,
            )
            logger.info(f"Created agent '{name}' with tools: {definition.tools}")
            return agent
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to create agent '{name}': {e}") from e

    def create_agents(
        self,
        names: List[str],
        memory_manager=None,
        model_manager: Optional[Model] = None,
        enable_delegation: bool = False,
    ) -> Dict[str, Agent]:
        """Create multiple agent instances.

        Args:
            names: List of agent names.
            memory_manager: Memory manager for all agents.
            model_manager: Optional Model for LLM agents.
            enable_delegation: Whether to enable Task tool for subagent delegation.

        Returns:
            Dictionary mapping agent name to Agent instances.
        """
        return {
            name:
            self.create_agent(name,
                              memory_manager,
                              model_manager,
                              enable_delegation=enable_delegation)
            for name in names
        }

    def list_available_agents(self) -> List[str]:
        """List all available agent definitions.

        Returns:
            List of agent names.
        """
        return list(self.parser.discover_agents().keys())

    def clear_cache(self) -> None:
        """Clear the definitions cache."""
        self._definitions_cache.clear()

    def get_sdk_agent_definitions(
        self,
        exclude_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get SDK-compatible agent definitions for subagent delegation.

        Args:
            exclude_names: Optional list of agent names to exclude.

        Returns:
            Dictionary mapping agent name to SDK AgentDefinition.
        """
        exclude_set = set(exclude_names or [])

        try:
            from claude_agent_sdk import AgentDefinition as SDKAgentDefinition
        except ImportError:
            logger.warning(
                "claude-agent-sdk not installed, returning empty definitions")
            return {}

        sdk_definitions = {}

        for name in self.list_available_agents():
            if name in exclude_set:
                continue

            try:
                definition = self.load_definition(name)

                sdk_def = SDKAgentDefinition(
                    description=definition.description or f"Agent {name}",
                    prompt=definition.system_prompt or "",
                    tools=definition.tools,
                    model=definition.model,
                )

                sdk_definitions[name] = sdk_def

            except Exception as e:
                logger.warning(f"Failed to create SDK definition for {name}: {e}")

        return sdk_definitions
