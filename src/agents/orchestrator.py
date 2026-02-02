"""Agent orchestrator for coordinating multiple agents."""

from datetime import datetime
import logging
from typing import Any, Dict, List

from src.core.config import FrameworkConfig
from src.core.logging import setup_logging

from .base import BaseAgent
from .markdown_agent import MarkdownAgentFactory


class AgentOrchestrator:
    """Central orchestrator for managing multiple agents and task execution."""

    # Agent IDs managed by the orchestrator
    AGENT_IDS = [
        "planner",
        "executor",
        "tool_manager",
        "memory_manager",
        "enzyme_kinetics_extractor",
    ]

    def __init__(self, config: FrameworkConfig):
        self.config = config
        self.agents: Dict[str, BaseAgent] = {}
        self.logger = logging.getLogger(__name__)
        self.model_manager = None
        self.memory_manager = None
        self.tool_registry = None

        setup_logging(config.log_level)
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Initialize all agents."""
        from src.memory.manager import MemoryManager
        from src.models.model import Model
        from src.tools.implementations import CalculatorTool
        from src.tools.implementations import CodeExecutorTool
        from src.tools.implementations import CodeWriterTool
        from src.tools.implementations import DocumentLoaderTool
        from src.tools.implementations import FileManagerTool
        from src.tools.implementations import WebSearchTool
        from src.tools.registry import ToolRegistry

        self.model_manager = Model()
        self.memory_manager = MemoryManager(config=self.config.memory)
        self.tool_registry = ToolRegistry()
        self.tool_registry.register_tools([
            CodeWriterTool(),
            CodeExecutorTool(),
            FileManagerTool(),
            WebSearchTool(),
            CalculatorTool(),
            DocumentLoaderTool(),
        ])

        agent_factory = MarkdownAgentFactory()
        self.agents = {}

        for agent_id in self.AGENT_IDS:
            try:
                agent = agent_factory.create_agent(
                    agent_id,
                    self.memory_manager,
                    self.tool_registry,
                    model_manager=self.model_manager,
                )
                self.agents[agent_id] = agent
                self.logger.info(f"Initialized agent: {agent_id}")
            except Exception as e:
                self.logger.warning(
                    f"Failed to initialize agent {agent_id}: {e}. Skipping.")

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using the agent orchestrator."""
        task_id = task.get("id", f"task_{datetime.now().timestamp()}")
        description = str(task.get("description", "")).strip()

        self.logger.info(f"Starting task execution: {task_id}")

        if not description:
            return self._error_result(task_id, "Task description is required")

        try:
            phases = {}
            phase_agents = {
                "planning": "planner",
                "execution": "executor",
                "tool_management": "tool_manager",
                "memory": "memory_manager",
            }

            for phase_name, agent_id in phase_agents.items():
                if agent_id in self.agents:
                    if phase_name == "execution":
                        phases[phase_name] = await self._execute_phase(
                            task, phases["planning"], description)
                    else:
                        phases[phase_name] = await self.agents[agent_id].process_task(
                            task)
                else:
                    phases[phase_name] = self._skip_result(agent_id)

            exec_status = phases.get("execution", {}).get("status", "skipped")
            status = "success" if exec_status == "success" else "failed"

            result = {
                "task_id": task_id,
                "status": status,
                "phases": phases,
                "summary": f"Task {task_id} completed with status: {status}",
                "timestamp": datetime.now().isoformat(),
            }

            self.logger.info(f"Task {task_id} completed: {status}")
            return result

        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            return self._error_result(task_id, str(e))

    def _skip_result(self, agent_id: str) -> Dict[str, Any]:
        """Create a skipped phase result."""
        return {
            "status": "skipped",
            "message": f"{agent_id.replace('_', ' ').title()} agent not available"
        }

    async def _execute_phase(self, task: Dict[str, Any], plan_result: Dict[str, Any],
                             description: str) -> Dict[str, Any]:
        """Execute the task if planning was successful."""
        plan_valid = (plan_result.get("status") == "success" and "plan" in plan_result)
        if plan_valid:
            return await self.agents["executor"].process_task(task)
        return {"status": "error", "error": "Planning failed"}

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

        return {
            "timestamp": datetime.now().isoformat(),
            "agents": agents_info,
            "tools": {
                "total_tools": len(self.tool_registry.list_tools())
            },
            "memory": memory_usage,
        }

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
        return {
            "status": "success",
            "summary": f"Memory summary for {agent_id}",
            "total_memories": 0,  # Placeholder
        }

    async def shutdown(self) -> None:
        """Shutdown all agents gracefully."""
        self.logger.info("Shutting down agent orchestrator...")
        for agent in self.agents.values():
            await agent.shutdown()
        self.logger.info("Agent orchestrator shutdown complete")
