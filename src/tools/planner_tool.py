"""Planning tool for complex enzyme design workflow planning.

This tool implements a 5-phase planning workflow:
1. Initial Understanding - Ask clarifying questions
2. Design - Create detailed implementation approach
3. Review - Present plan and collect feedback
4. Final Plan - Generate executable workflow JSON
5. Exit - Request final approval before execution
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic import Field

from src.tools.base import BaseTool
from src.tools.base import ToolResult
from src.tools.prompts import ENZYME_DESIGN_PLANNING_CONTEXT
from src.tools.prompts import PLANNING_PHASE_1_PROMPT
from src.tools.prompts import PLANNING_PHASE_2_PROMPT
from src.tools.prompts import PLANNING_PHASE_3_PROMPT
from src.tools.prompts import PLANNING_PHASE_4_PROMPT
from src.tools.prompts import PLANNING_PHASE_5_PROMPT
from src.tools.tracking_mixin import TrackingMixin

logger = logging.getLogger(__name__)

# Constants
_PLANS_DIR = Path("data/plans")
_STATUS_PENDING = "pending"
_STATUS_IN_PROGRESS = "in_progress"
_STATUS_COMPLETED = "completed"
_STATUS_APPROVED = "approved"
_STATUS_REJECTED = "rejected"

# Available agents for enzyme design
_AVAILABLE_AGENTS = {
    "enzyme_kinetics_extractor": {
        "description": "Extract kinetic parameters (Km, kcat, Tm)",
        "actions": ["extract_kinetics", "extract_mutations", "extract_conditions"],
    },
    "enzyme_design_extractor": {
        "description": "Extract design workflows and methodologies",
        "actions": ["extract_design_workflow", "extract_optimization_cycles"],
    },
    "vision_image_analyzer": {
        "description": "Analyze figures and extract data",
        "actions": ["analyze_figure", "extract_table_data"],
    },
    "enzyme_extraction_summary": {
        "description": "Generate comprehensive summaries",
        "actions": ["generate_summary", "analyze_performance"],
    },
}


class PlanState(BaseModel):
    """State tracking for plan phases."""

    phase_1: Dict[str, Any] = Field(default_factory=dict)
    phase_2: Dict[str, Any] = Field(default_factory=dict)
    phase_3: Dict[str, Any] = Field(default_factory=dict)
    phase_4: Dict[str, Any] = Field(default_factory=dict)
    phase_5: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStep(BaseModel):
    """A single step in the workflow."""

    step_id: int
    agent: str
    action: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None


class Plan(BaseModel):
    """Complete plan structure."""

    plan_id: str
    task: Dict[str, Any]
    workflow: List[WorkflowStep] = Field(default_factory=list)
    phases: PlanState = Field(default_factory=PlanState)
    status: str = _STATUS_PENDING
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PlanningTool(TrackingMixin, BaseTool):
    """Tool for 5-phase planning workflow.

    This tool guides users through structured planning for complex tasks,
    particularly enzyme design workflows. It generates plans that can be
    executed by the ExecutorAgent.
    """

    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters.

        Returns:
            JSON schema for planning tool parameters.
        """
        return {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Description of the task to plan"
                },
                "plan_id": {
                    "type": "string",
                    "description": "Existing plan ID to continue"
                },
                "phase": {
                    "type": "integer",
                    "description": "Current phase number (1-5)",
                    "minimum": 1,
                    "maximum": 5
                },
                "user_input": {
                    "type": "string",
                    "description": "User input/feedback for current phase"
                }
            }
        }

    def __init__(
        self,
        model_manager,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        step_id: Optional[str] = None,
        plans_dir: Optional[Path] = None,
    ):
        """Initialize PlanningTool.

        Args:
            model_manager: ModelManager for LLM operations.
            agent_id: Agent ID for tracking.
            session_id: Session ID for tracking.
            step_id: Step ID for tracking.
            plans_dir: Directory for plan storage.
        """
        BaseTool.__init__(
            self,
            name="planner",
            description="5-phase planning workflow for complex tasks",
            timeout=300,
        )
        TrackingMixin.__init__(self, agent_id, session_id, step_id)
        self.model_manager = model_manager
        self.plans_dir = plans_dir or _PLANS_DIR
        self.plans_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, **kwargs) -> ToolResult:
        """Execute planning workflow.

        Args:
            **kwargs: Must include either:
                - task_description: Task description to start new plan
                - plan_id: Existing plan ID to continue
                - phase: Current phase number (1-5)
                - user_input: User input/feedback for current phase

        Returns:
            ToolResult with plan data.
        """
        try:
            # Determine if starting new plan or continuing existing
            plan_id = kwargs.get("plan_id")
            phase = kwargs.get("phase", 1)

            if plan_id:
                plan = self._load_plan(plan_id)
            else:
                plan_id = self._generate_plan_id()
                plan = Plan(
                    plan_id=plan_id,
                    task={"description": kwargs.get("task_description", "")},
                    metadata={"created_at": datetime.now().isoformat()},
                )

            # Execute appropriate phase
            phase_method = getattr(self, f"execute_phase_{phase}", None)
            if not phase_method:
                return ToolResult(
                    status="error",
                    error=f"Invalid phase: {phase}. Must be 1-5.",
                )

            # Execute phase and update plan
            phase_result = await phase_method(plan, kwargs.get("user_input", ""))
            self._update_plan_phase(plan, phase, phase_result)

            # Save plan
            self._save_plan(plan)

            return ToolResult(
                status="success",
                data={
                    "plan_id": plan.plan_id,
                    "phase": phase,
                    "phase_result": phase_result,
                    "plan_status": plan.status,
                    "next_phase": phase + 1 if phase < 5 else None,
                    "ready_to_execute": plan.status == _STATUS_APPROVED,
                },
            )

        except Exception as e:
            logger.error(f"Planning workflow failed: {e}", exc_info=True)
            return ToolResult(status="error", error=str(e))

    async def execute_phase_1(self, plan: Plan, user_input: str = "") -> Dict[str, Any]:
        """Phase 1: Initial Understanding.

        Ask clarifying questions about objectives, constraints, methods.

        Args:
            plan: Current plan state.
            user_input: User's initial task description.

        Returns:
            Dictionary with understanding summary and questions.
        """
        # Build context prompt
        context = ENZYME_DESIGN_PLANNING_CONTEXT
        if any(keyword in plan.task.get("description", "").lower()
               for keyword in ["enzyme", "kinetics", "design", "workflow"]):
            context = ENZYME_DESIGN_PLANNING_CONTEXT

        prompt = PLANNING_PHASE_1_PROMPT.format(
            task_description=plan.task.get("description", ""),
            context=context,
            user_input=user_input,
        )

        # Generate understanding
        messages = [
            {
                "role": "system",
                "content": "You are an expert planning assistant."
            },
            {
                "role": "user",
                "content": prompt
            },
        ]

        response = await self.model_manager.generate(
            messages,
            agent_id=self.agent_id,
            agent_name="planner",
        )

        # Parse response
        result = self._parse_json_response(response.content or "")

        return {
            "status": _STATUS_COMPLETED,
            "understanding": result.get("understanding", ""),
            "questions": result.get("questions", []),
            "suggestions": result.get("suggestions", []),
            "completed_at": datetime.now().isoformat(),
        }

    async def execute_phase_2(self, plan: Plan, user_input: str = "") -> Dict[str, Any]:
        """Phase 2: Design Approach.

        Create detailed implementation approach with workflow steps.

        Args:
            plan: Current plan state.
            user_input: User's answers to phase 1 questions.

        Returns:
            Dictionary with approach, steps, risks, and mitigations.
        """
        # Build on phase 1 understanding
        understanding = plan.phases.phase_1.get("understanding", "")
        questions = plan.phases.phase_1.get("questions", [])
        answers = user_input or "No additional context provided."

        prompt = PLANNING_PHASE_2_PROMPT.format(
            task_description=plan.task.get("description", ""),
            understanding=understanding,
            questions=json.dumps(questions, indent=2),
            answers=answers,
            available_agents=json.dumps(_AVAILABLE_AGENTS, indent=2),
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert planning assistant."
            },
            {
                "role": "user",
                "content": prompt
            },
        ]

        response = await self.model_manager.generate(
            messages,
            agent_id=self.agent_id,
            agent_name="planner",
        )

        result = self._parse_json_response(response.content or "")

        return {
            "status": _STATUS_COMPLETED,
            "approach": result.get("approach", ""),
            "steps": result.get("steps", []),
            "risks": result.get("risks", []),
            "mitigations": result.get("mitigations", []),
            "estimated_duration_hours": result.get("estimated_duration_hours", 0),
            "completed_at": datetime.now().isoformat(),
        }

    async def execute_phase_3(self, plan: Plan, user_input: str = "") -> Dict[str, Any]:
        """Phase 3: Review and Validation.

        Present plan in human-readable format and collect feedback.

        Args:
            plan: Current plan state.
            user_input: User's feedback on phase 2 design.

        Returns:
            Dictionary with plan summary and approval status.
        """
        approach = plan.phases.phase_2.get("approach", "")
        steps = plan.phases.phase_2.get("steps", [])
        risks = plan.phases.phase_2.get("risks", [])
        feedback = user_input or "No feedback provided."

        prompt = PLANNING_PHASE_3_PROMPT.format(
            approach=approach,
            steps=json.dumps(steps, indent=2),
            risks=json.dumps(risks, indent=2),
            feedback=feedback,
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert planning assistant."
            },
            {
                "role": "user",
                "content": prompt
            },
        ]

        response = await self.model_manager.generate(
            messages,
            agent_id=self.agent_id,
            agent_name="planner",
        )

        result = self._parse_json_response(response.content or "")

        return {
            "status": _STATUS_COMPLETED,
            "plan_summary": result.get("plan_summary", ""),
            "approved": result.get("approved", False),
            "concerns": result.get("concerns", []),
            "modifications": result.get("modifications", []),
            "completed_at": datetime.now().isoformat(),
        }

    async def execute_phase_4(self, plan: Plan, user_input: str = "") -> Dict[str, Any]:
        """Phase 4: Final Plan Generation.

        Generate executable workflow JSON and write to disk.

        Args:
            plan: Current plan state.
            user_input: User's confirmation or modifications.

        Returns:
            Dictionary with workflow and plan path.
        """
        # Get approved steps from phase 2/3
        steps = plan.phases.phase_2.get("steps", [])
        modifications = plan.phases.phase_3.get("modifications", [])

        prompt = PLANNING_PHASE_4_PROMPT.format(
            task_description=plan.task.get("description", ""),
            steps=json.dumps(steps, indent=2),
            modifications=json.dumps(modifications, indent=2),
            available_agents=json.dumps(_AVAILABLE_AGENTS, indent=2),
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert planning assistant."
            },
            {
                "role": "user",
                "content": prompt
            },
        ]

        response = await self.model_manager.generate(
            messages,
            agent_id=self.agent_id,
            agent_name="planner",
        )

        result = self._parse_json_response(response.content or "")

        # Build workflow steps
        workflow = []
        for idx, step_data in enumerate(result.get("workflow", []), 1):
            workflow.append(
                WorkflowStep(
                    step_id=idx,
                    agent=step_data.get("agent", ""),
                    action=step_data.get("action", ""),
                    inputs=step_data.get("inputs", {}),
                    outputs={},
                    description=step_data.get("description", ""),
                ))

        plan.workflow = workflow

        return {
            "status": _STATUS_COMPLETED,
            "workflow": [step.model_dump() for step in workflow],
            "plan_path": str(self.plans_dir / f"{plan.plan_id}.json"),
            "total_steps": len(workflow),
            "completed_at": datetime.now().isoformat(),
        }

    async def execute_phase_5(self, plan: Plan, user_input: str = "") -> Dict[str, Any]:
        """Phase 5: Exit and Approval.

        Request final confirmation before execution.

        Args:
            plan: Current plan state.
            user_input: User's final approval or rejection.

        Returns:
            Dictionary with ready_to_execute flag and next steps.
        """
        workflow = [w.model_dump() for w in plan.workflow]
        approval = user_input or "pending"

        prompt = PLANNING_PHASE_5_PROMPT.format(
            task_description=plan.task.get("description", ""),
            workflow=json.dumps(workflow, indent=2),
            current_approval=approval,
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert planning assistant."
            },
            {
                "role": "user",
                "content": prompt
            },
        ]

        response = await self.model_manager.generate(
            messages,
            agent_id=self.agent_id,
            agent_name="planner",
        )

        result = self._parse_json_response(response.content or "")

        # Update plan status based on approval
        ready_to_execute = result.get("ready_to_execute", False)
        if ready_to_execute:
            plan.status = _STATUS_APPROVED
        else:
            plan.status = _STATUS_REJECTED

        return {
            "status": _STATUS_COMPLETED,
            "ready_to_execute": ready_to_execute,
            "next_steps": result.get("next_steps", []),
            "warnings": result.get("warnings", []),
            "completed_at": datetime.now().isoformat(),
        }

    def _update_plan_phase(self, plan: Plan, phase: int,
                           phase_result: Dict[str, Any]) -> None:
        """Update plan state with phase results.

        Args:
            plan: Plan to update.
            phase: Phase number (1-5).
            phase_result: Result from phase execution.
        """
        phase_key = f"phase_{phase}"
        setattr(plan.phases, phase_key, phase_result)

        # Update overall plan status
        if phase == 5:
            plan.status = (_STATUS_APPROVED if phase_result.get(
                "ready_to_execute", False) else _STATUS_PENDING)
        else:
            plan.status = _STATUS_IN_PROGRESS

    def _generate_plan_id(self) -> str:
        """Generate unique plan ID.

        Returns:
            Plan ID string.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"plan_{timestamp}"

    def _load_plan(self, plan_id: str) -> Plan:
        """Load plan from disk.

        Args:
            plan_id: Plan ID to load.

        Returns:
            Loaded Plan object.

        Raises:
            ValueError: If plan file not found.
        """
        plan_path = self.plans_dir / f"{plan_id}.json"
        if not plan_path.exists():
            raise ValueError(f"Plan not found: {plan_path}")

        with open(plan_path, "r") as f:
            data = json.load(f)

        # Convert workflow dicts to WorkflowStep objects
        if "workflow" in data:
            data["workflow"] = [WorkflowStep(**step) for step in data["workflow"]]

        return Plan(**data)

    def _save_plan(self, plan: Plan) -> None:
        """Save plan to disk.

        Args:
            plan: Plan to save.
        """
        plan_path = self.plans_dir / f"{plan.plan_id}.json"
        with open(plan_path, "w") as f:
            json.dump(plan.model_dump(), f, indent=2)

        logger.info(f"Plan saved to: {plan_path}")

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON response from LLM.

        Args:
            content: Raw response content.

        Returns:
            Parsed JSON dict or empty dict on failure.
        """
        content = content.strip()

        # Try direct JSON parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        import re

        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to parse JSON response: {content[:200]}...")
        return {}
