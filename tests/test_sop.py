"""Tests for the SOP module."""

from pathlib import Path
from typing import Any, Dict

import pytest

from gptase.sop import ExecutionContext
from gptase.sop import FailureDecision
from gptase.sop import ParallelStep
from gptase.sop import SOPDefinition
from gptase.sop import SOPLoader
from gptase.sop import SOPNotFoundError
from gptase.sop import SOPRegistry
from gptase.sop import SOPStep
from gptase.sop import SOPValidationError
from gptase.sop import StepResult
from gptase.sop import StepStatus
from gptase.sop import TaskResult
from gptase.sop.dispatcher import TaskDispatcher
from gptase.sop.failure_handler import FailureHandler


class TestSOPStep:
    """Tests for SOPStep model."""

    def test_step_creation(self) -> None:
        """Test creating a basic step."""
        step = SOPStep(
            step_id="1",
            agent="test_agent",
            action="process",
            description="Test step",
            inputs={"text": "{{input_text}}"},
        )
        assert step.step_id == "1"
        assert step.agent == "test_agent"
        assert step.action == "process"
        assert step.retry_count == 0
        assert not step.optional

    def test_step_id_conversion(self) -> None:
        """Test that integer step_id is converted to string."""
        step = SOPStep(step_id=1, agent="test_agent")
        assert step.step_id == "1"
        assert isinstance(step.step_id, str)

    def test_step_defaults(self) -> None:
        """Test default values for optional fields."""
        step = SOPStep(step_id="test", agent="agent")
        assert step.action == "process"
        assert step.description == ""
        assert step.inputs == {}
        assert step.retry_count == 0
        assert not step.optional


class TestParallelStep:
    """Tests for ParallelStep model."""

    def test_parallel_step_creation(self) -> None:
        """Test creating a parallel step group."""
        steps = [
            SOPStep(step_id="2a", agent="agent_a"),
            SOPStep(step_id="2b", agent="agent_b"),
        ]
        parallel = ParallelStep(parallel=steps)
        assert len(parallel.parallel) == 2
        assert parallel.parallel[0].step_id == "2a"


class TestSOPDefinition:
    """Tests for SOPDefinition model."""

    def test_definition_creation(self) -> None:
        """Test creating an SOP definition."""
        sop = SOPDefinition(
            plan_id="test_pipeline",
            name="Test Pipeline",
            description="A test pipeline",
            workflow=[
                SOPStep(step_id="1", agent="agent_a"),
                ParallelStep(parallel=[
                    SOPStep(step_id="2a", agent="agent_b"),
                    SOPStep(step_id="2b", agent="agent_c"),
                ]),
            ],
        )
        assert sop.plan_id == "test_pipeline"
        assert len(sop.workflow) == 2
        assert sop.version == "1.0"

    def test_workflow_parsing(self) -> None:
        """Test parsing workflow from dicts."""
        data = {
            "plan_id":
            "test",
            "workflow": [
                {
                    "step_id": "1",
                    "agent": "agent_a"
                },
                {
                    "parallel": [
                        {
                            "step_id": "2a",
                            "agent": "agent_b"
                        },
                    ]
                },
            ],
        }
        sop = SOPDefinition(**data)
        assert len(sop.workflow) == 2
        assert isinstance(sop.workflow[0], SOPStep)
        assert isinstance(sop.workflow[1], ParallelStep)

    def test_get_all_steps(self) -> None:
        """Test flattening all steps."""
        sop = SOPDefinition(
            plan_id="test",
            workflow=[
                SOPStep(step_id="1", agent="a"),
                ParallelStep(parallel=[
                    SOPStep(step_id="2a", agent="b"),
                    SOPStep(step_id="2b", agent="c"),
                ]),
                SOPStep(step_id="3", agent="d"),
            ],
        )
        all_steps = sop.get_all_steps()
        assert len(all_steps) == 4
        assert [s.step_id for s in all_steps] == ["1", "2a", "2b", "3"]

    def test_get_step_by_id(self) -> None:
        """Test finding a step by ID."""
        sop = SOPDefinition(
            plan_id="test",
            workflow=[
                SOPStep(step_id="1", agent="a"),
                SOPStep(step_id="2", agent="b"),
            ],
        )
        step = sop.get_step_by_id("2")
        assert step is not None
        assert step.agent == "b"

        assert sop.get_step_by_id("99") is None


class TestTaskResult:
    """Tests for TaskResult model."""

    def test_success_result(self) -> None:
        """Test a successful task result."""
        result = TaskResult(
            agent_id="test_agent",
            step_id="1",
            status="success",
            data={"output": "test"},
        )
        assert result.is_success()
        assert not result.is_failed()

    def test_failed_result(self) -> None:
        """Test a failed task result."""
        result = TaskResult(
            agent_id="test_agent",
            status="failed",
            error="Something went wrong",
        )
        assert not result.is_success()
        assert result.is_failed()


class TestExecutionContext:
    """Tests for ExecutionContext model."""

    def test_context_creation(self) -> None:
        """Test creating an execution context."""
        context = ExecutionContext(
            plan_id="test",
            input_data={"text": "hello"},
        )
        assert context.plan_id == "test"
        assert context.input_data["text"] == "hello"

    def test_step_result_management(self) -> None:
        """Test managing step results."""
        context = ExecutionContext(plan_id="test")

        result = TaskResult(agent_id="agent",
                            step_id="1",
                            status="success",
                            data={"x": 1})
        step_result = StepResult(step_id="1", status=StepStatus.SUCCESS, result=result)

        context.update_step_result("1", step_result)

        assert context.get_step_result("1") == step_result
        assert context.get_step_data("1") == {"x": 1}
        assert context.get_step_data("99") is None

    def test_variable_management(self) -> None:
        """Test managing variables."""
        context = ExecutionContext(plan_id="test")
        context.set_variable("key", "value")
        assert context.get_variable("key") == "value"
        assert context.get_variable("missing", "default") == "default"

    def test_to_result(self) -> None:
        """Test converting to result dictionary."""
        context = ExecutionContext(
            plan_id="test",
            session_id="session_123",
        )
        result = TaskResult(agent_id="agent",
                            step_id="1",
                            status="success",
                            data={"x": 1})
        step_result = StepResult(step_id="1", status=StepStatus.SUCCESS, result=result)
        context.update_step_result("1", step_result)

        result = context.to_result()
        assert result["plan_id"] == "test"
        assert result["session_id"] == "session_123"
        assert "1" in result["step_results"]


class TestSOPLoader:
    """Tests for SOPLoader class."""

    def test_list_available_sops(self) -> None:
        """Test listing available SOPs."""
        loader = SOPLoader()
        sops = loader.list_available_sops()
        assert len(sops) > 0
        # Should have at least the enzyme_extraction_pipeline
        plan_ids = [s["plan_id"] for s in sops]
        assert "enzyme_extraction_pipeline" in plan_ids

    def test_load_yaml_sop(self) -> None:
        """Test loading a YAML SOP definition."""
        loader = SOPLoader()
        sop = loader.load("enzyme_extraction_pipeline")
        assert sop.plan_id == "enzyme_extraction_pipeline"
        assert sop.name == "Standard Enzyme Extraction Pipeline"
        assert len(sop.workflow) == 3

    def test_sop_not_found(self) -> None:
        """Test error when SOP not found."""
        loader = SOPLoader()
        with pytest.raises(SOPNotFoundError):
            loader.load("nonexistent_sop")

    def test_exists(self) -> None:
        """Test checking if SOP exists."""
        loader = SOPLoader()
        assert loader.exists("enzyme_extraction_pipeline")
        assert not loader.exists("nonexistent_sop")


class TestSOPRegistry:
    """Tests for SOPRegistry singleton."""

    def test_singleton(self) -> None:
        """Test that registry is a singleton."""
        SOPRegistry.reset_instance()
        registry1 = SOPRegistry.get_instance()
        registry2 = SOPRegistry.get_instance()
        assert registry1 is registry2
        SOPRegistry.reset_instance()

    def test_list_sops(self) -> None:
        """Test listing SOPs via registry."""
        SOPRegistry.reset_instance()
        registry = SOPRegistry.get_instance()
        sops = registry.list_sops()
        assert len(sops) > 0
        SOPRegistry.reset_instance()


class TestFailureHandler:
    """Tests for FailureHandler class."""

    def test_optional_step_skip(self) -> None:
        """Test that optional steps are skipped."""
        handler = FailureHandler()
        step = SOPStep(step_id="1", agent="test", optional=True)
        decision = handler.should_skip_on_failure(step)
        assert decision is True

    def test_heuristic_retry_patterns(self) -> None:
        """Test heuristic retry decision."""
        handler = FailureHandler()
        step = SOPStep(step_id="1", agent="test")
        context = ExecutionContext(plan_id="test")

        # Test timeout error
        decision = handler._heuristic_decide(step, "Connection timeout", 0)
        assert decision == FailureDecision.RETRY

        # Test rate limit error
        decision = handler._heuristic_decide(step, "Rate limit exceeded", 0)
        assert decision == FailureDecision.RETRY

    def test_heuristic_abort_patterns(self) -> None:
        """Test heuristic abort decision."""
        handler = FailureHandler()
        step = SOPStep(step_id="1", agent="test")

        # Test not found error
        decision = handler._heuristic_decide(step, "Resource not found", 0)
        assert decision == FailureDecision.ABORT

        # Test unauthorized error
        decision = handler._heuristic_decide(step, "Unauthorized access", 0)
        assert decision == FailureDecision.ABORT


class TestTaskDispatcher:
    """Tests for TaskDispatcher class."""

    def test_resolve_inputs(self) -> None:
        """Test input template resolution."""
        # Create a mock dispatcher (without full setup)
        from unittest.mock import Mock

        dispatcher = TaskDispatcher(
            agent_factory=Mock(),
            memory_manager=Mock(),
        )

        context = ExecutionContext(
            plan_id="test",
            input_data={
                "text": "hello world",
                "document_path": "/path/to/doc"
            },
            document_path="/path/to/doc",
        )

        # Add step result
        result = TaskResult(agent_id="agent",
                            step_id="1",
                            status="success",
                            data={"analysis": {
                                "images": ["img1.png"]
                            }})
        step_result = StepResult(step_id="1", status=StepStatus.SUCCESS, result=result)
        context.update_step_result("1", step_result)

        # Test simple variable
        inputs = {"text": "{{input_text}}"}
        resolved = dispatcher._resolve_inputs(inputs, context)
        assert resolved["text"] == "hello world"

        # Test step reference
        inputs = {"images": "{{step1.analysis.images}}"}
        resolved = dispatcher._resolve_inputs(inputs, context)
        assert resolved["images"] == ["img1.png"]

    def test_get_nested_field(self) -> None:
        """Test nested field access."""
        from unittest.mock import Mock

        dispatcher = TaskDispatcher(
            agent_factory=Mock(),
            memory_manager=Mock(),
        )

        data = {"analysis": {"images": ["img1", "img2"], "nested": {"value": 42}}}

        assert dispatcher._get_nested_field(data, "analysis.images") == ["img1", "img2"]
        assert dispatcher._get_nested_field(data, "analysis.nested.value") == 42
        assert dispatcher._get_nested_field(data, "missing.field") is None
