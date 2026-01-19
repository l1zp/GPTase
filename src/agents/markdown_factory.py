"""Factory for creating agents from markdown definitions."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agents.markdown_agent import MarkdownAgent
from src.agents.markdown_parser import AgentDefinition
from src.agents.markdown_parser import MarkdownParser
from src.core.exceptions import AgentInitializationError

logger = logging.getLogger(__name__)


class MarkdownAgentFactory:
    """Factory for creating agents from markdown definitions.

  Replaces the old YAML-based AgentFactory with markdown-based system.
  """

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize factory with config directory.

    Args:
        config_dir: Directory containing .md agent definitions.
                   Defaults to 'config/agents/'
    """
        self.parser = MarkdownParser(config_dir)
        self._definitions_cache: Dict[str, AgentDefinition] = {}

    def load_definition(self, agent_id: str) -> AgentDefinition:
        """Load agent definition from markdown file.

    Args:
        agent_id: Agent identifier (filename without .md).

    Returns:
        Parsed AgentDefinition.

    Raises:
        AgentInitializationError: If file not found or invalid.
    """
        if agent_id in self._definitions_cache:
            return self._definitions_cache[agent_id]

        md_file = self.parser.config_dir / f"{agent_id}.md"

        if not md_file.exists():
            raise AgentInitializationError(f"Agent markdown file not found: {md_file}")

        try:
            definition = self.parser.parse_file(md_file)
            self._definitions_cache[agent_id] = definition
            logger.info(f"Loaded agent definition for '{agent_id}' from {md_file}")
            return definition
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to parse agent definition for '{agent_id}': {e}") from e

    def create_agent(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager: Optional[Any] = None,
    ) -> MarkdownAgent:
        """Create agent instance from markdown definition.

    Args:
        agent_id: Agent identifier.
        memory_manager: Memory manager instance.
        tool_registry: Tool registry instance.
        model_manager: Optional Model instance.

    Returns:
        Initialized MarkdownAgent.

    Raises:
        AgentInitializationError: If creation fails.
    """
        definition = self.load_definition(agent_id)

        try:
            agent = MarkdownAgent(
                definition=definition,
                memory_manager=memory_manager,
                tool_registry=tool_registry,
                model_manager=model_manager,
            )
            logger.info(f"Created agent '{agent_id}' "
                        f"with capabilities: {definition.capabilities}")
            return agent
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to create agent '{agent_id}': {e}") from e

    def create_agents(
        self,
        agent_ids: List[str],
        memory_manager,
        tool_registry,
        model_manager: Optional[Any] = None,
    ) -> Dict[str, MarkdownAgent]:
        """Create multiple agent instances.

    Args:
        agent_ids: List of agent identifiers.
        memory_manager: Memory manager for all agents.
        tool_registry: Tool registry for all agents.
        model_manager: Optional Model for LLM agents.

    Returns:
        Dictionary mapping agent_id to MarkdownAgent instances.

    Raises:
        AgentInitializationError: If any agent creation fails.
    """
        agents = {}
        for agent_id in agent_ids:
            agents[agent_id] = self.create_agent(agent_id, memory_manager,
                                                 tool_registry, model_manager)
        return agents

    def list_available_agents(self) -> List[str]:
        """List all available agent definitions.

    Returns:
        List of agent IDs (filenames without .md).
    """
        return list(self.parser.discover_agents().keys())

    def clear_cache(self) -> None:
        """Clear the definitions cache."""
        self._definitions_cache.clear()
