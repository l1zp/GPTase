"""Agent system with YAML frontmatter parser for Claude Code Agent format.

This module provides a complete system for defining and creating agents from
markdown files with YAML frontmatter, matching Claude Code Agent specification.
"""

from dataclasses import dataclass
from dataclasses import field
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

import yaml

from gptase.agents.base import BaseAgent
from gptase.core.constants import STATUS_ERROR
from gptase.core.constants import STATUS_SUCCESS
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
        color: Display color for UI purposes.
        system_prompt: System prompt content (body of the markdown file).
    """

    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    model: str = "sonnet"
    color: Optional[str] = None
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
    color: blue
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
        color = frontmatter.get("color")

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
            color=color,
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
        memory_manager,
        model_manager: Optional[Model] = None,
        enable_delegation: bool = False,
    ) -> 'MarkdownAgent':
        """Create agent instance from markdown definition.

        Args:
            name: Agent name.
            memory_manager: Memory manager instance.
            model_manager: Optional Model instance.
            enable_delegation: Whether to enable Task tool for subagent delegation.

        Returns:
            Initialized MarkdownAgent.

        Raises:
            AgentInitializationError: If creation fails.
        """
        definition = self.load_definition(name)

        # Add Task tool if delegation is enabled
        if enable_delegation and "Task" not in definition.tools:
            definition.tools.append("Task")
            logger.info(f"Enabled delegation for agent '{name}' - added Task tool")

        try:
            agent = MarkdownAgent(
                definition=definition,
                memory_manager=memory_manager,
                model_manager=model_manager,
            )
            logger.info(f"Created agent '{name}' with tools: {definition.tools}")
            return agent
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to create agent '{name}': {e}") from e

    def create_agents(
        self,
        names: List[str],
        memory_manager,
        model_manager: Optional[Model] = None,
        enable_delegation: bool = False,
    ) -> Dict[str, 'MarkdownAgent']:
        """Create multiple agent instances.

        Args:
            names: List of agent names.
            memory_manager: Memory manager for all agents.
            model_manager: Optional Model for LLM agents.
            enable_delegation: Whether to enable Task tool for subagent delegation.

        Returns:
            Dictionary mapping agent name to MarkdownAgent instances.
        """
        agents = {}
        for name in names:
            agents[name] = self.create_agent(
                name,
                memory_manager,
                model_manager,
                enable_delegation=enable_delegation,
            )
        return agents

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


# ============================================================================
# Markdown Agent
# ============================================================================


class MarkdownAgent(BaseAgent):
    """Agent that executes tasks based on Claude Code Agent definitions."""

    def __init__(
        self,
        definition: AgentDefinition,
        memory_manager,
        model_manager: Optional[Model] = None,
    ):
        """Initialize MarkdownAgent with parsed definition.

        Args:
            definition: Parsed AgentDefinition.
            memory_manager: Memory manager instance.
            model_manager: Optional Model instance.
        """
        super().__init__(
            agent_id=definition.name,
            memory_manager=memory_manager,
            capabilities=[],  # Claude Code format doesn't have explicit capabilities
        )
        self.definition = definition
        self.model_manager = model_manager

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task by delegating to the unified Agent class.

        Args:
            task: Task dictionary with task-specific data.

        Returns:
            Dictionary with status and result/error.
        """
        await self.update_status(STATUS_SUCCESS)
        try:
            from gptase.agents.agent import Agent

            # Get model config
            model_config = None
            if self.model_manager:
                model_config = self.model_manager.get_config_for_agent(self.agent_id)

            agent = Agent(
                system_prompt=self.definition.system_prompt,
                model_config=model_config,
            )

            # Check for multimodal task (with images)
            image_paths = self._extract_image_paths(task)

            if image_paths:
                prompt = self._build_user_prompt(task, include_images=False)
                result = await agent.run_with_images(prompt, image_paths)
            else:
                prompt = self._build_user_prompt(task)
                result = await agent.run(prompt)

            return result

        except Exception as e:
            logger.error(f"Task processing failed for {self.agent_id}: {e}")
            return {
                "status": STATUS_ERROR,
                "error": str(e),
                "agent_id": self.agent_id,
            }

    def _extract_image_paths(self, task: Dict[str, Any]) -> List[str]:
        """Extract image paths from task."""
        paths = []

        if task.get("image_path"):
            paths.append(task["image_path"])

        if task.get("image_paths"):
            paths.extend(task["image_paths"])

        if task.get("images"):
            for img in task["images"]:
                if isinstance(img, str):
                    paths.append(img)
                elif isinstance(img, dict) and img.get("path"):
                    paths.append(img["path"])

        # Deduplicate
        seen = set()
        return [p for p in paths if not (p in seen or seen.add(p))]

    def _build_user_prompt(self,
                           task: Dict[str, Any],
                           include_images: bool = True) -> str:
        """Build user prompt from task."""
        task_copy = {
            k: v
            for k, v in task.items() if k not in ("image_path", "image_paths", "images")
        }

        task_text = json.dumps(task_copy, indent=2, ensure_ascii=False)

        prompt = f"""Task: {task.get('description', 'Process the following data')}

Input Data:
{task_text}
"""
        if include_images:
            image_paths = self._extract_image_paths(task)
            if image_paths:
                prompt += f"\nImages: {', '.join(image_paths)}\n"

        prompt += "\nProcess this task according to your instructions.\n"
        return prompt
