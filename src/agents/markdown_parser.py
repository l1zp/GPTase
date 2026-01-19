"""Parser for markdown-based agent definitions."""

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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


class MarkdownParser:
    """Parses agent definitions from markdown files."""

    # Pattern for HTML comment markers: <!-- @key: value -->
    MARKER_PATTERN = re.compile(r'<!--\s*@(\w+):\s*(.+?)\s*-->')

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

    def parse_file(self, md_path: Path) -> AgentDefinition:
        """Parse a markdown file into AgentDefinition.

    Args:
        md_path: Path to markdown file.

    Returns:
        Parsed AgentDefinition.

    Raises:
        ValueError: If file cannot be parsed.
    """
        content = md_path.read_text()
        return self.parse_content(content, md_path.stem)

    def parse_content(self, content: str, agent_id: str) -> AgentDefinition:
        """Parse markdown content into AgentDefinition.

    Args:
        content: Markdown content.
        agent_id: Default agent ID (used if not in markers).

    Returns:
        Parsed AgentDefinition.

    Raises:
        ValueError: If content is invalid.
    """
        # Extract markers
        markers = self._extract_markers(content)

        # Remove marker lines for section parsing
        content_clean = self.MARKER_PATTERN.sub('', content)

        # Parse sections
        sections = self._parse_sections(content_clean)

        # Build definition
        return AgentDefinition(
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
        )

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

    Args:
        value: Comma-separated string.

    Returns:
        List of non-empty items.
    """
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]

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

    def discover_agents(self) -> Dict[str, AgentDefinition]:
        """Discover and parse all .md agent files.

    Returns:
        Dictionary mapping agent_id to AgentDefinition.
    """
        agents = {}
        if not self.config_dir.exists():
            logger.warning(f"Agent config directory not found: {self.config_dir}")
            return agents

        for md_file in self.config_dir.glob("*.md"):
            try:
                definition = self.parse_file(md_file)
                agents[definition.agent_id] = definition
                logger.info(f"Discovered agent '{definition.agent_id}' from {md_file}")
            except Exception as e:
                logger.warning(f"Failed to parse {md_file}: {e}")

        return agents
