"""Central orchestrator for managing multiple agents and task execution."""

from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from gptase.agents import Agent
from gptase.agents import AgentTask
from gptase.tools.base import get_tool_registry
from gptase.tools.handlers import DelegateTaskTool
from gptase.utils.config import FrameworkConfig

logger = logging.getLogger(__name__)

# Default directory for agent markdown definitions
_DEFAULT_CONFIG_DIR = Path(
    __file__).resolve().parent.parent.parent / ".claude" / "agents"


class AgentOrchestrator(Agent):
    """Central orchestrator for managing multiple agents and task execution.

    Acts as an Agent itself, capable of delegating tasks to its pool of agents.
    """

    def __init__(self, config: FrameworkConfig):
        self.config = config
        self.agents: Dict[str, Agent] = {}
        self.model_manager = None
        self.memory_manager = None
        self.logger = logger

        self._initialize_agents()

        # Default fallback attributes for the orchestrator agent
        system_prompt = "You are the central Agent Orchestrator. Your role is to delegate tasks."
        tools = ["DelegateTask"]

        # Attempt to load from .claude/agents/orchestrator.md if it exists
        orchestrator_md = _DEFAULT_CONFIG_DIR / "orchestrator.md"
        if orchestrator_md.exists():
            try:
                definition = Agent._parse_markdown(orchestrator_md.read_text(),
                                                   orchestrator_md.stem)
                system_prompt = definition.system_prompt
                tools = definition.tools
            except Exception as e:
                logger.warning(
                    f"Failed to parse orchestrator.md, using minimal default: {e}")

        # Initialize the base Agent class
        super().__init__(system_prompt=system_prompt,
                         tools=tools,
                         model_config=self.model_manager.get_config_for_agent("auto")
                         if self.model_manager else None,
                         agent_id="auto")

        # Register the DelegateTaskTool specially for this orchestrator
        registry = get_tool_registry()
        delegate_tool = DelegateTaskTool(orchestrator=self)
        registry.register(delegate_tool, allowed_agents=["auto"])

    def _initialize_agents(self) -> None:
        """Initialize all agents."""
        from gptase.memory.manager import MemoryManager
        from gptase.models.model import Model
        self.model_manager = Model()
        self.memory_manager = MemoryManager(config=self.config.memory)

        # Auto-discover available agents from .claude/agents/*.md
        self.agents = self._discover_agents()
        self.logger.info(
            "Discovered %d agents: %s",
            len(self.agents),
            list(self.agents.keys()),
        )

    def _discover_agents(self) -> Dict[str, Agent]:
        """Discover all agent markdown files and create Agent instances.

        Scans .claude/agents/ directory for .md files with YAML frontmatter.

        Returns:
            Dictionary mapping agent name to Agent instance.
        """
        config_dir = _DEFAULT_CONFIG_DIR
        agents: Dict[str, Agent] = {}

        if not config_dir.exists():
            logger.warning("Agent config directory not found: %s", config_dir)
            return agents

        for md_file in config_dir.glob("*.md"):
            if "_archived" in str(md_file):
                continue
            try:
                agent = Agent.from_markdown(md_file, model_manager=self.model_manager)
                agents[agent.agent_id] = agent
                logger.info("Discovered agent '%s' from %s", agent.agent_id, md_file)
            except Exception as e:
                logger.warning("Failed to load agent from %s: %s", md_file, e)

        return agents

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using the agent orchestrator.

        Args:
            task: Task dictionary with description and optional agent_id.
        """
        task_id = task.get("id", f"task_{datetime.now().timestamp()}")
        self.logger.info("Starting task execution: %s", task_id)

        try:
            description = str(task.get("description", "")).strip()
            if not description:
                return self._error_result(task_id, "Task description is required")

            # Convert task dict to AgentTask
            task_obj = AgentTask.from_dict(task)

            # If user explicitly requested a specific agent id, route directly without orchestrator LLM loop
            agent_id = task.get("agent_id")
            if agent_id and agent_id != "auto" and agent_id in self.agents:
                self.logger.info(
                    f"Directly routing task to requested agent: {agent_id}")
                result = await self.agents[agent_id].process_task(task_obj)
                return {
                    "task_id": task_id,
                    "status": result.get("status", "success"),
                    "data": result.get("data"),
                    "agent_id": agent_id,
                    "timestamp": datetime.now().isoformat(),
                }

            # Otherwise, use the Orchestrator's standard LLM loop to figure out what to do
            # The LLM may use DelegateTask to call other agents.
            self.logger.info("Routing task through Orchestrator LLM loop.")

            # Use process_task from the Agent base class
            result = await self.process_task(task_obj)
            return {
                "task_id": task_id,
                "status": result.get("status", "success"),
                "data": result.get("data"),
                "agent_id": "auto",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error("Task execution failed: %s", e)
            return self._error_result(task_id, str(e))

    def _error_result(self, task_id: str, error: str) -> Dict[str, Any]:
        """Create an error result dict.

        Args:
            task_id: Task identifier for the error result.
            error: Error message to include.
        """
        return {
            "task_id": task_id,
            "status": "failed",
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }

    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        agents_info = {}
        for agent_id, agent in self.agents.items():
            agents_info[agent_id] = {
                "agent_id": agent_id,
                "type": agent.__class__.__name__,
                "status": "active",
            }

        memory_usage = await self.memory_manager.get_usage()

        status = {
            "timestamp": datetime.now().isoformat(),
            "agents": agents_info,
            "memory": memory_usage,
        }

        return status

    async def list_available_agents(self) -> List[Dict[str, Any]]:
        """List all available agents."""
        return [{
            "agent_id": agent_id,
            "type": agent.__class__.__name__,
            "status": "active",
        } for agent_id, agent in self.agents.items()]

    async def get_agent_memory(self, agent_id: str) -> Dict[str, Any]:
        """Get memory summary for a specific agent.

        Args:
            agent_id: Agent identifier to get memory for.
        """
        if self.memory_manager:
            summary = await self.memory_manager.create_summary(
                context=f"agent:{agent_id}")
            return {"agent_id": agent_id, "memory_summary": summary}
        return {"agent_id": agent_id, "memory_summary": None}
