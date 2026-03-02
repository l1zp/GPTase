"""Agent orchestrator for coordinating multiple agents."""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from gptase.core.config import FrameworkConfig
from gptase.core.logging import setup_logging

from .base import BaseAgent
from .markdown_agent import MarkdownAgentFactory


class AgentOrchestrator:
    """Central orchestrator for managing multiple agents and task execution."""

    def __init__(self, config: FrameworkConfig):
        self.config = config
        self.agents: Dict[str, BaseAgent] = {}
        self.logger = logging.getLogger(__name__)
        self.model_manager = None
        self.memory_manager = None

        setup_logging(config.log_level)
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Initialize all agents."""
        from gptase.agents.markdown_agent import MarkdownAgentFactory
        from gptase.memory.manager import MemoryManager
        from gptase.models.model import Model
        self.model_manager = Model()
        self.memory_manager = MemoryManager(config=self.config.memory)

        agent_factory = MarkdownAgentFactory()
        self.agents = {}

        # Auto-discover available agents from config/agents/*.md
        available_agents = agent_factory.list_available_agents()
        self.logger.info("Discovered %d agent definitions: %s", len(available_agents),
                         available_agents)

        for agent_id in available_agents:
            try:
                # Use MarkdownAgentFactory for all agents
                agent = agent_factory.create_agent(
                    agent_id,
                    self.memory_manager,
                    model_manager=self.model_manager,
                )
                self.agents[agent_id] = agent
                self.logger.info("Initialized agent: %s", agent_id)
            except Exception as e:
                self.logger.warning(
                    "Failed to initialize agent %s: %s. Skipping.",
                    agent_id,
                    e,
                )

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using the agent orchestrator."""
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
        """Create an error result dict."""
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
                "capabilities": agent.capabilities,
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
            "capabilities": agent.capabilities,
            "status": "active",
        } for agent_id, agent in self.agents.items()]

    async def get_agent_memory(self, agent_id: str) -> Dict[str, Any]:
        """Get memory summary for a specific agent."""
        if self.memory_manager:
            summary = await self.memory_manager.create_memory_summary(agent_id)
            return {
                "status":
                "success",
                "summary":
                summary,
                "total_memories":
                summary.get("conversation_count", 0) + summary.get("task_count", 0),
            }
        return {
            "status": "success",
            "summary": f"No memory manager configured for {agent_id}",
            "total_memories": 0,
        }

    async def shutdown(self) -> None:
        """Shutdown all agents gracefully."""
        self.logger.info("Shutting down agent orchestrator...")

        # Shutdown agents
        for agent in self.agents.values():
            await agent.shutdown()

        self.logger.info("Agent orchestrator shutdown complete")
