"""Tests for the Plan Mode and Task System."""

import asyncio
from datetime import datetime
import json
from typing import Any, Dict
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from gptase.agents.execution_types import ExecutionContext
from gptase.agents.execution_types import TaskExecutionResult
from gptase.agents.execution_types import TaskResult
from gptase.agents.plan_dispatcher import TaskDispatcher
from gptase.agents.plan_loader import PlanLoader
from gptase.agents.planner import PlanManager
from gptase.agents.runtime_types import InteractiveRuntimeSnapshot
from gptase.agents.runtime_types import InteractiveTurn
from gptase.agents.runtime_types import RuntimeStopReason
from gptase.agents.types import AgentMode
from gptase.agents.types import Plan
from gptase.agents.types import PlannedTask
from gptase.agents.types import TaskStatus
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

        try:
            plan = await pm.create_plan("Do something")
            assert plan.goal == "Do something"
            assert len(plan.tasks) == 1
            assert plan.tasks[0].description == "Step one"
            # Verify run was called with DIRECT mode
            agent.run.assert_called_once()
            call_kwargs = agent.run.call_args
            assert call_kwargs.kwargs.get("mode") == AgentMode.DIRECT
        finally:
            await pm.close()

    def test_get_planner_agent_uses_parent_agent_without_model_context(self) -> None:
        """Lightweight contexts should reuse the parent agent as the planner."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        planner_agent = pm._get_planner_agent()

        assert planner_agent is agent

    @patch("gptase.agents.planner.Agent.from_markdown")
    def test_get_planner_agent_prefers_dedicated_planner(self,
                                                         mock_from_markdown) -> None:
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

        try:
            result = await pm.execute_plan(plan)
            assert result["status"] == "completed"
            assert result["progress"]["completed"] == 2
            assert result["progress"]["failed"] == 0
            assert agent.run.call_count == 2
        finally:
            await pm.close()

    @pytest.mark.asyncio
    async def test_execute_plan_checkpoints_each_completed_task(self) -> None:
        """Save progress as each concurrent task finishes, not only after the batch."""
        agent = self._make_mock_agent()
        pm = PlanManager(agent)

        plan = Plan(
            goal="Test",
            max_parallel=2,
            tasks=[
                PlannedTask(task_id="1", description="First"),
                PlannedTask(task_id="2", description="Second"),
            ],
        )

        second_task_gate = asyncio.Event()
        checkpoint_counts: list[int] = []

        async def run_side_effect(prompt: str, mode=None):
            if "ID: 2" in prompt:
                await second_task_gate.wait()
            return {
                "status": "success",
                "data": {
                    "content": "task done"
                },
            }

        async def save_side_effect(context, current_plan, status="in_progress"):
            completed = sum(1 for task in current_plan.tasks
                            if task.status == TaskStatus.COMPLETED)
            checkpoint_counts.append(completed)
            return "checkpoint-id"

        agent.run.side_effect = run_side_effect
        pm._save_checkpoint_to_db = AsyncMock(side_effect=save_side_effect)

        try:
            execution_task = asyncio.create_task(pm.execute_plan(plan))
            await asyncio.sleep(0.05)

            assert execution_task.done() is False
            assert 1 in checkpoint_counts

            second_task_gate.set()
            result = await execution_task

            assert result["status"] == "completed"
            assert checkpoint_counts[0] == 0
            assert checkpoint_counts[-1] == 2
        finally:
            await pm.close()

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
        try:
            with pytest.raises(PlanExecutionError):
                await pm.execute_plan(plan)
        finally:
            await pm.close()

    @pytest.mark.asyncio
    async def test_execute_plan_records_runtime_turn_checkpoint(self) -> None:
        """Turn callbacks should write runtime snapshots before task completion."""
        agent = self._make_mock_agent()
        agent.is_claude_model.return_value = False
        pm = PlanManager(agent)

        snapshot = InteractiveRuntimeSnapshot(
            messages=[{
                "role": "system",
                "content": "system"
            }],
            turns=[
                InteractiveTurn(
                    turn_index=1,
                    assistant_content="working",
                    stop_reason=None,
                )
            ],
            steps=[{
                "type": "llm_call",
                "iteration": 1,
            }],
            total_input_tokens=10,
            total_output_tokens=5,
            total_duration_ms=50,
        )

        async def run_side_effect(prompt: str, mode=None, **kwargs):
            callback = kwargs["_on_turn_complete"]
            await callback(
                snapshot,
                InteractiveTurn(
                    turn_index=1,
                    assistant_content="working",
                    stop_reason=RuntimeStopReason.FINAL_ANSWER,
                ),
            )
            return {
                "status": "success",
                "data": {
                    "content": "task done"
                },
                "trace": {
                    "runtime": {
                        "stop_reason": "final_answer",
                        "turn_count": 1,
                        "turns": [snapshot.turns[0].model_dump(mode="json")],
                    }
                },
            }

        checkpoint_runtime_turns = []

        async def save_side_effect(context, current_plan, status="in_progress"):
            runtime_state = context.active_tasks.get("1", {}).get("runtime_snapshot")
            checkpoint_runtime_turns.append(
                runtime_state.get("turns") if runtime_state else None)
            return "checkpoint-id"

        plan = Plan(goal="Test", tasks=[PlannedTask(task_id="1", description="First")])
        agent.run.side_effect = run_side_effect
        pm._save_checkpoint_to_db = AsyncMock(side_effect=save_side_effect)

        try:
            result = await pm.execute_plan(plan)
            assert result["status"] == "completed"
            assert any(turns for turns in checkpoint_runtime_turns)
            assert result["task_traces"]["1"]["runtime"]["turn_count"] == 1
        finally:
            await pm.close()

    @pytest.mark.asyncio
    async def test_execute_plan_resumes_local_task_from_runtime_snapshot(self) -> None:
        """Resumed local tasks should receive the stored runtime snapshot."""
        agent = self._make_mock_agent()
        agent.is_claude_model.return_value = False
        pm = PlanManager(agent)

        snapshot = InteractiveRuntimeSnapshot(
            messages=[
                {
                    "role": "system",
                    "content": "system"
                },
                {
                    "role": "user",
                    "content": "user"
                },
                {
                    "role": "assistant",
                    "content": "partial"
                },
            ],
            turns=[
                InteractiveTurn(
                    turn_index=1,
                    assistant_content="partial",
                    stop_reason=None,
                )
            ],
            steps=[{
                "type": "llm_call",
                "iteration": 1,
            }],
            total_input_tokens=10,
            total_output_tokens=5,
            total_duration_ms=50,
        )
        context = ExecutionContext(
            plan_id="resume-plan",
            session_id="resume-session",
            task_results={
                "1": TaskExecutionResult(
                    task_id="1",
                    status=TaskStatus.IN_PROGRESS,
                )
            },
            active_tasks={
                "1": {
                    "task_id": "1",
                    "agent_id": "test_agent",
                    "runtime_snapshot": snapshot.model_dump(mode="json"),
                    "last_turn_index": 1,
                }
            },
        )

        async def run_side_effect(prompt: str, mode=None, **kwargs):
            assert kwargs["_resume_snapshot"] == snapshot.model_dump(mode="json")
            return {
                "status": "success",
                "data": {
                    "content": "resumed"
                },
                "trace": {
                    "runtime": {
                        "stop_reason": "final_answer",
                        "turn_count": 2,
                        "turns": [],
                    }
                },
            }

        plan = Plan(goal="Test", tasks=[PlannedTask(task_id="1", description="First")])
        agent.run.side_effect = run_side_effect

        try:
            result = await pm.execute_plan(plan,
                                           context_checkpoint=context.to_checkpoint())
            assert result["status"] == "completed"
            assert result["task_results"]["1"]["content"] == "resumed"
        finally:
            await pm.close()


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
                "content":
                json.dumps({
                    "candidate_sequences": [{
                        "label": "WT",
                        "sequence": "ACDE",
                    }],
                    "template_pdb_for_prediction":
                    "1ABC",
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
                    "content":
                    json.dumps(
                        {"candidate_sequences": [{
                            "label": "WT",
                            "sequence": None,
                        }]})
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
            {"candidate_sequences": [{
                "label": "WT",
                "sequence": "ACDE",
            }]},
            {
                "status": "success",
                "data": {
                    "content": json.dumps({"fatal_error": "missing template_pdb"})
                },
            },
        )

        assert error == "missing template_pdb"

    @pytest.mark.asyncio
    async def test_dispatch_writes_outputs_into_task_subdirectory(self,
                                                                  tmp_path) -> None:
        dispatcher = self._make_dispatcher()
        task = PlannedTask(
            task_id="2b_r1",
            description="Analyze figures",
            agent_id="vision-image-analyzer",
            action="analyze",
            inputs={},
        )
        context = ExecutionContext(
            plan_id="test_plan",
            workspace_dir=str(tmp_path / "run"),
            document_path=str(tmp_path / "doc.md"),
        )

        agent = MagicMock()
        agent.process_task_with_mode = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "content":
                    json.dumps({
                        "analysis_results": [{
                            "image_number": 4,
                            "figure_id": "Figure 3b",
                            "content": "MM"
                        }],
                        "extracted_tables": [{
                            "image_number": 4,
                            "figure_id": "Figure 3b",
                            "csv_data": "A,B\n1,2"
                        }],
                    })
                },
            })
        dispatcher._get_agent = AsyncMock(return_value=agent)

        result = await dispatcher.dispatch(task, context)

        assert result.status == "success"
        task_dir = tmp_path / "run" / "vision-image-analyzer" / "2b_r1"
        assert (task_dir / "2b_r1_result.json").exists()
        assert (task_dir / "2b_r1_parsed.json").exists()
        assert (task_dir / "2b_r1_analysis_results.csv").exists()
        assert (task_dir / "table_4.csv").exists()


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


# ======================================================================
# PlanLoader replicate: N Tests
# ======================================================================


class TestPlanLoaderReplicate:
    """Tests for replicate: N expansion in PlanLoader._expand_replicated_step."""

    def _loader(self) -> PlanLoader:
        return PlanLoader()

    def _load(self, workflow) -> list:
        """Helper: load a workflow dict and return the resulting task list."""
        loader = self._loader()
        plan = loader.load_data({"plan_id": "test", "workflow": workflow})
        return plan.tasks

    def test_no_replicate_returns_single_task(self) -> None:
        """A step without replicate produces exactly one task."""
        tasks = self._load([{"step_id": "1", "agent": "agent_a", "action": "run"}])

        assert len(tasks) == 1
        assert tasks[0].task_id == "1"

    def test_replicate_3_expands_to_three_tasks(self) -> None:
        """replicate: 3 produces three tasks with _r1, _r2, _r3 suffixes."""
        tasks = self._load([{
            "step_id": "2a",
            "agent": "extractor",
            "action": "extract",
            "replicate": 3,
        }])

        assert len(tasks) == 3
        assert [t.task_id for t in tasks] == ["2a_r1", "2a_r2", "2a_r3"]

    def test_replicated_tasks_share_same_dependencies(self) -> None:
        """All replicas inherit the same upstream dependencies."""
        tasks = self._load([
            {
                "step_id": "1",
                "agent": "scanner",
                "action": "scan"
            },
            {
                "step_id": "2",
                "agent": "extractor",
                "action": "extract",
                "replicate": 3
            },
        ])

        replica_tasks = [t for t in tasks if t.task_id.startswith("2_r")]
        assert len(replica_tasks) == 3
        for t in replica_tasks:
            assert t.dependencies == ["1"]

    def test_replicated_tasks_share_same_inputs(self) -> None:
        """All replicas receive the same inputs dict."""
        tasks = self._load([{
            "step_id": "2a",
            "agent": "extractor",
            "action": "extract",
            "replicate": 2,
            "inputs": {
                "text": "{{input_text}}"
            },
        }])

        assert tasks[0].inputs == {"text": "{{input_text}}"}
        assert tasks[1].inputs == {"text": "{{input_text}}"}

    def test_replicated_step_in_parallel_group(self) -> None:
        """Replicated steps inside a parallel group expand correctly."""
        tasks = self._load([{
            "parallel": [
                {
                    "step_id": "2a",
                    "agent": "text_extractor",
                    "replicate": 3
                },
                {
                    "step_id": "2b",
                    "agent": "vision_extractor",
                    "replicate": 3
                },
            ]
        }])

        ids = [t.task_id for t in tasks]
        assert ids == ["2a_r1", "2a_r2", "2a_r3", "2b_r1", "2b_r2", "2b_r3"]

    def test_downstream_depends_on_all_replicas(self) -> None:
        """A sequential step after replicated ones waits for all replicas."""
        tasks = self._load([
            {
                "step_id": "1",
                "agent": "scanner",
                "action": "scan"
            },
            {
                "parallel": [{
                    "step_id": "2a",
                    "agent": "extractor",
                    "replicate": 3
                }]
            },
            {
                "step_id": "3",
                "agent": "summarizer",
                "action": "summarize"
            },
        ])

        step3 = next(t for t in tasks if t.task_id == "3")
        assert sorted(step3.dependencies) == ["2a_r1", "2a_r2", "2a_r3"]

    def test_enzyme_pipeline_yaml_produces_eight_tasks(self) -> None:
        """The enzyme_extraction_pipeline YAML expands to exactly 8 tasks.

        Expected: 1 (structure scan) + 3 (text extract) + 3 (vision extract) + 1 (summary)
        """
        plan = self._loader().load("enzyme_extraction_pipeline")

        task_ids = [t.task_id for t in plan.tasks]
        assert len(task_ids) == 8
        assert "1" in task_ids
        assert "2a_r1" in task_ids
        assert "2a_r2" in task_ids
        assert "2a_r3" in task_ids
        assert "2b_r1" in task_ids
        assert "2b_r2" in task_ids
        assert "2b_r3" in task_ids
        assert "3" in task_ids

    def test_enzyme_pipeline_step3_depends_on_all_replicas(self) -> None:
        """Step 3 in the enzyme pipeline depends on all 6 replicas."""
        plan = self._loader().load("enzyme_extraction_pipeline")

        step3 = plan.get_task("3")
        assert step3 is not None
        assert sorted(step3.dependencies) == [
            "2a_r1", "2a_r2", "2a_r3", "2b_r1", "2b_r2", "2b_r3"
        ]


# ======================================================================
# ExecutionContext.get_replicated_task_data Tests
# ======================================================================


class TestExecutionContextReplicate:
    """Tests for ExecutionContext.get_replicated_task_data."""

    def _make_context(self) -> ExecutionContext:
        return ExecutionContext(plan_id="test")

    def _add_result(self, ctx: ExecutionContext, task_id: str, data: dict) -> None:
        ctx.task_results[task_id] = TaskExecutionResult(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            result=TaskResult(agent_id="agent", action="run", data=data),
        )

    def test_returns_none_when_no_replicas_exist(self) -> None:
        """None is returned when the context has no matching replica tasks."""
        ctx = self._make_context()
        self._add_result(ctx, "1", {"content": "step 1 data"})

        assert ctx.get_replicated_task_data("2a") is None

    def test_returns_sorted_list_of_replica_data(self) -> None:
        """Results are collected in sorted order by task_id."""
        ctx = self._make_context()
        # Insert out of order to verify sort
        self._add_result(ctx, "2a_r3", {"reactions": [{"run": 3}]})
        self._add_result(ctx, "2a_r1", {"reactions": [{"run": 1}]})
        self._add_result(ctx, "2a_r2", {"reactions": [{"run": 2}]})

        result = ctx.get_replicated_task_data("2a")

        assert result == [
            {
                "reactions": [{
                    "run": 1
                }]
            },
            {
                "reactions": [{
                    "run": 2
                }]
            },
            {
                "reactions": [{
                    "run": 3
                }]
            },
        ]

    def test_sorts_replica_ids_numerically(self) -> None:
        """Replica results are ordered by numeric suffix, not string sort."""
        ctx = self._make_context()
        self._add_result(ctx, "2a_r10", {"reactions": [{"run": 10}]})
        self._add_result(ctx, "2a_r2", {"reactions": [{"run": 2}]})
        self._add_result(ctx, "2a_r1", {"reactions": [{"run": 1}]})

        result = ctx.get_replicated_task_data("2a")

        assert result == [
            {
                "reactions": [{
                    "run": 1
                }]
            },
            {
                "reactions": [{
                    "run": 2
                }]
            },
            {
                "reactions": [{
                    "run": 10
                }]
            },
        ]

    def test_skips_replica_with_no_result_data(self) -> None:
        """Replicas whose TaskExecutionResult has no data are excluded."""
        ctx = self._make_context()
        self._add_result(ctx, "2a_r1", {"reactions": [{"run": 1}]})
        # r2 exists but has no result
        ctx.task_results["2a_r2"] = TaskExecutionResult(
            task_id="2a_r2",
            status=TaskStatus.FAILED,
            result=None,
        )
        self._add_result(ctx, "2a_r3", {"reactions": [{"run": 3}]})

        result = ctx.get_replicated_task_data("2a")

        assert len(result) == 2
        assert result[0] == {"reactions": [{"run": 1}]}
        assert result[1] == {"reactions": [{"run": 3}]}

    def test_does_not_match_base_id_directly(self) -> None:
        """A task stored under the bare base_id is not confused with replicas."""
        ctx = self._make_context()
        self._add_result(ctx, "2a", {"reactions": []})  # non-replicated result

        assert ctx.get_replicated_task_data("2a") is None

    def test_does_not_match_unrelated_tasks(self) -> None:
        """Tasks like '2a_extra' or '12a_r1' are not matched for base_id '2a'."""
        ctx = self._make_context()
        self._add_result(ctx, "12a_r1", {"reactions": []})
        self._add_result(ctx, "2a_extra", {"reactions": []})

        assert ctx.get_replicated_task_data("2a") is None


class TestExecutionContextActiveTasks:
    """Tests for ExecutionContext active task tracking."""

    def test_mark_task_started_tracks_multiple_active_tasks(self) -> None:
        ctx = ExecutionContext(plan_id="test")

        ctx.mark_task_started("1", agent_id="agent-a", started_at="2026-03-31T12:00:00")
        ctx.mark_task_started("2", agent_id="agent-b", started_at="2026-03-31T12:00:01")

        assert ctx.active_tasks == {
            "1": {
                "task_id": "1",
                "agent_id": "agent-a",
                "started_at": "2026-03-31T12:00:00",
            },
            "2": {
                "task_id": "2",
                "agent_id": "agent-b",
                "started_at": "2026-03-31T12:00:01",
            },
        }

    def test_mark_task_finished_updates_active_tasks_until_empty(self) -> None:
        ctx = ExecutionContext(plan_id="test")
        ctx.mark_task_started("1", agent_id="agent-a", started_at="2026-03-31T12:00:00")
        ctx.mark_task_started("2", agent_id="agent-b", started_at="2026-03-31T12:00:01")

        ctx.mark_task_finished("1")
        assert list(ctx.active_tasks.keys()) == ["2"]

        ctx.mark_task_finished("2")
        assert ctx.active_tasks == {}

    def test_checkpoint_round_trip_preserves_active_tasks(self) -> None:
        ctx = ExecutionContext(plan_id="test", session_id="session-1")
        ctx.mark_task_started("1", agent_id="agent-a", started_at="2026-03-31T12:00:00")
        checkpoint = ctx.to_checkpoint()

        restored = ExecutionContext.from_checkpoint(checkpoint)

        assert restored.active_tasks == {
            "1": {
                "task_id": "1",
                "agent_id": "agent-a",
                "started_at": "2026-03-31T12:00:00",
            }
        }


# ======================================================================
# TaskDispatcher replicated step fallback Tests
# ======================================================================


class TestTaskDispatcherReplicateFallback:
    """Tests for TaskDispatcher resolving {{stepX}} when step X was replicated."""

    def _make_dispatcher(self) -> TaskDispatcher:
        return TaskDispatcher(memory_manager=MemoryManager(), model_manager=None)

    def _make_context_with_replicas(self, base_id: str,
                                    payloads: list) -> ExecutionContext:
        ctx = ExecutionContext(plan_id="test")
        for i, data in enumerate(payloads, start=1):
            task_id = f"{base_id}_r{i}"
            ctx.task_results[task_id] = TaskExecutionResult(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=TaskResult(agent_id="agent", action="run", data=data),
            )
        return ctx

    def test_resolves_replicated_step_as_list(self) -> None:
        """{{step2a}} returns a list when 2a_r1/r2/r3 exist but 2a does not."""
        payloads = [
            {
                "reactions": [{
                    "enzyme": "A"
                }]
            },
            {
                "reactions": [{
                    "enzyme": "B"
                }]
            },
            {
                "reactions": [{
                    "enzyme": "C"
                }]
            },
        ]
        ctx = self._make_context_with_replicas("2a", payloads)
        dispatcher = self._make_dispatcher()

        resolved = dispatcher._resolve_inputs({"text_extraction_data": "{{step2a}}"},
                                              ctx)

        result = resolved["text_extraction_data"]
        assert isinstance(result, list)
        assert len(result) == 3
        # Structured data is extracted from the parsed_output / content layer
        assert result[0]["reactions"][0]["enzyme"] == "A"
        assert result[1]["reactions"][0]["enzyme"] == "B"
        assert result[2]["reactions"][0]["enzyme"] == "C"

    def test_returns_none_when_neither_direct_nor_replicated(self) -> None:
        """{{step2a}} resolves to None when no task with that ID exists."""
        ctx = ExecutionContext(plan_id="test")
        dispatcher = self._make_dispatcher()

        resolved = dispatcher._resolve_inputs({"data": "{{step2a}}"}, ctx)

        assert resolved["data"] is None

    def test_resolves_replicated_step_field_as_list(self) -> None:
        """{{step2a.images}} returns the selected field from each replica."""
        payloads = [
            {
                "images": ["fig1.png"],
                "reactions": [{
                    "enzyme": "A"
                }]
            },
            {
                "images": ["fig2.png"],
                "reactions": [{
                    "enzyme": "B"
                }]
            },
            {
                "images": ["fig3.png"],
                "reactions": [{
                    "enzyme": "C"
                }]
            },
        ]
        ctx = self._make_context_with_replicas("2a", payloads)
        dispatcher = self._make_dispatcher()

        resolved = dispatcher._resolve_inputs({"images": "{{step2a.images}}"}, ctx)

        assert resolved["images"] == [["fig1.png"], ["fig2.png"], ["fig3.png"]]

    def test_direct_step_still_resolves_normally(self) -> None:
        """Non-replicated steps continue to resolve as a single dict."""
        ctx = ExecutionContext(plan_id="test")
        ctx.task_results["1"] = TaskExecutionResult(
            task_id="1",
            status=TaskStatus.COMPLETED,
            result=TaskResult(
                agent_id="agent",
                action="run",
                data={"images": ["fig1.png", "fig2.png"]},
            ),
        )
        dispatcher = self._make_dispatcher()

        resolved = dispatcher._resolve_inputs({"images": "{{step1.images}}"}, ctx)

        assert resolved["images"] == ["fig1.png", "fig2.png"]
