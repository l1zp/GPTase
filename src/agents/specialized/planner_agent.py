"""PlannerAgent wrapper for delegation pattern.

This agent delegates to PlanningTool for 5-phase planning workflow.
"""

import logging
from typing import Any, Dict, Optional

from src.agents.base import BaseAgent
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_SUCCESS
from src.tools.planner_tool import PlanningTool

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """Agent for 5-phase planning workflow.

    This agent delegates to PlanningTool to implement structured planning
    for complex tasks, particularly enzyme design workflows.

    Capabilities:
    - Requirement analysis and clarification
    - Multi-step workflow design
    - Resource and risk assessment
    - Interactive plan refinement
    - Plan generation and validation

    The agent follows a delegation pattern:
    Agent (thin orchestrator) → Tool (business logic) → ModelManager (LLM)
    """

    AGENT_NAME = "planner"

    def __init__(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager,
    ):
        """Initialize PlannerAgent.

        Args:
            agent_id: Unique identifier for this agent.
            memory_manager: MemoryManager instance.
            tool_registry: ToolRegistry instance.
            model_manager: ModelManager instance for LLM operations.
        """
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
            capabilities=[
                "requirement_analysis",
                "workflow_design",
                "resource_estimation",
                "multi_phase_planning",
                "interactive_planning",
            ],
        )
        self.model_manager = model_manager

    async def process_task(
        self,
        task: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process planning task.

        Args:
            task: Task dictionary containing:
                - task_description: Task description (for new plans)
                - plan_id: Existing plan ID (to continue)
                - phase: Current phase number (1-5)
                - user_input: User input/feedback for current phase
            session_id: Session ID for tracking.
            agent_id: Agent ID for tracking.
            step_id: Session step ID for tracking.

        Returns:
            Dictionary with:
                - status: STATUS_SUCCESS or STATUS_ERROR
                - data: Planning results with plan_id, phase, and status
        """
        try:
            # Extract task parameters
            task_description = task.get("task_description", "")
            plan_id = task.get("plan_id", "")
            phase = task.get("phase", 1)
            user_input = task.get("user_input", "")

            # Validate input
            if not task_description and not plan_id:
                return {
                    "status": STATUS_ERROR,
                    "data": {
                        "error": "Either task_description or plan_id is required"
                    },
                }

            logger.info(
                f"Planning task: phase={phase}, "
                f"plan_id={plan_id or 'new'}, "
                f"description={task_description[:50] if task_description else 'N/A'}")

            # Create tool with tracking
            planner = PlanningTool(
                model_manager=self.model_manager,
                agent_id=agent_id or self.agent_id,
                session_id=session_id,
                step_id=step_id,
            )

            # Execute planning phase
            result = await planner.execute(
                task_description=task_description,
                plan_id=plan_id,
                phase=phase,
                user_input=user_input,
            )

            if result.status == "error":
                return {
                    "status": STATUS_ERROR,
                    "data": {
                        "error": result.error
                    },
                }

            # Return success with plan data
            return {
                "status": STATUS_SUCCESS,
                "data": result.data,
            }

        except Exception as e:
            logger.error(f"Planning task failed: {e}", exc_info=True)
            return {
                "status": STATUS_ERROR,
                "data": {
                    "error": str(e)
                },
            }
