"""Unit tests for gptase.agents.types — agent definition + Task + session types.

Covers the live surface after L0 #12 refactor:
- AgentDefinition (dataclass) — markdown frontmatter parse target
- Task (BaseModel) — work unit consumed by Agent.process_task
- SessionType / DirectSessionStatus enums
- SessionMessage / SessionTrace / DirectSession persistence dataclasses

Dead members removed in the immediately prior refactor commit (AgentState,
TaskStatus, SessionType.PLAN, 9 Plan-mode Task fields, 3 Task helper
methods) are intentionally not covered.
"""
from datetime import datetime

from gptase.agents.types import AgentDefinition
from gptase.agents.types import DirectSession
from gptase.agents.types import DirectSessionStatus
from gptase.agents.types import SessionMessage
from gptase.agents.types import SessionTrace
from gptase.agents.types import SessionType
from gptase.agents.types import Task


class TestAgentDefinition:
    """Parsed agent definition from markdown frontmatter + body."""

    def test_minimal_with_name_and_defaults(self):
        defn = AgentDefinition(name="my-agent")

        assert defn.name == "my-agent"
        assert defn.description == ""
        assert defn.tools == []
        assert defn.system_prompt == ""
        assert defn.skills == []
        assert defn.max_iterations == 10
        assert defn.auto_resolve_artifacts is False

    def test_full_construction_with_all_flags(self):
        defn = AgentDefinition(
            name="enzyme-variant-normalizer",
            description="Normalize enzyme replicas",
            tools=["NormalizeEnzymeVariants"],
            system_prompt="You normalize variants...",
            skills=["biochem_databases"],
            max_iterations=20,
            auto_resolve_artifacts=True,
        )

        assert defn.name == "enzyme-variant-normalizer"
        assert defn.tools == ["NormalizeEnzymeVariants"]
        assert defn.skills == ["biochem_databases"]
        assert defn.max_iterations == 20
        assert defn.auto_resolve_artifacts is True

    def test_agent_id_property_aliases_name(self):
        # agent_id is the documented public alias used at multiple call
        # sites in core/orchestrator.py and tools/handlers.py.
        defn = AgentDefinition(name="planner")

        assert defn.agent_id == "planner"
        assert defn.agent_id is defn.name


class TestTask:
    """Basic unit of work consumed by Agent.process_task."""

    def test_default_factories_for_id_and_inputs(self):
        task = Task()

        assert task.task_id.startswith("task_")
        assert len(task.task_id) == 13  # "task_" + 8 hex chars
        assert task.description == "Process the following data"
        assert task.action == "process"
        assert task.workspace_dir is None
        assert task.agent_id is None
        assert task.inputs == {}
        assert task.image_path is None
        assert task.image_paths is None
        assert task.images is None

    def test_from_dict_classmethod_round_trip(self):
        # Pin the contract used by orchestrator.py:157 — Task.from_dict
        # accepts a dict and produces a populated instance.
        data = {
            "task_id": "fixed-id",
            "description": "extract enzymes",
            "agent_id": "enzyme-extractor",
            "workspace_dir": "/data/output",
            "image_paths": ["/a.png", "/b.png"],
        }

        task = Task.from_dict(data)

        assert task.task_id == "fixed-id"
        assert task.description == "extract enzymes"
        assert task.agent_id == "enzyme-extractor"
        assert task.workspace_dir == "/data/output"
        assert task.image_paths == ["/a.png", "/b.png"]

    def test_extra_keys_preserved_via_allow_config(self):
        # ConfigDict(extra="allow") absorbs forward-compat / spread kwargs
        # without raising — orchestrator.py:157 spreads
        # **request.model_dump(exclude_none=True) so unknown fields must
        # not break Task construction.
        task = Task(description="x", forwarded_flag=True, legacy_field="kept")

        assert task.model_extra is not None
        assert task.model_extra["forwarded_flag"] is True
        assert task.model_extra["legacy_field"] == "kept"


class TestSessionType:
    """Top-level session type surfaced to the web UI."""

    def test_enum_string_values(self):
        # Two members remain after Slice 1-5 plan-mode removal — the wire
        # values are persisted to SQLite session rows.
        assert SessionType.CHAT.value == "chat"
        assert SessionType.AGENT.value == "agent"
        assert {member.value for member in SessionType} == {"chat", "agent"}


class TestDirectSessionStatus:
    """Lifecycle status for direct chat/agent sessions."""

    def test_enum_string_values(self):
        assert DirectSessionStatus.DRAFT.value == "draft"
        assert DirectSessionStatus.IN_PROGRESS.value == "in_progress"
        assert DirectSessionStatus.COMPLETED.value == "completed"
        assert DirectSessionStatus.FAILED.value == "failed"


class TestSessionMessage:
    """Persisted message in the session message thread."""

    def test_default_timestamp_and_metadata(self):
        msg = SessionMessage(id="msg-1", role="user", content="hi")

        assert msg.id == "msg-1"
        assert msg.role == "user"
        assert msg.content == "hi"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}


class TestSessionTrace:
    """Persisted execution trace item for direct sessions."""

    def test_default_timestamp_and_details(self):
        trace = SessionTrace(
            id="trace-1",
            step_id="step-1",
            type="tool_call",
            message="Read /tmp/x",
        )

        assert trace.id == "trace-1"
        assert trace.step_id == "step-1"
        assert trace.type == "tool_call"
        assert trace.message == "Read /tmp/x"
        assert isinstance(trace.timestamp, datetime)
        assert trace.details == {}


class TestDirectSession:
    """Persistent direct session for chat and worker-agent modes."""

    def test_minimal_required_fields_with_default_status(self):
        session = DirectSession(
            session_id="sess-1",
            session_type=SessionType.CHAT,
            title="My chat",
            agent_id="orchestrator",
        )

        assert session.session_id == "sess-1"
        assert session.session_type == SessionType.CHAT
        assert session.title == "My chat"
        assert session.agent_id == "orchestrator"
        assert session.status == DirectSessionStatus.DRAFT
        assert session.messages == []
        assert session.traces == []
        assert session.metadata == {}
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)
