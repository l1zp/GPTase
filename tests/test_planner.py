"""Tests for the Plan Mode and Task System."""

from datetime import datetime
import json
from typing import Any, Dict
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from gptase.agents.execution_types import ExecutionContext
from gptase.agents.plan_dispatcher import TaskDispatcher
from gptase.agents.planner import PlanManager
from gptase.agents.execution_types import TaskResult
from gptase.agents.types import AgentMode
from gptase.agents.types import Plan
from gptase.agents.types import PlannedTask
from gptase.agents.types import TaskStatus
from gptase.agents.execution_types import TaskExecutionResult
from gptase.memory.manager import MemoryManager

# ======================================================================
# PlannedTask Tests
# ======================================================================


class TestPlannedTask:
    """Tests for PlannedTask model."""

    def test_task_creation(self) -> None:
        """Test creating a basic planned task."""
        task = PlannedTask(
            task_id="1",
            description="Analyze the data",
        )
        assert task.task_id == "1"
        assert task.description == "Analyze the data"
        assert task.status == TaskStatus.PENDING
        assert task.dependencies == []
        assert task.result is None
        assert task.error is None

    def test_task_with_dependencies(self) -> None:
        """Test creating a task with dependencies."""
        task = PlannedTask(
            task_id="2",
            description="Process results",
            dependencies=["1"],
            reasoning="Needs raw data from step 1",
        )
        assert task.dependencies == ["1"]
        assert task.reasoning == "Needs raw data from step 1"

    def test_is_ready_no_deps(self) -> None:
        """Test that a task with no dependencies is always ready."""
        task = PlannedTask(task_id="1", description="First task")
        assert task.is_ready(set()) is True
        assert task.is_ready({"other"}) is True

    def test_is_ready_with_deps_met(self) -> None:
        """Test readiness when dependencies are met."""
        task = PlannedTask(
            task_id="3",
            description="Final task",
            dependencies=["1", "2"],
        )
        assert task.is_ready({"1", "2"}) is True
        assert task.is_ready({"1", "2", "extra"}) is True

    def test_is_ready_with_deps_unmet(self) -> None:
        """Test readiness when dependencies are not met."""
        task = PlannedTask(
            task_id="3",
            description="Final task",
            dependencies=["1", "2"],
        )
        assert task.is_ready(set()) is False
        assert task.is_ready({"1"}) is False

    def test_task_serialization(self) -> None:
        """Test task can be serialized to dict."""
        task = PlannedTask(
            task_id="1",
            description="Test",
            status=TaskStatus.COMPLETED,
            result={"content": "done"},
        )
        data = task.model_dump()
        assert data["task_id"] == "1"
        assert data["status"] == "completed"
        assert data["result"] == {"content": "done"}


# ======================================================================
# Plan Tests
# ======================================================================


class TestPlan:
    """Tests for Plan model."""

    def _make_plan(self) -> Plan:
        """Create a sample plan for testing."""
        return Plan(
            plan_id="test_plan",
            goal="Test goal",
            summary="Test summary",
            tasks=[
                PlannedTask(task_id="1", description="Step 1"),
                PlannedTask(task_id="2", description="Step 2", dependencies=["1"]),
                PlannedTask(task_id="3", description="Step 3", dependencies=["1"]),
                PlannedTask(
                    task_id="4",
                    description="Step 4",
                    dependencies=["2", "3"],
                ),
            ],
        )

    def test_plan_creation(self) -> None:
        """Test creating a basic plan."""
        plan = self._make_plan()
        assert plan.plan_id == "test_plan"
        assert plan.goal == "Test goal"
        assert len(plan.tasks) == 4
        assert plan.status == "draft"

    def test_plan_auto_id(self) -> None:
        """Test that plan_id is auto-generated if not provided."""
        plan = Plan(goal="Auto ID test")
        assert plan.plan_id.startswith("plan_")

    def test_get_next_tasks_initial(self) -> None:
        """Test getting next tasks when no tasks are completed."""
        plan = self._make_plan()
        next_tasks = plan.get_next_tasks()
        assert len(next_tasks) == 1
        assert next_tasks[0].task_id == "1"

    def test_get_next_tasks_after_first(self) -> None:
        """Test getting next tasks after first task completes."""
        plan = self._make_plan()
        plan.tasks[0].status = TaskStatus.COMPLETED  # Task 1 done
        next_tasks = plan.get_next_tasks()
        assert len(next_tasks) == 2
        task_ids = {t.task_id for t in next_tasks}
        assert task_ids == {"2", "3"}

    def test_get_next_tasks_final(self) -> None:
        """Test getting next tasks when all deps of final task are met."""
        plan = self._make_plan()
        plan.tasks[0].status = TaskStatus.COMPLETED
        plan.tasks[1].status = TaskStatus.COMPLETED
        plan.tasks[2].status = TaskStatus.COMPLETED
        next_tasks = plan.get_next_tasks()
        assert len(next_tasks) == 1
        assert next_tasks[0].task_id == "4"

    def test_get_progress(self) -> None:
        """Test progress tracking."""
        plan = self._make_plan()
        progress = plan.get_progress()
        assert progress["total"] == 4
        assert progress["pending"] == 4
        assert progress["completed"] == 0

        plan.tasks[0].status = TaskStatus.COMPLETED
        plan.tasks[1].status = TaskStatus.IN_PROGRESS
        plan.tasks[3].status = TaskStatus.FAILED
        progress = plan.get_progress()
        assert progress["completed"] == 1
        assert progress["in_progress"] == 1
        assert progress["failed"] == 1
        assert progress["pending"] == 1

    def test_is_complete(self) -> None:
        """Test plan completion detection."""
        plan = self._make_plan()
        assert plan.is_complete() is False

        for t in plan.tasks:
            t.status = TaskStatus.COMPLETED
        assert plan.is_complete() is True

    def test_is_complete_with_failures(self) -> None:
        """Test plan is considered complete even with failures."""
        plan = self._make_plan()
        plan.tasks[0].status = TaskStatus.COMPLETED
        plan.tasks[1].status = TaskStatus.FAILED
        plan.tasks[2].status = TaskStatus.COMPLETED
        plan.tasks[3].status = TaskStatus.SKIPPED
        assert plan.is_complete() is True

    def test_get_task(self) -> None:
        """Test finding a task by ID."""
        plan = self._make_plan()
        task = plan.get_task("2")
        assert task is not None
        assert task.description == "Step 2"
        assert plan.get_task("999") is None


# ======================================================================
# PlanManager Tests
# ======================================================================


class TestPlanManager:
    """Tests for PlanManager class."""

    def _make_mock_agent(self):
        """Create a mock agent for testing."""
        agent = MagicMock()
        agent.agent_id = "test_agent"
        agent.run = AsyncMock()
        return agent

    def test_parse_plan_output(self) -> None:
        """Test parsing valid LLM output into a Plan."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        llm_output = json.dumps({
            "summary":
            "Two-step plan",
            "tasks": [
                {
                    "task_id": "1",
                    "description": "First step",
                    "reasoning": "Need to start here",
                    "dependencies": [],
                    "expected_output": "Raw data",
                },
                {
                    "task_id": "2",
                    "description": "Second step",
                    "reasoning": "Process results",
                    "dependencies": ["1"],
                    "expected_output": "Final report",
                },
            ],
        })

        plan = pm._parse_plan_output(llm_output, "Test goal")
        assert len(plan.tasks) == 2
        assert plan.goal == "Test goal"
        assert plan.summary == "Two-step plan"
        assert plan.tasks[0].task_id == "1"
        assert plan.tasks[1].dependencies == ["1"]

    def test_parse_plan_output_markdown_wrapped(self) -> None:
        """Test parsing JSON wrapped in markdown fences."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        llm_output = '```json\n{"summary": "Test", "tasks": [{"task_id": "1", "description": "Do something"}]}\n```'
        plan = pm._parse_plan_output(llm_output, "Goal")
        assert len(plan.tasks) == 1

    def test_parse_plan_output_invalid(self) -> None:
        """Test that invalid output raises ValueError."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        with pytest.raises(ValueError, match="Failed to parse plan JSON"):
            pm._parse_plan_output("not json at all", "Goal")

    def test_parse_plan_output_no_tasks(self) -> None:
        """Test that plan with no tasks raises ValueError."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        with pytest.raises(ValueError, match="no valid tasks"):
            pm._parse_plan_output('{"summary": "empty", "tasks": []}', "Goal")

    def test_validate_dependencies_valid(self) -> None:
        """Test validation passes for valid dependencies."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        plan = Plan(
            goal="test",
            tasks=[
                PlannedTask(task_id="1", description="A"),
                PlannedTask(task_id="2", description="B", dependencies=["1"]),
            ],
        )
        # Should not raise
        pm._validate_dependencies(plan)

    def test_validate_dependencies_cycle(self) -> None:
        """Test that circular dependencies are detected."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        plan = Plan(
            goal="test",
            tasks=[
                PlannedTask(task_id="1", description="A", dependencies=["2"]),
                PlannedTask(task_id="2", description="B", dependencies=["1"]),
            ],
        )
        with pytest.raises(ValueError, match="Circular dependency"):
            pm._validate_dependencies(plan)

    def test_validate_dependencies_removes_unknown(self) -> None:
        """Test that references to unknown tasks are removed."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        plan = Plan(
            goal="test",
            tasks=[
                PlannedTask(
                    task_id="1",
                    description="A",
                    dependencies=["unknown"],
                ),
            ],
        )
        pm._validate_dependencies(plan)
        assert plan.tasks[0].dependencies == []

    def test_extract_json_direct(self) -> None:
        """Test extracting direct JSON."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        assert pm._extract_json('{"key": "value"}') == '{"key": "value"}'

    def test_extract_json_markdown(self) -> None:
        """Test extracting JSON from markdown code block."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        result = pm._extract_json('```json\n{"key": "value"}\n```')
        assert json.loads(result) == {"key": "value"}

    def test_extract_json_embedded(self) -> None:
        """Test extracting JSON embedded in text."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        result = pm._extract_json('Here is the plan: {"key": "value"} end.')
        assert json.loads(result) == {"key": "value"}

    def test_build_task_prompt(self) -> None:
        """Test building execution prompt for a task."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        plan = Plan(
            goal="Analyze data",
            tasks=[
                PlannedTask(
                    task_id="1",
                    description="Read file",
                    status=TaskStatus.COMPLETED,
                    result={"content": "file contents here"},
                ),
                PlannedTask(
                    task_id="2",
                    description="Process data",
                    dependencies=["1"],
                    expected_output="Summary report",
                ),
            ],
        )

        prompt = pm._build_task_prompt(plan.tasks[1], plan)
        assert "Analyze data" in prompt
        assert "Process data" in prompt
        assert "Summary report" in prompt
        assert "file contents here" in prompt

    @pytest.mark.asyncio
    async def test_create_plan(self) -> None:
        """Test end-to-end plan creation with mocked LLM."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        plan_json = json.dumps({
            "summary":
            "Test plan",
            "tasks": [
                {
                    "task_id": "1",
                    "description": "Step one",
                    "dependencies": [],
                },
            ],
        })

        agent.run.return_value = {
            "status": "success",
            "data": {
                "content": plan_json
            },
        }

        plan = await pm.create_plan("Do something")
        assert plan.goal == "Do something"
        assert len(plan.tasks) == 1
        assert plan.tasks[0].description == "Step one"
        # Verify run was called with DIRECT mode
        agent.run.assert_called_once()
        call_kwargs = agent.run.call_args
        assert call_kwargs.kwargs.get("mode") == AgentMode.DIRECT

    def test_get_planner_agent_uses_parent_agent_without_model_context(self) -> None:
        """Lightweight contexts should reuse the parent agent as the planner."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        planner_agent = pm._get_planner_agent()

        assert planner_agent is agent

    @patch("gptase.agents.planner.Agent.from_markdown")
    def test_get_planner_agent_prefers_dedicated_planner(self, mock_from_markdown) -> None:
        """Planner should load the dedicated markdown agent when available."""
        agent = self._make_mock_agent()
        agent.model_config = object()
        dedicated = MagicMock()
        dedicated.system_prompt = "Planner base prompt"
        mock_from_markdown.return_value = dedicated

        pm = PlanManager(agent, model_manager=MagicMock())
        planner_agent = pm._get_planner_agent()

        assert planner_agent is dedicated
        mock_from_markdown.assert_called_once()
        assert "Task Planning Instructions" in planner_agent.system_prompt

    @pytest.mark.asyncio
    async def test_execute_plan(self) -> None:
        """Test executing a plan with mocked agent."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        plan = Plan(
            goal="Test",
            tasks=[
                PlannedTask(task_id="1", description="First"),
                PlannedTask(task_id="2", description="Second", dependencies=["1"]),
            ],
        )

        agent.run.return_value = {
            "status": "success",
            "data": {
                "content": "task done"
            },
        }

        result = await pm.execute_plan(plan)
        assert result["status"] == "completed"
        assert result["progress"]["completed"] == 2
        assert result["progress"]["failed"] == 0
        assert agent.run.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_plan_with_failure(self) -> None:
        """Test plan execution when a task fails."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        plan = Plan(
            goal="Test",
            tasks=[
                PlannedTask(task_id="1", description="First"),
                PlannedTask(task_id="2", description="Second", dependencies=["1"]),
            ],
        )

        # First call fails, second never happens (dep unmet)
        agent.run.return_value = {
            "status": "error",
            "error": "Something broke",
        }

        from gptase.agents.planner import PlanExecutionError
        with pytest.raises(PlanExecutionError):
            await pm.execute_plan(plan)


# ======================================================================
# TaskDispatcher Tests
# ======================================================================


class TestTaskDispatcher:
    """Tests for task input resolution and validation."""

    def _make_dispatcher(self) -> TaskDispatcher:
        return TaskDispatcher(memory_manager=MemoryManager(), model_manager=None)

    def _make_context_with_result(self, task_id: str,
                                  data: Dict[str, Any]) -> ExecutionContext:
        context = ExecutionContext(plan_id="test_plan")
        context.task_results[task_id] = TaskExecutionResult(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            result=TaskResult(agent_id="test-agent", task_id=task_id, data=data),
        )
        return context

    def test_resolve_placeholder_input_to_structured_dependency_output(self) -> None:
        dispatcher = self._make_dispatcher()
        context = self._make_context_with_result(
            "3",
            {
                "content": json.dumps({
                    "candidate_sequences": [{
                        "label": "WT",
                        "sequence": "ACDE",
                    }],
                    "template_pdb_for_prediction": "1ABC",
                })
            },
        )

        resolved = dispatcher._resolve_inputs(
            {
                "initial_candidate_sequences": "Output from task 3",
                "template_pdb": "Output from task 3",
            },
            context,
        )

        assert resolved["initial_candidate_sequences"] == [{
            "label": "WT",
            "sequence": "ACDE",
        }]
        assert resolved["template_pdb"] == "1ABC"

    def test_resolve_multi_task_output_bundle(self) -> None:
        dispatcher = self._make_dispatcher()
        context = ExecutionContext(plan_id="test_plan")
        for task_id, payload in {
            "1": {
                "content": json.dumps({"papers_found": 3})
            },
            "2": {
                "content": json.dumps({"uniprot_entries": ["P1"]})
            },
        }.items():
            context.task_results[task_id] = TaskExecutionResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=TaskResult(agent_id="test-agent", task_id=task_id, data=payload),
            )

        resolved = dispatcher._resolve_inputs(
            {"all_task_outputs": "Outputs from tasks 1 through 2"},
            context,
        )

        assert resolved["all_task_outputs"] == {
            "1": {
                "papers_found": 3
            },
            "2": {
                "uniprot_entries": ["P1"]
            },
        }

    def test_validate_resolved_inputs_blocks_low_quality_upstream_data(self) -> None:
        dispatcher = self._make_dispatcher()
        task = PlannedTask(
            task_id="3",
            description="Design",
            inputs={"literature_data": "Output from task 1"},
        )

        error = dispatcher._validate_resolved_inputs(
            task,
            {"literature_data": {
                "data_sufficiency": "low"
            }},
        )

        assert error is not None
        assert "insufficient" in error

    def test_validate_task_output_rejects_null_candidate_sequences(self) -> None:
        dispatcher = self._make_dispatcher()
        task = PlannedTask(task_id="3", description="Design")

        error = dispatcher._validate_task_output(
            task,
            {},
            {
                "status": "success",
                "data": {
                    "content": json.dumps({
                        "candidate_sequences": [{
                            "label": "WT",
                            "sequence": None,
                        }]
                    })
                },
            },
        )

        assert error is not None
        assert "usable candidate sequences" in error

    def test_validate_task_output_rejects_fatal_error_payload(self) -> None:
        dispatcher = self._make_dispatcher()
        task = PlannedTask(task_id="5", description="Predict")

        error = dispatcher._validate_task_output(
            task,
            {
                "candidate_sequences": [{
                    "label": "WT",
                    "sequence": "ACDE",
                }]
            },
            {
                "status": "success",
                "data": {
                    "content": json.dumps({
                        "fatal_error": "missing template_pdb"
                    })
                },
            },
        )

        assert error == "missing template_pdb"


# ======================================================================
# AgentMode Tests
# ======================================================================


class TestAgentMode:
    """Tests for AgentMode enum."""

    def test_mode_values(self) -> None:
        """Test mode enum values."""
        assert AgentMode.DIRECT == "direct"
        assert AgentMode.PLAN == "plan"

    def test_mode_is_string(self) -> None:
        """Test that mode enum is string-compatible."""
        assert str(AgentMode.PLAN) == "AgentMode.PLAN"
        assert AgentMode.PLAN.value == "plan"
