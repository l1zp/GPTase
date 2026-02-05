"""Executor tool for executing finalized plans.

This tool loads plans from data/plans/{plan_id}.json and executes
the workflow steps with agent orchestration.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.base import TrackingMixin

logger = logging.getLogger(__name__)

# Constants
_PLANS_DIR = Path("data/plans")
_STATUS_PENDING = "pending"
_STATUS_IN_PROGRESS = "in_progress"
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"


class ExecutionResult(BaseModel):
    """Result of a workflow step execution."""

    step_id: Union[str, int]
    status: str
    agent: str
    action: str
    outputs: Dict[str, Any]
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    cached: bool = False  # Whether result was loaded from cache


class ExecutorTool(TrackingMixin, BaseTool):
    """Tool for executing finalized plans.

    This tool loads a plan from disk and executes each workflow step
    by calling the appropriate agent. It aggregates results and provides
    a comprehensive execution report. Supports both sequential and parallel
    step execution.
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
        """Execute a finalized plan with data flow support."""
        try:
            plan_id = kwargs.get("plan_id")
            if not plan_id:
                return ToolResult(status="error", error="plan_id is required")

            # Load plan
            plan = self._load_plan(plan_id)
            if plan.get("status") != "approved" and not plan_id.endswith("_sop"):
                return ToolResult(status="error", error=f"Plan {plan_id} not approved")

            # Initialize execution context with inputs from kwargs
            context = {
                "input_text": kwargs.get("text", ""),
                "document_path": kwargs.get("document_path", ""),
                "source_file": kwargs.get("source_file", ""),
                "output_dir": kwargs.get("output_dir", "")  # For caching
            }

            workflow = plan.get("workflow", [])
            execution_results = []

            for item in workflow:
                # Check if this is a parallel group
                if "parallel" in item:
                    parallel_steps = item["parallel"]
                    # Execute parallel steps
                    parallel_results = await self._execute_parallel_steps(
                        parallel_steps, plan_id, context)
                    execution_results.extend(parallel_results)

                    # Check if any parallel step failed
                    if any(r.status == _STATUS_FAILED for r in parallel_results):
                        break
                else:
                    # Sequential step
                    result = await self._execute_step(item, plan_id, context)
                    execution_results.append(result)
                    if result.status == _STATUS_FAILED:
                        break

            summary = self._aggregate_results(execution_results)
            return ToolResult(status="success",
                              data={
                                  "plan_id":
                                  plan_id,
                                  "execution_summary":
                                  summary,
                                  "step_results":
                                  [result.model_dump() for result in execution_results]
                              })

        except Exception as e:
            logger.error(f"Plan execution failed: {e}", exc_info=True)
            return ToolResult(status="error", error=str(e))

    async def _execute_parallel_steps(self, steps: List[Dict[str, Any]], plan_id: str,
                                      context: Dict[str, Any]) -> List[ExecutionResult]:
        """Execute multiple steps in parallel.

        Args:
            steps: List of step definitions to execute in parallel.
            plan_id: Plan ID for execution tracking.
            context: Execution context with variable bindings.

        Returns:
            List of ExecutionResult objects.
        """

        async def execute_single_step(step_data):
            return await self._execute_step(step_data, plan_id, context)

        # Run all steps in parallel
        results = await asyncio.gather(*[execute_single_step(step) for step in steps],
                                       return_exceptions=True)

        # Handle exceptions
        execution_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                step_data = steps[i]
                execution_results.append(
                    ExecutionResult(step_id=step_data.get("step_id", i),
                                    status=_STATUS_FAILED,
                                    agent=step_data.get("agent", "unknown"),
                                    action=step_data.get("action", "unknown"),
                                    outputs={},
                                    error=str(result),
                                    started_at=None,
                                    completed_at=None))
            else:
                execution_results.append(result)

        return execution_results

    async def _execute_step(self, step_data: Dict[str, Any], plan_id: str,
                            context: Dict[str, Any]) -> ExecutionResult:
        """Execute a single workflow step with variable substitution and result reuse."""
        from datetime import datetime
        import json
        from pathlib import Path

        step_id = step_data.get("step_id", 0)
        agent_name = step_data.get("agent", "")
        action = step_data.get("action", "")
        raw_inputs = step_data.get("inputs", {})

        # Check if result file already exists
        output_dir = context.get("output_dir", "")
        result_file = None
        if output_dir:
            output_path = Path(output_dir)
            result_file = output_path / f"step_{step_id}_{action}.json"

            if result_file and result_file.exists():
                logger.info(f"[CACHE HIT] Loading existing result: step {step_id}")
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        cached_data = json.load(f)

                    # Restore to context (try different keys)
                    step_outputs = cached_data.get("analysis",
                                                   cached_data.get("data", cached_data))
                    context[f"step{step_id}"] = step_outputs

                    return ExecutionResult(step_id=step_id,
                                           status="completed",
                                           agent=agent_name,
                                           action=action,
                                           outputs=step_outputs,
                                           error=None,
                                           started_at=None,
                                           completed_at=None,
                                           cached=True)
                except Exception as e:
                    logger.warning(
                        f"[CACHE FAIL] Failed to load existing result for step {step_id}: {e}, re-executing"
                    )

        # Resolve variables in inputs
        inputs = self._resolve_variables(raw_inputs, context)

        started_at = datetime.now().isoformat()
        logger.info(f"Executing step {step_id}: {agent_name}.{action}")

        try:
            task = {
                "id": f"{plan_id}_step_{step_id}",
                "description": step_data.get("description", ""),
                "action": action,
                **inputs,
            }

            # Execute via orchestrator
            if self.agent_orchestrator and agent_name in self.agent_orchestrator.agents:
                agent = self.agent_orchestrator.agents[agent_name]
                result = await agent.process_task(task)
            else:
                raise ValueError(f"Agent {agent_name} not available")

            completed_at = datetime.now().isoformat()
            status = _STATUS_COMPLETED if result.get("status") in (
                "success", "completed") else _STATUS_FAILED

            # Store result in context for future steps
            step_data_out = result.get("data", {})
            context[f"step{step_id}"] = step_data_out

            return ExecutionResult(step_id=step_id,
                                   status=status,
                                   agent=agent_name,
                                   action=action,
                                   outputs=step_data_out,
                                   error=result.get("data", {}).get("error")
                                   if status == _STATUS_FAILED else None,
                                   started_at=started_at,
                                   completed_at=completed_at,
                                   cached=False)
        except Exception as e:
            return ExecutionResult(step_id=step_id,
                                   status=_STATUS_FAILED,
                                   agent=agent_name,
                                   action=action,
                                   outputs={},
                                   error=str(e),
                                   started_at=started_at,
                                   completed_at=datetime.now().isoformat(),
                                   cached=False)

    def _resolve_variables(self, inputs: Dict[str, Any],
                           context: Dict[str, Any]) -> Dict[str, Any]:
        """Deep resolve {{variable}} placeholders in input dictionary."""
        resolved = {}
        for k, v in inputs.items():
            if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
                path = v[2:-2].strip()
                # Simple path traversal: "step1.raw_tool_data.tables"
                parts = path.split('.')
                val = context
                try:
                    for part in parts:
                        val = val[part]
                    resolved[k] = val
                except (KeyError, TypeError):
                    logger.warning(f"Could not resolve variable: {v}")
                    resolved[k] = v
            else:
                resolved[k] = v
        return resolved

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
        # For enzyme extraction agents, we expect them to be managed by the orchestrator.
        # If the orchestrator is missing an agent, it's a configuration error.

        # Mapping legacy or specific agent requests to their expert agent implementations
        agent_mapping = {
            "enzyme_kinetics_extractor": "enzyme_kinetics_extractor",
            "enzyme_design_extractor": "enzyme_design_extractor",
            "vision_image_analyzer": "vision_image_analyzer",
        }

        target_agent = agent_mapping.get(agent_name)
        if not target_agent:
            raise ValueError(f"Unsupported expert agent: {agent_name}")

        if self.agent_orchestrator and target_agent in self.agent_orchestrator.agents:
            agent = self.agent_orchestrator.agents[target_agent]
            result = await agent.process_task(task)
            return {"status": result.get("status"), "data": result.get("data")}
        else:
            raise ValueError(
                f"Agent {target_agent} not found in orchestrator. Please ensure it is properly registered."
            )

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
        """Load plan from disk, supporting both dynamic plans and static SOPs."""
        import json

        # 1. Determine search path
        if plan_id.endswith("_sop"):
            # Look in config/sops/ directory
            sop_name = plan_id.replace("_sop", "")
            plan_path = Path("config/sops") / f"{sop_name}.json"
        else:
            # Traditional dynamic plan location
            plan_path = self.plans_dir / f"{plan_id}.json"

        if not plan_path.exists():
            # Fallback check in data/plans if not found in sops
            fallback_path = self.plans_dir / f"{plan_id}.json"
            if fallback_path.exists():
                plan_path = fallback_path
            else:
                raise ValueError(
                    f"Plan or SOP not found: {plan_id} (Checked {plan_path})")

        with open(plan_path, "r") as f:
            return json.load(f)
