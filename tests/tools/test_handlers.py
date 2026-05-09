"""Unit tests for gptase.tools.handlers — the 5 default tools.

Covers ReadTool, GrepTool, GlobTool, BashTool happy paths + key error
branches; DelegateTaskTool's three flow modes (orchestrator missing,
agent missing, non-deterministic delegation, deterministic shortcut)
and the workspace-artifact persistence contract; plus the
_try_parse_json_object helper's two strategies.

Filesystem tools use real tmp_path I/O — they're cheap and the OS
gives the most accurate behavior. DelegateTaskTool uses MagicMock for
the orchestrator + AsyncMock for process_task.
"""
import asyncio
import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from gptase.tools.base import BaseTool
from gptase.tools.base import ToolRegistry
from gptase.tools.handlers import _try_parse_json_object
from gptase.tools.handlers import BashTool
from gptase.tools.handlers import DelegateTaskTool
from gptase.tools.handlers import GlobTool
from gptase.tools.handlers import GrepTool
from gptase.tools.handlers import ReadTool


class _StubTool(BaseTool):
    """Local stub tool registered for deterministic-path tests."""

    def __init__(self, name: str, output: str = "stub-out"):
        self.name = name
        self.description = "Stub for tests"
        self.output = output
        self.calls = []

    def get_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self.output


class TestReadTool:
    """ReadTool: line-numbered text + binary detection + missing-file error."""

    async def test_reads_text_file_with_line_numbers(self, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("line one\nline two\nline three\n")

        out = await ReadTool().execute(file_path=str(f))

        assert "1\tline one" in out
        assert "2\tline two" in out
        assert "3\tline three" in out

    async def test_returns_error_for_nonexistent_path(self, tmp_path):
        out = await ReadTool().execute(file_path=str(tmp_path / "nope.txt"))

        assert "[ERROR]" in out
        assert "File not found" in out

    async def test_detects_binary_extension(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\nfake-image-bytes")

        out = await ReadTool().execute(file_path=str(f))

        assert "[INFO] Binary file" in out
        assert ".png" in out


class TestGrepTool:
    """GrepTool: regex search results with file:line: prefix."""

    async def test_finds_regex_matches_with_filenames_and_line_numbers(self, tmp_path):
        a = tmp_path / "a.txt"
        a.write_text("foo\nbar\nfoo bar\n")
        b = tmp_path / "b.txt"
        b.write_text("nothing\nstill nothing\n")

        out = await GrepTool().execute(pattern=r"foo", path=str(tmp_path))

        # Both matching lines from a.txt are reported with line numbers.
        assert "a.txt:1: foo" in out
        assert "a.txt:3: foo bar" in out
        assert "b.txt" not in out

    async def test_invalid_regex_returns_error(self, tmp_path):
        out = await GrepTool().execute(pattern=r"[unclosed", path=str(tmp_path))

        assert "[ERROR]" in out
        assert "Invalid regex" in out


class TestGlobTool:
    """GlobTool: glob matches relative to base path."""

    async def test_returns_relative_paths_to_base(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("")
        (tmp_path / "src" / "util.py").write_text("")

        out = await GlobTool().execute(pattern="**/*.py", path=str(tmp_path))

        assert "src/main.py" in out
        assert "src/util.py" in out

    async def test_no_matches_returns_info_message(self, tmp_path):
        out = await GlobTool().execute(pattern="*.zzz", path=str(tmp_path))

        assert "[INFO] No files matched" in out


class TestBashTool:
    """BashTool: subprocess + safety blacklist + timeout."""

    async def test_executes_simple_command(self):
        out = await BashTool().execute(command="echo hello")

        assert "hello" in out

    async def test_blocks_dangerous_pattern_via_blacklist(self):
        out = await BashTool().execute(command="rm -rf /")

        assert "[ERROR]" in out
        assert "blocked for safety" in out

    async def test_timeout_returns_error(self):
        # Use sleep > timeout to trigger TimeoutError path. Keep it
        # snappy: timeout=1, sleep=5.
        out = await BashTool().execute(command="sleep 5", timeout=1)

        assert "[ERROR]" in out
        assert "timed out" in out


class TestDelegateTaskToolBasic:
    """DelegateTaskTool: orchestrator/agent gating + non-deterministic delegation."""

    async def test_returns_error_when_orchestrator_missing(self):
        tool = DelegateTaskTool(orchestrator=None)

        result_json = await tool.execute(agent_id="x", task_description="do x")
        result = json.loads(result_json)

        assert result["status"] == "failed"
        assert "Orchestrator not found" in result["error"]

    async def test_returns_error_when_agent_not_found(self):
        orch = MagicMock()
        orch.agents = {"alpha": MagicMock(), "beta": MagicMock()}
        tool = DelegateTaskTool(orchestrator=orch)

        result_json = await tool.execute(agent_id="missing", task_description="x")
        result = json.loads(result_json)

        assert result["status"] == "failed"
        assert "Agent 'missing' not found" in result["error"]
        assert "alpha" in result["error"]  # available agents listed
        assert "beta" in result["error"]

    async def test_delegates_to_non_deterministic_agent(self):
        # Non-deterministic agent: process_task returns success with content.
        worker = MagicMock()
        worker.deterministic = False
        worker.auto_resolve_artifacts = False
        worker.process_task = AsyncMock(return_value={
            "status": "success",
            "data": {
                "content": "did it"
            }
        })

        orch = MagicMock()
        orch.agents = {"worker": worker}
        tool = DelegateTaskTool(orchestrator=orch)

        result_json = await tool.execute(agent_id="worker",
                                         task_description="extract enzymes")
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["content"] == "did it"
        worker.process_task.assert_awaited_once()


class TestDelegateTaskToolDeterministic:
    """Deterministic shortcut bypasses LLM loop and calls the sole tool directly."""

    async def test_deterministic_path_calls_tool_directly_with_task_inputs(
            self, monkeypatch):
        # Wire a deterministic agent that declares a single tool name.
        worker = MagicMock()
        worker.deterministic = True
        worker.tools = ["MyDetTool"]

        orch = MagicMock()
        orch.agents = {"normalizer": worker}

        # Inject our stub tool into the global registry. Reset the
        # singleton afterward via module attr so other tests aren't
        # polluted.
        from gptase.tools import base as base_module
        from gptase.tools.handlers import register_default_tools

        fresh_registry = ToolRegistry()
        stub = _StubTool("MyDetTool", output="deterministic-out")
        fresh_registry.register(stub)
        monkeypatch.setattr(base_module, "_global_registry", fresh_registry)

        tool = DelegateTaskTool(orchestrator=orch)
        result_json = await tool.execute(
            agent_id="normalizer",
            task_description="ignored when task_inputs supplied",
            task_inputs={"key": "value"},
        )
        result = json.loads(result_json)

        assert result["status"] == "success"
        assert result["content"] == "deterministic-out"
        # The stub tool was called directly with the task_inputs dict —
        # no LLM hop, no Task object, no process_task.
        assert stub.calls == [{"key": "value"}]
        worker_attr = orch.agents["normalizer"]
        assert not hasattr(worker_attr,
                           "process_task") or not worker_attr.process_task.called

    async def test_deterministic_rejects_when_agent_has_zero_or_multiple_tools(self):
        # Multiple tools: not allowed for the deterministic shortcut.
        worker = MagicMock()
        worker.deterministic = True
        worker.tools = ["A", "B"]

        orch = MagicMock()
        orch.agents = {"bad": worker}
        tool = DelegateTaskTool(orchestrator=orch)

        result_json = await tool.execute(agent_id="bad",
                                         task_description="x",
                                         task_inputs={"k": "v"})
        result = json.loads(result_json)

        assert result["status"] == "failed"
        assert "must declare exactly one tool" in result["error"]


class TestDelegateTaskWorkspaceArtifacts:
    """workspace_dir set: full payload persisted to disk + compact reference returned."""

    async def test_workspace_writes_artifact_and_returns_compact_reference(
            self, tmp_path):
        worker = MagicMock()
        worker.deterministic = False
        worker.auto_resolve_artifacts = False
        big_content = "X" * 5000  # > _PREVIEW_CHARS (1500)
        worker.process_task = AsyncMock(return_value={
            "status": "success",
            "data": {
                "content": big_content
            },
        })

        orch = MagicMock()
        orch.agents = {"worker": worker}
        tool = DelegateTaskTool(orchestrator=orch, workspace_dir=str(tmp_path))

        result_json = await tool.execute(agent_id="worker",
                                         task_description="big extract")
        result = json.loads(result_json)

        # Compact reference returned, not full content.
        assert "content" not in result
        assert result["content_chars"] == 5000
        assert result["content_preview"].endswith("…")  # truncated marker
        assert len(result["content_preview"]) <= 1501  # 1500 + ellipsis
        # Artifact file exists on disk under worker_results/.
        artifact_path = tmp_path / "worker_results" / "001_worker.json"
        assert artifact_path.is_file()
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert artifact["content"] == big_content

    async def test_no_workspace_returns_full_content_inline(self):
        worker = MagicMock()
        worker.deterministic = False
        worker.auto_resolve_artifacts = False
        worker.process_task = AsyncMock(return_value={
            "status": "success",
            "data": {
                "content": "small"
            },
        })

        orch = MagicMock()
        orch.agents = {"worker": worker}
        tool = DelegateTaskTool(orchestrator=orch)  # no workspace_dir

        result_json = await tool.execute(agent_id="worker", task_description="x")
        result = json.loads(result_json)

        # Full content inline (back-compat path).
        assert result["content"] == "small"
        assert "content_preview" not in result


class TestTryParseJsonObject:
    """_try_parse_json_object: direct + balanced-brace recovery."""

    def test_parses_json_object_directly_or_with_fence(self):
        # Direct JSON object.
        assert _try_parse_json_object('{"a": 1}') == {"a": 1}
        # Fenced ```json block.
        fenced = '```json\n{"key": "value"}\n```'
        assert _try_parse_json_object(fenced) == {"key": "value"}
        # Plain ``` fence.
        plain = '```\n{"key": 2}\n```'
        assert _try_parse_json_object(plain) == {"key": 2}

    def test_balanced_brace_scan_recovers_object_from_noise(self):
        # JSON embedded in free-form text: balanced-brace scan finds it.
        text = ('Here is the answer: {"agent_id": "worker", '
                '"value": 42} and some trailing prose.')

        result = _try_parse_json_object(text)

        assert result == {"agent_id": "worker", "value": 42}
