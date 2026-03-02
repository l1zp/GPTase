"""Markdown-based agent system with unified parser, factory, and agent implementation.

This module provides a complete system for defining and creating agents from markdown files.
It combines parsing, factory creation, and agent execution in a single module.
"""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.core.exceptions import AgentInitializationError
from src.models.model import Model

logger = logging.getLogger(__name__)

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class AgentDefinition:
    """Parsed agent definition from markdown.

    Attributes:
        agent_id: Unique identifier for the agent.
        capabilities: List of agent capabilities.
        requires_model: Whether agent needs LLM access.
        model_role: Model role to use.
        tools: List of tools the agent can use.
        description: Human-readable description.
        system_prompt: System prompt for LLM.
        task_processing: Instructions for task processing.
        output_format: Expected output format.
        examples: Optional few-shot examples.
        temperature: LLM temperature override.
        max_tokens: Token limit override.
        timeout: Task timeout in seconds.
        subagents: Optional list of subagent IDs this agent can delegate to.
    """

    agent_id: str
    capabilities: List[str]
    requires_model: bool
    model_role: str
    tools: List[str]
    description: str
    system_prompt: Optional[str]
    task_processing: str
    output_format: str
    examples: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    timeout: Optional[int]
    subagents: Optional[List[str]] = None


# ============================================================================
# Markdown Parser
# ============================================================================


class MarkdownParser:
    """Parses agent definitions from markdown files."""

    # Pattern for HTML comment markers: <!-- @key: value -->
    # Using [\s\S]+? to match across multiple lines
    MARKER_PATTERN = re.compile(r'@(\w+):\s*([\s\S]+?)(?=\n\s*@|-->)')

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the parser.

        Args:
            config_dir: Directory containing .md agent definitions.
                       Defaults to 'config/agents/'
        """
        if config_dir is None:
            config_dir = Path(
                __file__).resolve().parent.parent.parent / "config" / "agents"
        self.config_dir = Path(config_dir)

    def parse_file(self, md_path: Path) -> tuple[AgentDefinition, Dict[str, Any]]:
        """Parse a markdown file into AgentDefinition and tool definitions.

        Args:
            md_path: Path to markdown file.

        Returns:
            Tuple of (AgentDefinition, tool_definitions_dict).

        Raises:
            ValueError: If file cannot be parsed.
        """
        content = md_path.read_text()
        return self.parse_content(content, md_path.stem)

    def parse_content(self, content: str,
                      agent_id: str) -> tuple[AgentDefinition, Dict[str, Any]]:
        """Parse markdown content into AgentDefinition and tool definitions.

        Args:
            content: Markdown content.
            agent_id: Default agent ID (used if not in markers).

        Returns:
            Tuple of (AgentDefinition, tool_definitions_dict).

        Raises:
            ValueError: If content is invalid.
        """
        # Extract markers
        markers = self._extract_markers(content)

        # Remove marker lines for section parsing
        content_clean = self.MARKER_PATTERN.sub('', content)

        # Parse sections
        sections = self._parse_sections(content_clean)

        # Parse inline tool definitions
        tool_definitions = self._parse_tool_definitions(
            sections.get('Tool Definitions', ''))

        # Build definition
        definition = AgentDefinition(
            agent_id=markers.get('agent_id', agent_id),
            capabilities=self._parse_list(markers.get('capabilities', '')),
            requires_model=markers.get('requires_model', 'true').lower() == 'true',
            model_role=markers.get('model_role', 'general'),
            tools=self._parse_list(markers.get('tools', '')),
            description=sections.get('Agent Description', '').strip(),
            system_prompt=sections.get('System Prompt'),
            task_processing=sections.get('Task Processing', '').strip(),
            output_format=sections.get('Output Format', '').strip(),
            examples=sections.get('Examples'),
            temperature=self._parse_float(markers.get('temperature')),
            max_tokens=self._parse_int(markers.get('max_tokens')),
            timeout=self._parse_int(markers.get('timeout')),
            subagents=self._parse_list(markers.get('subagents', '')) or None,
        )

        return definition, tool_definitions

    def _extract_markers(self, content: str) -> Dict[str, str]:
        """Extract all HTML comment markers.

        Args:
            content: Markdown content.

        Returns:
            Dictionary of marker key to value.
        """
        return dict(self.MARKER_PATTERN.findall(content))

    def _parse_sections(self, content: str) -> Dict[str, str]:
        """Parse markdown sections (## headers).

        Args:
            content: Markdown content without markers.

        Returns:
            Dictionary of section name to content.
        """
        sections = {}
        current_section = None
        current_content = []

        for line in content.split('\n'):
            if line.startswith('## '):
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                # Start new section
                current_section = line[3:].strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _parse_list(self, value: str) -> List[str]:
        """Parse comma-separated list.

        Handles both comma-separated strings and [item1, item2] format.

        Args:
            value: Comma-separated string or bracketed list.

        Returns:
            List of non-empty items.
        """
        if not value:
            return []

        # Remove surrounding whitespace
        value = value.strip()

        # Handle bracketed list format: [item1, item2]
        if value.startswith('[') and value.endswith(']'):
            value = value[1:-1]

        # Split by comma and clean up
        items = [item.strip().strip('\'"') for item in value.split(',') if item.strip()]
        return items

    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """Parse optional float.

        Args:
            value: String value to parse.

        Returns:
            Float or None if invalid/empty.
        """
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Parse optional int.

        Args:
            value: String value to parse.

        Returns:
            Int or None if invalid/empty.
        """
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _parse_json(self, value: Optional[str]) -> Optional[Dict[str, Any]]:
        """Parse optional JSON string.

        Args:
            value: JSON string to parse.

        Returns:
            Parsed dict or None if invalid/empty.
        """
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in value: {value[:50]}...")
            return None

    def _parse_tool_definitions(self, content: str) -> Dict[str, Any]:
        """Parse inline tool definitions from Tool Definitions section.

        Args:
            content: Content of the Tool Definitions section.

        Returns:
            Dictionary mapping tool names to their definitions.
        """
        if not content:
            return {}

        # Extract JSON from code block
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if not json_match:
            return {}

        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid tool definitions JSON: {e}")
            return {}

    def discover_agents(self) -> Dict[str, tuple[AgentDefinition, Dict[str, Any]]]:
        """Discover and parse all .md agent files.

        Returns:
            Dictionary mapping agent_id to (AgentDefinition, tool_definitions).
        """
        agents = {}
        if not self.config_dir.exists():
            logger.warning(f"Agent config directory not found: {self.config_dir}")
            return agents

        for md_file in self.config_dir.glob("*.md"):
            try:
                definition, tool_defs = self.parse_file(md_file)
                agents[definition.agent_id] = (definition, tool_defs)
                logger.info(f"Discovered agent '{definition.agent_id}' from {md_file}")
            except Exception as e:
                logger.warning(f"Failed to parse {md_file}: {e}")

        return agents


# ============================================================================
# Agent Factory
# ============================================================================


class MarkdownAgentFactory:
    """Factory for creating agents from markdown definitions."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize factory with config directory.

        Args:
            config_dir: Directory containing .md agent definitions.
                       Defaults to 'config/agents/'
        """
        self.parser = MarkdownParser(config_dir)
        self._definitions_cache: Dict[str, AgentDefinition] = {}
        self._tool_defs_cache: Dict[str, Dict[str, Any]] = {}

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
            definition, tool_defs = self.parser.parse_file(md_file)
            self._definitions_cache[agent_id] = definition
            self._tool_defs_cache[agent_id] = tool_defs
            logger.info(f"Loaded agent definition for '{agent_id}' from {md_file}")
            return definition
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to parse agent definition for '{agent_id}': {e}") from e

    def create_agent(
        self,
        agent_id: str,
        memory_manager,
        model_manager: Optional[Model] = None,
        enable_delegation: bool = False,
    ) -> 'MarkdownAgent':
        """Create agent instance from markdown definition.

        Args:
            agent_id: Agent identifier.
            memory_manager: Memory manager instance.
            model_manager: Optional Model instance.
            enable_delegation: Whether to enable Task tool for subagent delegation.

        Returns:
            Initialized MarkdownAgent.

        Raises:
            AgentInitializationError: If creation fails.
        """
        definition = self.load_definition(agent_id)

        # Add Task tool if delegation is enabled
        if enable_delegation and "Task" not in definition.tools:
            definition.tools.append("Task")
            logger.info(f"Enabled delegation for agent '{agent_id}' - added Task tool")

        try:
            agent = MarkdownAgent(
                definition=definition,
                memory_manager=memory_manager,
                model_manager=model_manager,
            )
            logger.info(f"Created agent '{agent_id}' "
                        f"with capabilities: {definition.capabilities}"
                        f" (delegation={enable_delegation})")
            return agent
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to create agent '{agent_id}': {e}") from e

    def create_agents(
        self,
        agent_ids: List[str],
        memory_manager,
        model_manager: Optional[Model] = None,
        enable_delegation: bool = False,
    ) -> Dict[str, 'MarkdownAgent']:
        """Create multiple agent instances.

        Args:
            agent_ids: List of agent identifiers.
            memory_manager: Memory manager for all agents.
            model_manager: Optional Model for LLM agents.
            enable_delegation: Whether to enable Task tool for subagent delegation.

        Returns:
            Dictionary mapping agent_id to MarkdownAgent instances.

        Raises:
            AgentInitializationError: If any agent creation fails.
        """
        agents = {}
        for agent_id in agent_ids:
            agents[agent_id] = self.create_agent(
                agent_id,
                memory_manager,
                tool_registry,
                model_manager,
                enable_delegation=enable_delegation,
            )
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
        self._tool_defs_cache.clear()

    def get_sdk_agent_definitions(
        self,
        exclude_agent_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get SDK-compatible agent definitions for subagent delegation.

        This method creates a dictionary of agent definitions that can be
        passed to SDK's ClaudeAgentOptions.agents for subagent delegation.

        Args:
            exclude_agent_ids: Optional list of agent IDs to exclude
                             (e.g., the calling agent to avoid self-delegation).

        Returns:
            Dictionary mapping agent_id to SDK AgentDefinition.
        """
        exclude_ids = set(exclude_agent_ids or [])

        # Try to import SDK types
        try:
            from claude_agent_sdk import AgentDefinition as SDKAgentDefinition
        except ImportError:
            logger.warning(
                "claude-agent-sdk not installed, returning empty definitions")
            return {}

        sdk_definitions = {}

        for agent_id in self.list_available_agents():
            if agent_id in exclude_ids:
                continue

            try:
                gptase_def = self.load_definition(agent_id)

                # Map model role to SDK model
                model_map = {
                    "general": "sonnet",
                    "reasoning": "opus",
                    "fast": "haiku",
                }

                sdk_def = SDKAgentDefinition(
                    description=gptase_def.description or f"Agent {agent_id}",
                    prompt=gptase_def.system_prompt or "",
                    tools=gptase_def.tools,
                    model=model_map.get(gptase_def.model_role.lower(), "sonnet"),
                )

                sdk_definitions[agent_id] = sdk_def

            except Exception as e:
                logger.warning(f"Failed to create SDK definition for {agent_id}: {e}")

        return sdk_definitions


# ============================================================================
# Markdown Agent
# ============================================================================


class MarkdownAgent(BaseAgent):
    """Universal agent that executes tasks based on markdown definitions.

    This single class can represent any agent type defined in markdown format.
    It delegates execution to the unified Agent class which auto-routes
    between Claude SDK and custom LLM loop based on model configuration.
    """

    def __init__(
        self,
        definition: AgentDefinition,
        memory_manager,
        model_manager: Optional[Model] = None,
    ):
        """Initialize MarkdownAgent with parsed definition.

        Args:
            definition: Parsed AgentDefinition from markdown.
            memory_manager: Memory manager instance.
            model_manager: Optional Model instance (required if requires_model=True).

        Raises:
            ValueError: If requires_model=True but no model_manager provided.
        """
        super().__init__(
            agent_id=definition.agent_id,
            memory_manager=memory_manager,
            capabilities=definition.capabilities,
        )
        self.definition = definition
        self.model_manager = model_manager

        # Validate model requirement
        if definition.requires_model and model_manager is None:
            raise ValueError(
                f"Agent '{definition.agent_id}' requires model_manager but none provided"
            )

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task by delegating to the unified Agent class.

        The Agent class automatically routes to Claude SDK or custom
        LLM loop based on the configured model.

        Args:
            task: Task dictionary with task-specific data.

        Returns:
            Dictionary with status and result/error.
        """
        await self.update_status(STATUS_SUCCESS)
        try:
            from src.agents.agent import Agent

            # Build system prompt
            system_prompt = (self.definition.system_prompt
                             or self._build_default_system_prompt())

            # Resolve skill paths from agent definition tools
            skills = self._resolve_skills()

            # Get model config from model_manager if available
            model_config = None
            if self.model_manager:
                model_config = self.model_manager.default_config

            agent = Agent(
                system_prompt=system_prompt,
                skills=skills,
                model_config=model_config,
            )

            # Build prompt and run
            prompt = self._build_user_prompt(task)
            result = await agent.run(prompt)

            # Add pipeline metadata
            if result.get("status") == "success":
                data = result.get("data", {})
                if isinstance(data, dict):
                    if "pipeline" not in data:
                        data["pipeline"] = {
                            "steps": [],
                            "validations": [],
                            "errors": []
                        }
                    data["pipeline"]["steps"].append({
                        "name": "agent_processing",
                        "agent_id": self.agent_id,
                        "status": "completed",
                    })

            return result

        except Exception as e:
            logger.error(f"Task processing failed for {self.agent_id}: {e}")
            return {
                "status": STATUS_ERROR,
                "error": str(e),
                "agent_id": self.agent_id,
            }

    def _resolve_skills(self) -> List[str]:
        """Resolve skill file paths from agent definition.

        Maps tool names to skill paths if a corresponding skill exists.

        Returns:
            List of skill file paths.
        """
        skills = []
        skill_dirs = [
            Path("skills"),
            Path(".claude/skills"),
        ]

        for tool_name in (self.definition.tools or []):
            for skill_dir in skill_dirs:
                skill_path = skill_dir / tool_name / "SKILL.md"
                if skill_path.exists():
                    skills.append(str(skill_path))
                    break

        return skills

    def _build_default_system_prompt(self) -> str:
        """Build default system prompt if none specified.

        Returns:
            Default system prompt string.
        """
        prompt = f"""You are {self.agent_id}, an AI agent with capabilities: {', '.join(self.capabilities)}.

{self.definition.description}

Task Processing:
{self.definition.task_processing}

Output Format:
{self.definition.output_format}
"""

        return prompt

    def _build_user_prompt(self, task: Dict[str, Any]) -> str:
        """Build user prompt from task.

        Args:
            task: Task dictionary.

        Returns:
            User prompt string.
        """
        # Format task as readable text
        task_text = json.dumps(task, indent=2)

        prompt = f"""Task: {task.get('description', 'Process the following data')}

Input Data:
{task_text}

Process this task according to your instructions and return the result in the specified format.
"""

        # Add examples if available
        if self.definition.examples:
            prompt += f"\n\nExamples:\n{self.definition.examples}"

        return prompt

    def _parse_output(self, content: str) -> Any:
        """Parse LLM output, handling JSON extraction.

        Args:
            content: Raw LLM response content.

        Returns:
            Parsed output (dict or raw text).
        """
        content = content.strip()

        # Try direct JSON parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Return as plain text if not JSON
        return {"response": content}

    def _extract_tool_parameters(self, task: Dict[str, Any],
                                 tool_name: str) -> Dict[str, Any]:
        """Extract parameters for a tool from task.

        Args:
            task: Task dictionary.
            tool_name: Name of the tool.

        Returns:
            Tool parameters dictionary.
        """
        # Try 'parameters' key first, fallback to entire task
        return task.get("parameters", task)
