"""Tests for the PlanningTool."""

import json
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.tools.base import ToolResult
from src.tools.planner_tool import Plan
from src.tools.planner_tool import PlanningTool
from src.tools.planner_tool import PlanState
from src.tools.planner_tool import WorkflowStep


@pytest.fixture
def mock_model_manager():
    """Create mock model manager."""
    manager = MagicMock()
    manager.generate = AsyncMock()
    return manager


@pytest.fixture
def plan_state():
    """Create plan state fixture."""
    return PlanState()


@pytest.fixture
def workflow_step():
    """Create workflow step fixture."""
    return WorkflowStep(
        step_id=1,
        agent="enzyme_kinetics_extractor",
        action="extract_kinetics",
        inputs={"document_path": "data/test.md"},
        description="Extract kinetic parameters",
    )


@pytest.fixture
def sample_plan():
    """Create sample plan fixture."""
    return Plan(
        plan_id="plan_20250204_123456",
        task={"description": "Test task"},
        workflow=[
            WorkflowStep(
                step_id=1,
                agent="enzyme_kinetics_extractor",
                action="extract_kinetics",
                inputs={"document_path": "data/test.md"},
                description="Extract kinetics",
            )
        ],
        phases=PlanState(),
        status="pending",
        metadata={"created_at": "2025-02-04T12:00:00"},
    )


class TestPlanningTool:
    """Test PlanningTool functionality."""

    def test_initialization(self, mock_model_manager, tmp_path):
        """Test PlanningTool initialization."""
        tool = PlanningTool(
            model_manager=mock_model_manager,
            agent_id="test_agent",
            session_id="test_session",
            step_id="test_step",
            plans_dir=tmp_path,
        )

        assert tool.name == "planner"
        assert tool.plans_dir == tmp_path
        assert tmp_path.exists()

    @pytest.mark.asyncio
    async def test_execute_phase_1(self, mock_model_manager, tmp_path):
        """Test Phase 1 execution."""
        # Mock LLM response
        mock_model_manager.generate.return_value = MagicMock(
            content=json.dumps({
                "understanding": "Test understanding",
                "questions": ["Question 1?", "Question 2?"],
                "suggestions": ["Suggestion 1"],
            }))

        tool = PlanningTool(
            model_manager=mock_model_manager,
            plans_dir=tmp_path,
        )

        result = await tool.execute(
            task_description="Test task",
            phase=1,
            user_input="",
        )

        assert result.status == "success"
        data = result.data
        assert data["phase"] == 1
        assert data["phase_result"]["understanding"] == "Test understanding"
        assert len(data["phase_result"]["questions"]) == 2
        assert data["next_phase"] == 2

    @pytest.mark.asyncio
    async def test_execute_phase_2(self, mock_model_manager, sample_plan, tmp_path):
        """Test Phase 2 execution."""
        # Set up phase 1 results
        sample_plan.phases.phase_1 = {
            "understanding": "Test understanding",
            "questions": ["Q1"],
        }

        # Mock LLM response
        mock_model_manager.generate.return_value = MagicMock(content=json.dumps({
            "approach":
            "Test approach",
            "steps": [{
                "step_number": 1,
                "description": "Test step",
                "agent": "enzyme_kinetics_extractor",
                "action": "extract_kinetics",
                "inputs": {
                    "document_path": "test.md"
                },
            }],
            "risks": ["Risk 1"],
            "mitigations": ["Mitigation 1"],
            "estimated_duration_hours":
            2,
        }))

        tool = PlanningTool(
            model_manager=mock_model_manager,
            plans_dir=tmp_path,
        )

        # Save plan first
        tool._save_plan(sample_plan)

        result = await tool.execute(
            plan_id=sample_plan.plan_id,
            phase=2,
            user_input="Answers",
        )

        assert result.status == "success"
        data = result.data
        assert data["phase"] == 2
        assert data["phase_result"]["approach"] == "Test approach"
        assert len(data["phase_result"]["steps"]) == 1
        assert data["phase_result"]["estimated_duration_hours"] == 2

    @pytest.mark.asyncio
    async def test_execute_phase_3(self, mock_model_manager, sample_plan, tmp_path):
        """Test Phase 3 execution."""
        # Set up phase 2 results
        sample_plan.phases.phase_2 = {
            "approach": "Test approach",
            "steps": [{
                "step_number": 1
            }],
            "risks": ["Risk 1"],
        }

        # Mock LLM response
        mock_model_manager.generate.return_value = MagicMock(
            content=json.dumps({
                "plan_summary": "Test summary",
                "approved": True,
                "concerns": [],
                "modifications": [],
            }))

        tool = PlanningTool(
            model_manager=mock_model_manager,
            plans_dir=tmp_path,
        )

        tool._save_plan(sample_plan)

        result = await tool.execute(
            plan_id=sample_plan.plan_id,
            phase=3,
            user_input="Looks good",
        )

        assert result.status == "success"
        data = result.data
        assert data["phase"] == 3
        assert data["phase_result"]["approved"] is True

    @pytest.mark.asyncio
    async def test_execute_phase_4(self, mock_model_manager, sample_plan, tmp_path):
        """Test Phase 4 execution."""
        # Set up phase 2/3 results
        sample_plan.phases.phase_2 = {
            "steps": [{
                "step_number": 1,
                "agent": "enzyme_kinetics_extractor",
                "action": "extract_kinetics",
            }]
        }
        sample_plan.phases.phase_3 = {"modifications": []}

        # Mock LLM response
        mock_model_manager.generate.return_value = MagicMock(content=json.dumps({
            "workflow": [{
                "agent": "enzyme_kinetics_extractor",
                "action": "extract_kinetics",
                "inputs": {
                    "document_path": "test.md"
                },
                "description": "Extract kinetics",
            }]
        }))

        tool = PlanningTool(
            model_manager=mock_model_manager,
            plans_dir=tmp_path,
        )

        tool._save_plan(sample_plan)

        result = await tool.execute(
            plan_id=sample_plan.plan_id,
            phase=4,
            user_input="",
        )

        assert result.status == "success"
        data = result.data
        assert data["phase"] == 4
        assert data["phase_result"]["total_steps"] == 1
        assert "plan_path" in data["phase_result"]

        # Verify workflow was saved to plan
        updated_plan = tool._load_plan(sample_plan.plan_id)
        assert len(updated_plan.workflow) == 1

    @pytest.mark.asyncio
    async def test_execute_phase_5_approved(self, mock_model_manager, sample_plan,
                                            tmp_path):
        """Test Phase 5 execution with approval."""
        sample_plan.workflow = [
            WorkflowStep(
                step_id=1,
                agent="enzyme_kinetics_extractor",
                action="extract_kinetics",
                inputs={"document_path": "test.md"},
            )
        ]

        # Mock LLM response
        mock_model_manager.generate.return_value = MagicMock(
            content=json.dumps({
                "ready_to_execute": True,
                "next_steps": ["Execute step 1"],
                "warnings": [],
            }))

        tool = PlanningTool(
            model_manager=mock_model_manager,
            plans_dir=tmp_path,
        )

        tool._save_plan(sample_plan)

        result = await tool.execute(
            plan_id=sample_plan.plan_id,
            phase=5,
            user_input="Approve",
        )

        assert result.status == "success"
        data = result.data
        assert data["phase"] == 5
        assert data["ready_to_execute"] is True
        assert data["plan_status"] == "approved"

        # Verify plan status updated
        updated_plan = tool._load_plan(sample_plan.plan_id)
        assert updated_plan.status == "approved"

    @pytest.mark.asyncio
    async def test_execute_phase_5_rejected(self, mock_model_manager, sample_plan,
                                            tmp_path):
        """Test Phase 5 execution with rejection."""
        sample_plan.workflow = [
            WorkflowStep(
                step_id=1,
                agent="enzyme_kinetics_extractor",
                action="extract_kinetics",
                inputs={},
            )
        ]

        # Mock LLM response
        mock_model_manager.generate.return_value = MagicMock(
            content=json.dumps({
                "ready_to_execute": False,
                "next_steps": ["Revise plan"],
                "warnings": ["Incomplete inputs"],
            }))

        tool = PlanningTool(
            model_manager=mock_model_manager,
            plans_dir=tmp_path,
        )

        tool._save_plan(sample_plan)

        result = await tool.execute(
            plan_id=sample_plan.plan_id,
            phase=5,
            user_input="Need changes",
        )

        assert result.status == "success"
        data = result.data
        assert data["ready_to_execute"] is False
        assert data["plan_status"] == "rejected"

    def test_save_and_load_plan(self, sample_plan, tmp_path, mock_model_manager):
        """Test plan persistence."""
        tool = PlanningTool(model_manager=mock_model_manager, plans_dir=tmp_path)

        # Save plan
        tool._save_plan(sample_plan)

        # Verify file exists
        plan_path = tmp_path / f"{sample_plan.plan_id}.json"
        assert plan_path.exists()

        # Load plan
        loaded_plan = tool._load_plan(sample_plan.plan_id)

        assert loaded_plan.plan_id == sample_plan.plan_id
        assert loaded_plan.task == sample_plan.task
        assert loaded_plan.status == sample_plan.status
        assert len(loaded_plan.workflow) == len(sample_plan.workflow)

    def test_load_nonexistent_plan(self, tmp_path, mock_model_manager):
        """Test loading nonexistent plan raises error."""
        tool = PlanningTool(model_manager=mock_model_manager, plans_dir=tmp_path)

        with pytest.raises(ValueError, match="Plan not found"):
            tool._load_plan("nonexistent_plan")

    def test_generate_plan_id(self, tmp_path, mock_model_manager):
        """Test plan ID generation."""
        tool = PlanningTool(model_manager=mock_model_manager, plans_dir=tmp_path)

        plan_id_1 = tool._generate_plan_id()
        plan_id_2 = tool._generate_plan_id()

        assert plan_id_1.startswith("plan_")
        assert plan_id_2.startswith("plan_")
        assert plan_id_1 != plan_id_2

    def test_parse_json_response_valid(self, mock_model_manager):
        """Test parsing valid JSON response."""
        tool = PlanningTool(model_manager=mock_model_manager)

        content = '{"key": "value", "number": 123}'
        result = tool._parse_json_response(content)

        assert result == {"key": "value", "number": 123}

    def test_parse_json_response_with_markdown(self, mock_model_manager):
        """Test parsing JSON from markdown code block."""
        tool = PlanningTool(model_manager=mock_model_manager)

        content = '''
        Some text before.
        ```json
        {"key": "value", "number": 123}
        ```
        Some text after.
        '''
        result = tool._parse_json_response(content)

        assert result == {"key": "value", "number": 123}

    def test_parse_json_response_invalid(self, mock_model_manager):
        """Test parsing invalid JSON returns empty dict."""
        tool = PlanningTool(model_manager=mock_model_manager)

        content = "This is not JSON"
        result = tool._parse_json_response(content)

        assert result == {}


class TestWorkflowStep:
    """Test WorkflowStep model."""

    def test_workflow_step_creation(self, workflow_step):
        """Test creating workflow step."""
        assert workflow_step.step_id == 1
        assert workflow_step.agent == "enzyme_kinetics_extractor"
        assert workflow_step.action == "extract_kinetics"
        assert workflow_step.inputs == {"document_path": "data/test.md"}
        assert workflow_step.description == "Extract kinetic parameters"

    def test_workflow_step_serialization(self, workflow_step):
        """Test workflow step serialization."""
        data = workflow_step.model_dump()

        assert data["step_id"] == 1
        assert data["agent"] == "enzyme_kinetics_extractor"
        assert data["action"] == "extract_kinetics"
        assert data["inputs"] == {"document_path": "data/test.md"}


class TestPlan:
    """Test Plan model."""

    def test_plan_creation(self, sample_plan):
        """Test creating plan."""
        assert sample_plan.plan_id == "plan_20250204_123456"
        assert sample_plan.status == "pending"
        assert len(sample_plan.workflow) == 1

    def test_plan_serialization(self, sample_plan):
        """Test plan serialization."""
        data = sample_plan.model_dump()

        assert data["plan_id"] == "plan_20250204_123456"
        assert data["status"] == "pending"
        assert "workflow" in data
        assert "phases" in data
        assert "metadata" in data
