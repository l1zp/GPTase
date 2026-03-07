"""Central orchestrator for managing multiple agents and task execution."""

from datetime import datetime
import logging
from typing import Any, Dict, List

from gptase.agents.base import Agent
from gptase.utils.config import FrameworkConfig

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Central orchestrator for managing multiple agents and task execution."""

    def __init__(self, config: FrameworkConfig):
        self.config = config
        self.agents: Dict[str, Agent] = {}
        self.logger = logging.getLogger(__name__)
        self.model_manager = None
        self.memory_manager = None

        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Initialize all agents."""
        from gptase.memory.manager import MemoryManager
        from gptase.models.model import Model
        self.model_manager = Model()
        self.memory_manager = MemoryManager(config=self.config.memory)

        # Auto-discover available agents from .claude/agents/*.md
        self.agents = Agent.discover_agents(model_manager=self.model_manager)
        self.logger.info(
            "Discovered %d agents: %s",
            len(self.agents),
            list(self.agents.keys()),
        )

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

            # Route to appropriate agent based on task
            agent_id = task.get("agent_id")
            if agent_id and agent_id in self.agents:
                result = await self.agents[agent_id].process_task(task)
                return {
                    "task_id": task_id,
                    "status": result.get("status", "success"),
                    "data": result.get("data"),
                    "agent_id": agent_id,
                    "timestamp": datetime.now().isoformat(),
                }

            # Default: run with first available agent
            for aid, agent in self.agents.items():
                result = await agent.process_task(task)
                return {
                    "task_id": task_id,
                    "status": result.get("status", "success"),
                    "data": result.get("data"),
                    "agent_id": aid,
                    "timestamp": datetime.now().isoformat(),
                }

            return self._error_result(task_id, "No agents available")

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
