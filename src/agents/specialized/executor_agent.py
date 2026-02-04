"""ExecutorAgent wrapper for delegation pattern.

This agent delegates to ExecutorTool for plan execution.
"""

import logging
from typing import Any, Dict, Optional

from src.agents.base import BaseAgent
from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.tools.executor_tool import ExecutorTool

logger = logging.getLogger(__name__)


class ExecutorAgent(BaseAgent):
    """Agent for executing finalized plans.

    This agent delegates to ExecutorTool to execute plans created
    by the PlannerAgent, coordinating multiple agents in the process.

    Capabilities:
    - Load and validate finalized plans
    - Execute workflow steps sequentially
    - Coordinate agent orchestration
    - Aggregate execution results
    - Handle errors gracefully

    The agent follows a delegation pattern:
    Agent (thin orchestrator) → Tool (business logic) → Other Agents
    """

    AGENT_NAME = "executor"

    def __init__(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager,
        orchestrator: Optional[AgentOrchestrator] = None,
    ):
        """Initialize ExecutorAgent.

        Args:
            agent_id: Unique identifier for this agent.
            memory_manager: MemoryManager instance.
            tool_registry: ToolRegistry instance.
            model_manager: ModelManager instance (may not be needed).
            orchestrator: Optional AgentOrchestrator for agent access.
        """
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
            capabilities=[
                "plan_execution",
                "agent_orchestration",
                "result_aggregation",
                "workflow_coordination",
            ],
        )
        self.model_manager = model_manager
        self.orchestrator = orchestrator

    async def process_task(
        self,
        task: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process execution task.

        Args:
            task: Task dictionary containing:
                - plan_id: Plan ID to execute (required)
            session_id: Session ID for tracking.
            agent_id: Agent ID for tracking.
            step_id: Session step ID for tracking.

        Returns:
            Dictionary with:
                - status: STATUS_SUCCESS or STATUS_ERROR
                - data: Execution results with summary and step outcomes
        """
        try:
            # Extract task parameters
            plan_id = task.get("plan_id", "")

            if not plan_id:
                return {
                    "status": STATUS_ERROR,
                    "data": {
                        "error": "plan_id is required for execution"
                    },
                }

            logger.info(f"Executing plan: {plan_id}")

            # Create tool with tracking and orchestrator
            executor = ExecutorTool(
                model_manager=self.model_manager,
                agent_orchestrator=self.orchestrator,
                agent_id=agent_id or self.agent_id,
                session_id=session_id,
                step_id=step_id,
            )

            # Execute plan
            result = await executor.execute(plan_id=plan_id)

            if result.status == "error":
                return {
                    "status": STATUS_ERROR,
                    "data": {
                        "error": result.error
                    },
                }

            # Return success with execution data
            return {
                "status": STATUS_SUCCESS,
                "data": result.data,
            }

        except Exception as e:
            logger.error(f"Execution task failed: {e}", exc_info=True)
            return {
                "status": STATUS_ERROR,
                "data": {
                    "error": str(e)
                },
            }
