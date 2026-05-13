"""Unit tests for gptase.memory.models — pydantic dataclasses for the
SQLite-backed conversation/extraction/agent persistence layer.

Covers the live surface after L0 #10 refactor: 3 enums + 7 dataclasses.
The auto-id, auto-timestamp factories and the AgentMessage custom
__init__ are pinned explicitly. Enum string values are pinned because
they are persisted to SQLite — renames break existing rows.

Dead members removed in the immediately prior refactor commit
(MessageRole, Message, ExtractionResult) are intentionally not covered.
"""
from datetime import datetime

from gptase.memory.models import AgentMessage
from gptase.memory.models import AgentWorkingMemory
from gptase.memory.models import Conversation
from gptase.memory.models import ConversationStatus
from gptase.memory.models import ExtractionSession
from gptase.memory.models import ExtractionSessionStatus
from gptase.memory.models import ExtractionSessionStep
from gptase.memory.models import ExtractionStepStatus
from gptase.memory.models import PersistedAgentState
from gptase.memory.models import Response


class TestConversationModel:
    """One LLM interaction tracked in the SQLite conversations table."""

    def test_default_factories_generate_id_timestamp_status(self):
        conv = Conversation(model_name="gpt-4", provider="openai")

        assert conv.id and isinstance(conv.id, str)
        assert isinstance(conv.timestamp, datetime)
        assert conv.status == ConversationStatus.IN_PROGRESS
        assert conv.metadata == {}
        # Optional cost/duration default to None — ledger fills them later
        assert conv.total_duration_seconds is None
        assert conv.estimated_cost_usd is None
        assert conv.error_message is None
        assert conv.agent_id is None

    def test_explicit_fields_override_defaults(self):
        conv = Conversation(
            id="conv-fixed",
            model_name="claude-opus-4-7",
            provider="anthropic",
            agent_id="enzyme-extractor",
            status=ConversationStatus.COMPLETED,
            total_duration_seconds=12.5,
            estimated_cost_usd=0.04,
            metadata={"trace_id": "abc"},
        )

        assert conv.id == "conv-fixed"
        assert conv.model_name == "claude-opus-4-7"
        assert conv.provider == "anthropic"
        assert conv.agent_id == "enzyme-extractor"
        assert conv.status == ConversationStatus.COMPLETED
        assert conv.total_duration_seconds == 12.5
        assert conv.estimated_cost_usd == 0.04
        assert conv.metadata == {"trace_id": "abc"}


class TestResponseModel:
    """LLM response payload stored alongside its conversation."""

    def test_minimal_construction_with_required_fields(self):
        resp = Response(conversation_id="conv-1", content="hello")

        assert resp.id and isinstance(resp.id, str)
        assert resp.conversation_id == "conv-1"
        assert resp.content == "hello"
        # Token / latency fields default to None — provider may not always
        # report them; ledger handles the absence downstream.
        assert resp.prompt_tokens is None
        assert resp.completion_tokens is None
        assert resp.total_tokens is None
        assert resp.latency_seconds is None
        assert isinstance(resp.timestamp, datetime)


class TestExtractionSessionModel:
    """One extraction workflow run grouping multiple LLM calls."""

    def test_defaults_status_in_progress_started_at_set(self):
        session = ExtractionSession(
            document_path="/data/papers/listov2025.md",
            extraction_type="enzyme_kinetics",
            agent_id="enzyme-kinetics-extractor",
        )

        assert session.id and isinstance(session.id, str)
        assert session.status == ExtractionSessionStatus.IN_PROGRESS
        assert session.total_llm_calls == 0
        assert session.phase is None
        assert isinstance(session.started_at, datetime)
        assert session.completed_at is None


class TestExtractionSessionStepModel:
    """A step within an extraction session."""

    def test_default_status_pending(self):
        step = ExtractionSessionStep(
            session_id="sess-1",
            step_name="extract_kinetics",
            step_phase="extraction",
            step_order=1,
        )

        assert step.id and isinstance(step.id, str)
        assert step.status == ExtractionStepStatus.PENDING
        assert step.started_at is None
        assert step.completed_at is None
        assert step.error_message is None
        assert step.conversation_id is None


class TestPersistedAgentStateModel:
    """Cached agent runtime state persisted to SQLite (distinct from
    in-memory gptase.agents.base.AgentState)."""

    def test_state_data_required_field(self):
        state = PersistedAgentState(agent_id="planner", state_data='{"step": 3}')

        assert state.agent_id == "planner"
        assert state.state_data == '{"step": 3}'
        assert isinstance(state.last_updated, datetime)


class TestAgentMessageCustomInit:
    """AgentMessage overrides __init__ to auto-fill timestamp.

    timestamp is declared Optional[datetime] = None (not default_factory),
    and the custom init sets datetime.now() when omitted. This is the
    only behavior in the file beyond pydantic defaults.
    """

    def test_timestamp_auto_filled_when_omitted(self):
        msg = AgentMessage(sender="planner", recipient="executor", content="run")

        assert isinstance(msg.timestamp, datetime)

    def test_explicit_timestamp_preserved(self):
        fixed = datetime(2026, 1, 1, 12, 0, 0)
        msg = AgentMessage(sender="a", recipient="b", content="x", timestamp=fixed)

        assert msg.timestamp == fixed

    def test_content_accepts_arbitrary_payload(self):
        # `content: Any` is documented — non-string payloads must round-trip.
        payload = {"task": "extract", "params": [1, 2, 3]}
        msg = AgentMessage(sender="a",
                           recipient="b",
                           content=payload,
                           message_type="task_request")

        assert msg.content == payload
        assert msg.message_type == "task_request"


class TestAgentWorkingMemoryModel:
    """Persistent working memory summary keyed by agent name."""

    def test_minimal_construction_with_id_and_summary(self):
        mem = AgentWorkingMemory(
            agent_id="enzyme-kinetics-extractor",
            summary="Extracted 3 papers; saw novel phosphoryl-transfer pattern.",
        )

        assert mem.agent_id == "enzyme-kinetics-extractor"
        assert "phosphoryl" in mem.summary
        assert mem.metadata == {}
        assert isinstance(mem.last_updated, datetime)


class TestStringEnumsPinDbValues:
    """The enums are persisted as strings in SQLite columns; renaming
    a value breaks existing rows. Pin the on-disk wire values so a
    refactor must consciously update the schema migration.
    """

    def test_enum_string_values_match_db_persistence(self):
        # ConversationStatus
        assert ConversationStatus.IN_PROGRESS.value == "in_progress"
        assert ConversationStatus.COMPLETED.value == "completed"
        assert ConversationStatus.ERROR.value == "error"

        # ExtractionSessionStatus
        assert ExtractionSessionStatus.IN_PROGRESS.value == "in_progress"
        assert ExtractionSessionStatus.COMPLETED.value == "completed"
        assert ExtractionSessionStatus.FAILED.value == "failed"
        assert ExtractionSessionStatus.PARTIAL.value == "partial"

        # ExtractionStepStatus
        assert ExtractionStepStatus.PENDING.value == "pending"
        assert ExtractionStepStatus.IN_PROGRESS.value == "in_progress"
        assert ExtractionStepStatus.COMPLETED.value == "completed"
        assert ExtractionStepStatus.FAILED.value == "failed"
