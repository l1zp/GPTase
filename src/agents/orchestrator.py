"""
Agent orchestrator for coordinating multiple agents
"""

import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, List

from src.core.config import FrameworkConfig
from src.core.logging import setup_logging

from .base import BaseAgent
from .specialized import EnzymeDesignAgent
from .specialized import ExecutorAgent
from .specialized import LLMEnzymeExtractorAgent
from .specialized import MemoryManagerAgent
from .specialized import PlannerAgent
from .specialized import ToolManagerAgent


class AgentOrchestrator:
    """Central orchestrator for managing multiple agents and task execution."""

    def __init__(self, config: FrameworkConfig):
        self.config = config
        self.agents: Dict[str, BaseAgent] = {}
        self.logger = logging.getLogger(__name__)

        # Setup logging
        setup_logging(config.log_level)

        # Initialize agents
        self._initialize_agents()

    def _initialize_agents(self):
        """Initialize all agents."""
        from src.memory.manager import MemoryManager
        from src.models.manager import ModelManager
        from src.models.types import ModelProvider
        from src.models.types import ModelRole
        from src.tools.implementations import CalculatorTool
        from src.tools.implementations import CodeExecutorTool
        from src.tools.implementations import CodeWriterTool
        from src.tools.implementations import DocumentLoaderTool
        from src.tools.implementations import FileManagerTool
        from src.tools.implementations import WebSearchTool
        from src.tools.registry import ToolRegistry

        base_model_config = self.config.get_model_config_for_role(ModelRole.GENERAL)
        model_config = (base_model_config.model_copy(deep=True) if hasattr(
            base_model_config, "model_copy") else base_model_config.copy())
        if not model_config.api_key and model_config.provider == ModelProvider.OPENAI:
            model_config.provider = ModelProvider.CUSTOM

        model_manager = ModelManager(default_config=model_config)

        memory_manager = MemoryManager(config=self.config.memory)
        tool_registry = ToolRegistry()
        tool_registry.register_tools([
            CodeWriterTool(),
            CodeExecutorTool(),
            FileManagerTool(),
            WebSearchTool(),
            CalculatorTool(),
            DocumentLoaderTool(),
        ])
        self.model_manager = model_manager
        self.memory_manager = memory_manager

        # Create specialized agents
        self.agents = {
            "planner":
            PlannerAgent("planner", memory_manager, tool_registry),
            "executor":
            ExecutorAgent("executor", memory_manager, tool_registry),
            "tool_manager":
            ToolManagerAgent("tool_manager", memory_manager, tool_registry),
            "memory_manager":
            MemoryManagerAgent("memory_manager", memory_manager, tool_registry),
            "enzyme":
            LLMEnzymeExtractorAgent("enzyme", memory_manager, tool_registry,
                                    model_manager),
            "enzyme_design":
            EnzymeDesignAgent("enzyme_design", memory_manager, tool_registry),
        }

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using the agent orchestrator."""
        try:
            task_id = task.get("id", f"task_{datetime.now().timestamp()}")
            self.logger.info(f"Starting task execution: {task_id}")
            description = str(task.get("description", "")).strip()
            self.logger.debug(f"Description: '{description}'")
            if not description:
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": "Task description is required",
                    "timestamp": datetime.now().isoformat(),
                }

            # Planning phase
            self.logger.info("Starting planning phase...")
            plan_result = await self.agents["planner"].process_task(task)

            # Execution phase
            self.logger.info("Starting execution phase...")
            if (plan_result["status"] == "success" and "plan" in plan_result
                    and description):
                exec_result = await self.agents["executor"].process_task(task)
            else:
                exec_result = {"status": "error", "error": "Planning failed"}

            # Tool management phase
            self.logger.info("Starting tool management phase...")
            tool_result = await self.agents["tool_manager"].process_task(task)

            # Memory management phase
            self.logger.info("Starting memory management phase...")
            memory_result = await self.agents["memory_manager"].process_task(task)

            # Compile results
            result = {
                "task_id":
                task_id,
                "status": ("success" if description
                           and exec_result["status"] == "success" else "failed"),
                "phases": {
                    "planning": plan_result,
                    "execution": exec_result,
                    "tool_management": tool_result,
                    "memory": memory_result,
                },
                "summary":
                f"Task {task_id} completed with status: {exec_result['status']}",
                "timestamp":
                datetime.now().isoformat(),
            }

            self.logger.info(f"Task {task_id} completed: {result['status']}")
            return result

        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            return {
                "task_id": task.get("id", "unknown"),
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": {
                agent_id: {
                    "agent_id": agent_id,
                    "type": agent.__class__.__name__,
                    "capabilities": agent.capabilities,
                    "status": "active",
                }
                for agent_id, agent in self.agents.items()
            },
            "tools": {
                "total_tools": len(self.agents["tool_manager"].tools)
            },
            "memory": {
                **(await self.memory_manager.get_usage())
            },
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

    async def shutdown(self):
        """Shutdown all agents gracefully."""
        self.logger.info("Shutting down agent orchestrator...")
        for agent_id, agent in self.agents.items():
            await agent.shutdown()
        self.logger.info("Agent orchestrator shutdown complete")
