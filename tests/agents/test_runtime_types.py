"""Unit tests for gptase.agents.runtime_types — pydantic dataclasses
for the interactive Coordinator runtime.

Covers the live surface (1 enum + 8 dataclasses, all active per L0 #11
audit). The shared `model_config = ConfigDict(use_enum_values=True)`
contract is pinned via the InteractiveRuntimeResult dump test —
removing it would silently flip JSON serialization of every enum field
across the runtime layer.
"""
from gptase.agents.runtime_types import CoordinatorRuntimeSummary
from gptase.agents.runtime_types import CoordinatorTurnSummary
from gptase.agents.runtime_types import CoordinatorWorkerResult
from gptase.agents.runtime_types import InteractiveRuntimeResult
from gptase.agents.runtime_types import InteractiveRuntimeSnapshot
from gptase.agents.runtime_types import InteractiveSessionState
from gptase.agents.runtime_types import InteractiveToolResult
from gptase.agents.runtime_types import InteractiveTurn
from gptase.agents.runtime_types import RuntimeStopReason


class TestRuntimeStopReason:
    """Terminal conditions for the interactive runtime."""

    def test_enum_string_values_pin_terminal_conditions(self):
        # These strings are emitted into JSON via use_enum_values=True
        # and consumed by tools/executor.py:88 + downstream UI traces;
        # renames are not silent.
        assert RuntimeStopReason.FINAL_ANSWER.value == "final_answer"
        assert RuntimeStopReason.MAX_TURNS.value == "max_turns"
        assert RuntimeStopReason.NEEDS_USER_INPUT.value == "needs_user_input"
        assert RuntimeStopReason.ERROR.value == "error"


class TestCoordinatorWorkerResult:
    """Single delegated worker result."""

    def test_minimal_with_required_agent_id_and_default_status(self):
        result = CoordinatorWorkerResult(agent_id="vision-image-analyzer")

        assert result.agent_id == "vision-image-analyzer"
        assert result.status == "success"
        assert result.content == ""
        assert result.error is None


class TestCoordinatorTurnSummary:
    """One Coordinator runtime turn that delegated tasks."""

    def test_default_factories_for_lists_and_counts(self):
        turn = CoordinatorTurnSummary(turn_index=0)

        assert turn.turn_index == 0
        assert turn.delegation_count == 0
        assert turn.delegated_agents == []
        assert turn.worker_results == []
        assert turn.assistant_content == ""
        assert turn.stop_reason is None


class TestCoordinatorRuntimeSummary:
    """Aggregate Coordinator delegation summary across an entire run."""

    def test_default_aggregator_state(self):
        summary = CoordinatorRuntimeSummary()

        assert summary.turn_count == 0
        assert summary.delegation_count == 0
        assert summary.delegated_agents == []
        assert summary.worker_results == []
        assert summary.turns == []


class TestInteractiveToolResult:
    """Normalized payload for a single executed tool call (trace entry)."""

    def test_arguments_default_dict_optional_error_type(self):
        result = InteractiveToolResult(tool_name="Read")

        assert result.tool_name == "Read"
        assert result.arguments == {}
        assert result.content == ""
        assert result.error_type is None


class TestInteractiveTurn:
    """One completed interactive runtime turn."""

    def test_required_turn_index_and_default_lists(self):
        turn = InteractiveTurn(turn_index=3)

        assert turn.turn_index == 3
        assert turn.assistant_content == ""
        assert turn.reasoning_content is None
        assert turn.tool_results == []
        assert turn.stop_reason is None


class TestInteractiveRuntimeSnapshot:
    """Serializable checkpoint for resuming a runtime session."""

    def test_default_token_and_duration_counters(self):
        snap = InteractiveRuntimeSnapshot()

        assert snap.messages == []
        assert snap.turns == []
        assert snap.steps == []
        assert snap.total_input_tokens == 0
        assert snap.total_output_tokens == 0
        assert snap.total_duration_ms == 0


class TestInteractiveRuntimeResult:
    """Terminal output from the interactive runtime."""

    def test_required_stop_reason_and_snapshot(self):
        snap = InteractiveRuntimeSnapshot()
        result = InteractiveRuntimeResult(
            stop_reason=RuntimeStopReason.FINAL_ANSWER,
            snapshot=snap,
        )

        assert result.stop_reason == RuntimeStopReason.FINAL_ANSWER.value
        assert result.snapshot is snap
        assert result.content == ""
        assert result.reasoning is None
        assert result.turn_count == 0
        assert result.usage == {}
        assert result.error is None
        assert result.coordinator_summary is None

    def test_model_dump_serializes_enum_as_string(self):
        # ConfigDict(use_enum_values=True) flips enum fields to their
        # .value when dumped — pin the wire format that JSON serializers,
        # the web UI, and persisted traces all consume.
        result = InteractiveRuntimeResult(
            stop_reason=RuntimeStopReason.MAX_TURNS,
            snapshot=InteractiveRuntimeSnapshot(),
        )

        dumped = result.model_dump()

        assert dumped["stop_reason"] == "max_turns"
        assert isinstance(dumped["stop_reason"], str)


class TestInteractiveSessionState:
    """In-flight runtime state — extends InteractiveRuntimeSnapshot."""

    def test_extends_snapshot_with_turn_index_and_max_turns(self):
        state = InteractiveSessionState()

        # New runtime control fields:
        assert state.turn_index == 0
        assert state.max_turns == 10

        # Inherited snapshot fields preserved:
        assert state.messages == []
        assert state.turns == []
        assert state.steps == []
        assert state.total_input_tokens == 0
        assert state.total_output_tokens == 0
        assert state.total_duration_ms == 0
