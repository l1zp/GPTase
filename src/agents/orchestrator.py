"""Agent orchestrator for coordinating multiple agents."""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

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
        "enzyme_design_extractor",
        "vision_image_analyzer",
        "enzyme_extraction_summary",
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
        from src.agents.specialized.executor_agent import ExecutorAgent
        from src.agents.specialized.planner_agent import PlannerAgent
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
                # Use Python class instances for planner and executor
                if agent_id == "planner":
                    agent = PlannerAgent(
                        agent_id=agent_id,
                        memory_manager=self.memory_manager,
                        tool_registry=self.tool_registry,
                        model_manager=self.model_manager,
                    )
                elif agent_id == "executor":
                    agent = ExecutorAgent(
                        agent_id=agent_id,
                        memory_manager=self.memory_manager,
                        tool_registry=self.tool_registry,
                        model_manager=self.model_manager,
                        orchestrator=self,
                    )
                else:
                    # Use MarkdownAgentFactory for other agents
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
            # Check if this is a plan execution task (only if not in planning mode)
            plan_id = task.get("plan_id")
            use_planner = task.get("use_planner", False)

            # If use_planner is True, continue planning workflow even with plan_id
            if use_planner and "planner" in self.agents:
                return await self._run_planning_workflow(task_id, task)

            # Otherwise, if plan_id is present, execute the plan
            if plan_id:
                return await self._execute_plan(task_id, plan_id)

            # Default: run standard phases
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

    async def _run_planning_workflow(self, task_id: str,
                                     task: Dict[str, Any]) -> Dict[str, Any]:
        """Run complete 5-phase planning workflow.

        Args:
            task_id: Unique task identifier.
            task: Task dictionary with planning parameters.

        Returns:
            Result dictionary with planning outcomes.
        """
        self.logger.info(f"Starting 5-phase planning workflow for task: {task_id}")

        plan_id = task.get("plan_id", "")
        phase = task.get("phase", 1)
        user_input = task.get("user_input", "")

        # Build planning task
        planning_task = {
            "task_description": task.get("description", ""),
            "plan_id": plan_id,
            "phase": phase,
            "user_input": user_input,
        }

        # Execute planning phase
        planner = self.agents.get("planner")
        if not planner:
            return self._error_result(task_id, "Planner agent not available")

        phase_result = await planner.process_task(planning_task)

        if phase_result.get("status") != "success":
            return self._error_result(
                task_id,
                phase_result.get("data", {}).get("error", "Planning failed"))

        plan_data = phase_result.get("data", {})

        # If plan is ready to execute, offer to run it
        if plan_data.get("ready_to_execute"):
            final_plan_id = plan_data.get("plan_id")
            self.logger.info(f"Plan {final_plan_id} approved and ready for execution")

            return {
                "task_id":
                task_id,
                "status":
                "success",
                "plan_id":
                final_plan_id,
                "ready_to_execute":
                True,
                "next_steps": [
                    f"Plan saved to data/plans/{final_plan_id}.json",
                    "Execute with: execute_task({'plan_id': '" + final_plan_id + "'})",
                ],
                "timestamp":
                datetime.now().isoformat(),
            }

        # Otherwise, return phase results for continuation
        next_phase = plan_data.get("next_phase")
        return {
            "task_id":
            task_id,
            "status":
            "success",
            "plan_id":
            plan_data.get("plan_id"),
            "current_phase":
            phase,
            "next_phase":
            next_phase,
            "phase_result":
            plan_data.get("phase_result"),
            "instructions":
            (f"Continue to phase {next_phase}" if next_phase else "Planning complete"),
            "timestamp":
            datetime.now().isoformat(),
        }

    async def _execute_plan(self, task_id: str, plan_id: str) -> Dict[str, Any]:
        """Execute a finalized plan.

        Args:
            task_id: Unique task identifier.
            plan_id: Plan ID to execute.

        Returns:
            Result dictionary with execution outcomes.
        """
        self.logger.info(f"Executing plan: {plan_id}")

        executor = self.agents.get("executor")
        if not executor:
            return self._error_result(task_id, "Executor agent not available")

        # Build execution task
        execution_task = {
            "plan_id": plan_id,
        }

        # Execute plan
        exec_result = await executor.process_task(execution_task)

        if exec_result.get("status") != "success":
            return self._error_result(
                task_id,
                exec_result.get("data", {}).get("error", "Execution failed"),
            )

        execution_data = exec_result.get("data", {})
        summary = execution_data.get("execution_summary", {})

        return {
            "task_id": task_id,
            "plan_id": plan_id,
            "status": summary.get("status", "unknown"),
            "execution_summary": summary,
            "step_results": execution_data.get("step_results", []),
            "timestamp": datetime.now().isoformat(),
        }

    async def _execute_phase(self, task: Dict[str, Any], plan_result: Dict[str, Any],
                             description: str) -> Dict[str, Any]:
        """Execute the task if planning was successful.

        Args:
            task: Task specification.
            plan_result: Result from planning phase.
            description: Task description.

        Returns:
            Execution phase result.
        """
        # Check if plan_id is available
        plan_id = None
        if "data" in plan_result:
            plan_id = plan_result["data"].get("plan_id")

        if plan_id:
            # Execute the plan
            return await self._execute_plan(task.get("id", "task"), plan_id)

        # Fallback to original behavior
        plan_valid = (plan_result.get("status") == "success" and "plan" in plan_result)
        if plan_valid:
            return await self.agents["executor"].process_task(task)
        return {"status": "error", "error": "Planning failed"}
