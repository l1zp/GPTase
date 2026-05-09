"""Unit tests for gptase.web.server FastAPI endpoints.

The server keeps a module-level ``orchestrator`` singleton built at
import time (FastAPI convention). Each test replaces that singleton
with an ``AsyncMock`` via ``monkeypatch.setattr`` — the route handlers
look up ``orchestrator`` by name at call time, so the swap is visible
without re-importing the module.

The ``_AGENTS_DIR`` module constant is similarly patched per test for
filesystem-touching eval routes so we never read the real
``.claude/agents/`` tree.

12 cases:

* ChatRequest backward-compat (legacy ``message`` -> ``query``).
* ``/api/agents`` orchestrator-first ordering.
* ``/api/chat`` validation (invalid session_type -> 500) + happy path.
* ``/api/sessions[/{id}]`` list passthrough + 404 on miss + hit.
* ``/api/memory/{agent_id}`` agent_id passthrough.
* ``/api/evals`` empty when no agents dir + listing with traces.
* ``/api/evals/{agent}/traces[/{filename}]`` newest-first + filename
  validation + 404 on miss.
"""
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from gptase.web.server import app
from gptase.web.server import ChatRequest


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_orch(monkeypatch):
    """Replace the module-level orchestrator singleton for one test."""
    orch = MagicMock()
    # Methods called from route handlers — return value supplied per-test.
    orch.list_available_agents = AsyncMock(return_value=[])
    orch.execute_direct_session = AsyncMock()
    orch.list_sessions = AsyncMock(return_value=[])
    orch.get_session_status = AsyncMock(return_value=None)
    orch.get_agent_working_memory = AsyncMock(return_value={})
    monkeypatch.setattr("gptase.web.server.orchestrator", orch)
    return orch


@pytest.fixture
def mock_agents_dir(monkeypatch, tmp_path):
    """Replace _AGENTS_DIR to keep eval routes off the real filesystem."""
    monkeypatch.setattr("gptase.web.server._AGENTS_DIR", tmp_path)
    return tmp_path


class TestChatRequestValidator:
    """Pydantic model_validator backwards-compat for `message` field."""

    def test_legacy_message_field_rewritten_to_query(self):
        # Frontend used to send {"message": ...}; new schema is "query".
        # The model_validator rewrites pre-validation so old clients work.
        req = ChatRequest.model_validate({
            "agent_id": "x",
            "message": "hello",
        })

        assert req.query == "hello"

    def test_modern_query_field_passes_through_unchanged(self):
        req = ChatRequest.model_validate({
            "agent_id": "x",
            "query": "hello",
        })

        assert req.query == "hello"


class TestApiAgents:
    """GET /api/agents ordering."""

    def test_orchestrator_listed_first_then_workers(self, client, mock_orch):
        mock_orch.list_available_agents = AsyncMock(return_value=[
            {
                "agent_id": "worker-a",
                "description": "first worker"
            },
            {
                "agent_id": "worker-b",
                "description": "second worker"
            },
        ])

        r = client.get("/api/agents")

        assert r.status_code == 200
        data = r.json()
        assert data[0]["id"] == "orchestrator"
        assert [a["id"] for a in data[1:]] == ["worker-a", "worker-b"]


class TestApiChat:
    """POST /api/chat — validation + execute_direct_session passthrough."""

    def test_invalid_session_type_returns_500(self, client, mock_orch):
        # The route catches ValueError and re-raises as HTTPException(500).
        r = client.post("/api/chat",
                        json={
                            "agent_id": "chat",
                            "query": "hi",
                            "session_type": "bogus",
                        })

        assert r.status_code == 500
        assert "session_type" in r.json()["detail"]
        # Should NOT have called the orchestrator on validation failure.
        mock_orch.execute_direct_session.assert_not_awaited()

    def test_happy_path_forwards_all_fields(self, client, mock_orch):
        mock_orch.execute_direct_session = AsyncMock(return_value={
            "session_id": "sess-1",
            "status": "ok"
        })

        r = client.post("/api/chat",
                        json={
                            "agent_id": "chat",
                            "query": "hello",
                            "session_id": "sess-existing",
                            "session_type": "chat",
                            "image_paths": ["/tmp/x.png"],
                        })

        assert r.status_code == 200
        assert r.json()["session_id"] == "sess-1"
        # Inspect the kwargs that reached the orchestrator.
        call_kwargs = mock_orch.execute_direct_session.call_args.kwargs
        assert call_kwargs["query"] == "hello"
        assert call_kwargs["agent_id"] == "chat"
        assert call_kwargs["session_id"] == "sess-existing"
        assert call_kwargs["image_paths"] == ["/tmp/x.png"]


class TestApiSessions:
    """GET /api/sessions + GET /api/sessions/{id}."""

    def test_get_session_returns_404_when_orchestrator_returns_none(
            self, client, mock_orch):
        mock_orch.get_session_status = AsyncMock(return_value=None)

        r = client.get("/api/sessions/missing-session")

        assert r.status_code == 404
        assert r.json()["detail"] == "Session not found"

    def test_get_session_returns_status_when_found(self, client, mock_orch):
        mock_orch.get_session_status = AsyncMock(return_value={
            "session_id": "sess-1",
            "status": "completed",
        })

        r = client.get("/api/sessions/sess-1")

        assert r.status_code == 200
        assert r.json()["status"] == "completed"


class TestApiMemory:
    """GET /api/memory/{agent_id}."""

    def test_returns_working_memory_payload(self, client, mock_orch):
        mock_orch.get_agent_working_memory = AsyncMock(return_value={
            "agent_id": "code-analyzer",
            "working_memory": {
                "summary": "..."
            },
        })

        r = client.get("/api/memory/code-analyzer")

        assert r.status_code == 200
        assert r.json()["agent_id"] == "code-analyzer"
        # Verify the agent_id was forwarded.
        mock_orch.get_agent_working_memory.assert_awaited_once_with("code-analyzer")


class TestApiEvalsList:
    """GET /api/evals — agents with at least one trace_*.json."""

    def test_returns_empty_when_agents_dir_missing(self, client, monkeypatch, tmp_path):
        # Point _AGENTS_DIR at a non-existent path.
        monkeypatch.setattr("gptase.web.server._AGENTS_DIR", tmp_path / "missing")

        r = client.get("/api/evals")

        assert r.status_code == 200
        assert r.json() == []

    def test_lists_only_agents_with_traces(self, client, mock_agents_dir):
        # Two agents: one with a trace, one without. Only the first
        # should appear in the response.
        agent_a = mock_agents_dir / "agent-a"
        (agent_a / "evals" / "output").mkdir(parents=True)
        (agent_a / "evals" / "output" / "trace_20260101.json").write_text(
            '{"summary": {"timestamp": "20260101", "model": "gpt-4",'
            ' "final_status": "success"}, "steps": []}',
            encoding="utf-8",
        )
        agent_b = mock_agents_dir / "agent-b"
        agent_b.mkdir()  # no evals/ dir

        r = client.get("/api/evals")

        data = r.json()
        assert len(data) == 1
        assert data[0]["agent_name"] == "agent-a"
        assert data[0]["trace_count"] == 1
        assert data[0]["latest_model"] == "gpt-4"


class TestApiEvalsTraces:
    """GET /api/evals/{agent}/traces — newest-first listing."""

    def test_lists_traces_newest_first_with_step_count(self, client, mock_agents_dir):
        out_dir = mock_agents_dir / "agent-a" / "evals" / "output"
        out_dir.mkdir(parents=True)
        (out_dir / "trace_20260101.json").write_text(
            '{"summary": {"timestamp": "20260101"},'
            ' "steps": [{"i": 1}]}',
            encoding="utf-8",
        )
        (out_dir / "trace_20260202.json").write_text(
            '{"summary": {"timestamp": "20260202"},'
            ' "steps": [{"i": 1}, {"i": 2}, {"i": 3}]}',
            encoding="utf-8",
        )

        r = client.get("/api/evals/agent-a/traces")

        traces = r.json()
        # reverse=True -> newest filename first.
        assert [t["filename"]
                for t in traces] == ["trace_20260202.json", "trace_20260101.json"]
        # step_count is computed from the steps array length.
        assert traces[0]["step_count"] == 3
        assert traces[1]["step_count"] == 1


class TestApiEvalsGetTrace:
    """GET /api/evals/{agent}/traces/{filename} — validation + 404."""

    def test_rejects_filename_not_matching_trace_pattern(self, client, mock_agents_dir):
        # Filename that doesn't start with "trace_" or end with ".json"
        # is rejected with 400 — basic path-traversal guard.
        r = client.get("/api/evals/agent-a/traces/etc_passwd.txt")

        assert r.status_code == 400
        assert "Invalid trace filename" in r.json()["detail"]

    def test_returns_404_when_trace_file_missing(self, client, mock_agents_dir):
        # Filename pattern is valid but file doesn't exist.
        r = client.get("/api/evals/agent-a/traces/trace_20260101.json")

        assert r.status_code == 404
        assert r.json()["detail"] == "Trace not found"
