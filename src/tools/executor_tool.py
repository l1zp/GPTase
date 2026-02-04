"""Executor tool for executing finalized plans.

This tool loads plans from data/plans/{plan_id}.json and executes
the workflow steps with agent orchestration.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.tracking_mixin import TrackingMixin

logger = logging.getLogger(__name__)

# Constants
_PLANS_DIR = Path("data/plans")
_STATUS_PENDING = "pending"
_STATUS_IN_PROGRESS = "in_progress"
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"


class ExecutionResult(BaseModel):
    """Result of a workflow step execution."""

    step_id: int
    status: str
    agent: str
    action: str
    outputs: Dict[str, Any]
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ExecutorTool(TrackingMixin, BaseTool):
    """Tool for executing finalized plans.

    This tool loads a plan from disk and executes each workflow step
    by calling the appropriate agent. It aggregates results and provides
    a comprehensive execution report.
    """

    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters.

        Returns:
            JSON schema for executor tool parameters.
        """
        return {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "Plan ID to execute"
                }
            },
            "required": ["plan_id"]
        }

    def __init__(
        self,
        model_manager,
        agent_orchestrator=None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
        plans_dir: Optional[Path] = None,
    ):
        """Initialize ExecutorTool.

        Args:
            model_manager: ModelManager for LLM operations.
            agent_orchestrator: AgentOrchestrator for agent access.
            agent_id: Agent ID for tracking.
            session_id: Session ID for tracking.
            step_id: Step ID for tracking.
            plans_dir: Directory for plan storage.
        """
        BaseTool.__init__(
            self,
            name="executor",
            description="Execute finalized plans with agent orchestration",
            timeout=600,
        )
        TrackingMixin.__init__(self, agent_id, session_id, step_id)
        self.model_manager = model_manager
        self.agent_orchestrator = agent_orchestrator
        self.plans_dir = plans_dir or _PLANS_DIR

    async def execute(self, **kwargs) -> ToolResult:
        """Execute a finalized plan.

        Args:
            **kwargs: Must include:
                - plan_id: Plan ID to execute

        Returns:
            ToolResult with execution results.
        """
        try:
            plan_id = kwargs.get("plan_id")
            if not plan_id:
                return ToolResult(
                    status="error",
                    error="plan_id is required for execution",
                )

            # Load plan
            plan = self._load_plan(plan_id)

            # Validate plan status
            if plan.get("status") != "approved":
                return ToolResult(
                    status="error",
                    error=f"Plan {plan_id} is not approved for execution. "
                    f"Current status: {plan.get('status')}",
                )

            # Execute workflow steps
            workflow = plan.get("workflow", [])
            execution_results = []

            for step_data in workflow:
                result = await self._execute_step(step_data, plan_id)
                execution_results.append(result)

                # Stop if step failed
                if result.status == _STATUS_FAILED:
                    logger.error(f"Step {result.step_id} failed: {result.error}")
                    break

            # Aggregate results
            summary = self._aggregate_results(execution_results)

            return ToolResult(
                status="success",
                data={
                    "plan_id": plan_id,
                    "execution_summary": summary,
                    "step_results":
                    [result.model_dump() for result in execution_results],
                },
            )

        except Exception as e:
            logger.error(f"Plan execution failed: {e}", exc_info=True)
            return ToolResult(status="error", error=str(e))

    async def _execute_step(self, step_data: Dict[str, Any],
                            plan_id: str) -> ExecutionResult:
        """Execute a single workflow step.

        Args:
            step_data: Step configuration from plan.
            plan_id: Plan ID for tracking.

        Returns:
            ExecutionResult with step outcomes.
        """
        from datetime import datetime

        step_id = step_data.get("step_id", 0)
        agent_name = step_data.get("agent", "")
        action = step_data.get("action", "")
        inputs = step_data.get("inputs", {})

        started_at = datetime.now().isoformat()

        logger.info(f"Executing step {step_id}: {agent_name}.{action} "
                    f"with inputs: {list(inputs.keys())}")

        try:
            # Build task for agent
            task = {
                "id": f"{plan_id}_step_{step_id}",
                "description": step_data.get("description", ""),
                "action": action,
                **inputs,
            }

            # Execute via orchestrator or directly
            if self.agent_orchestrator and agent_name in self.agent_orchestrator.agents:
                agent = self.agent_orchestrator.agents[agent_name]
                result = await agent.process_task(task)
            else:
                # Fallback: try to use tool_registry directly
                result = await self._execute_via_tool(agent_name, action, task)

            completed_at = datetime.now().isoformat()

            # Determine success status
            status = (_STATUS_COMPLETED if result.get("status")
                      in ("success", "completed") else _STATUS_FAILED)

            return ExecutionResult(
                step_id=step_id,
                status=status,
                agent=agent_name,
                action=action,
                outputs=result.get("data", {}),
                error=result.get("error"),
                started_at=started_at,
                completed_at=completed_at,
            )

        except Exception as e:
            completed_at = datetime.now().isoformat()
            logger.error(f"Step {step_id} execution failed: {e}", exc_info=True)

            return ExecutionResult(
                step_id=step_id,
                status=_STATUS_FAILED,
                agent=agent_name,
                action=action,
                outputs={},
                error=str(e),
                started_at=started_at,
                completed_at=completed_at,
            )

    async def _execute_via_tool(self, agent_name: str, action: str,
                                task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute via tool registry as fallback.

        Args:
            agent_name: Agent/tool name.
            action: Action to perform.
            task: Task parameters.

        Returns:
            Result dictionary.

        Raises:
            ValueError: If tool not found.
        """
        # Map agent names to tool names
        tool_mapping = {
            "enzyme_kinetics_extractor": "enzyme_kinetics_extractor",
            "enzyme_design_extractor": "enzyme_design_extractor",
            "vision_image_analyzer": "vision_image_analyzer",
        }

        tool_name = tool_mapping.get(agent_name)
        if not tool_name:
            raise ValueError(f"No tool found for agent: {agent_name}")

        # For enzyme extraction tools, we need to handle them differently
        # since they're specialized tools with specific interfaces
        if agent_name == "enzyme_kinetics_extractor":
            from src.tools.enzyme_kinetics_extractor import EnzymeKineticsExtractorTool

            tool = EnzymeKineticsExtractorTool(
                model_manager=self.model_manager,
                agent_id=self.agent_id,
                session_id=self.session_id,
                step_id=self.step_id,
            )
            result = await tool.execute(
                text=task.get("text", ""),
                source_file=task.get("source_file", ""),
            )
            return {"status": result.status, "data": result.data}

        elif agent_name == "enzyme_design_extractor":
            from src.tools.enzyme_design_extractor import EnzymeDesignExtractorTool

            tool = EnzymeDesignExtractorTool(
                model_manager=self.model_manager,
                agent_id=self.agent_id,
                session_id=self.session_id,
                step_id=self.step_id,
            )
            result = await tool.execute(
                text=task.get("text", ""),
                source_file=task.get("source_file", ""),
            )
            return {"status": result.status, "data": result.data}

        elif agent_name == "vision_image_analyzer":
            from src.tools.vision_image_analyzer import VisionImageAnalyzerTool

            tool = VisionImageAnalyzerTool(
                model_manager=self.model_manager,
                agent_id=self.agent_id,
                session_id=self.session_id,
                step_id=self.step_id,
            )
            result = await tool.execute(
                image_path=task.get("image_path", ""),
                figure_number=task.get("figure_number"),
            )
            return {"status": result.status, "data": result.data}

        else:
            raise ValueError(f"Unsupported agent for direct execution: {agent_name}")

    def _aggregate_results(self,
                           execution_results: List[ExecutionResult]) -> Dict[str, Any]:
        """Aggregate execution results into summary.

        Args:
            execution_results: List of step execution results.

        Returns:
            Summary dictionary.
        """
        total_steps = len(execution_results)
        completed_steps = sum(1 for r in execution_results
                              if r.status == _STATUS_COMPLETED)
        failed_steps = total_steps - completed_steps

        return {
            "total_steps":
            total_steps,
            "completed_steps":
            completed_steps,
            "failed_steps":
            failed_steps,
            "success_rate": (completed_steps / total_steps if total_steps > 0 else 0.0),
            "status": ("success" if failed_steps == 0 else
                       "partial" if completed_steps > 0 else "failed"),
        }

    def _load_plan(self, plan_id: str) -> Dict[str, Any]:
        """Load plan from disk.

        Args:
            plan_id: Plan ID to load.

        Returns:
            Plan dictionary.

        Raises:
            ValueError: If plan file not found.
        """
        import json

        plan_path = self.plans_dir / f"{plan_id}.json"
        if not plan_path.exists():
            raise ValueError(f"Plan not found: {plan_path}")

        with open(plan_path, "r") as f:
            return json.load(f)
