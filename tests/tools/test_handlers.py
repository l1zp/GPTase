"""Unit tests for gptase.tools.handlers — the 5 default tools.

Covers ReadTool, GrepTool, GlobTool, BashTool happy paths + key error
branches; DelegateTaskTool's three flow modes (orchestrator missing,
agent missing, normal delegation) and the workspace-artifact
persistence contract; plus the _try_parse_json_object helper's two
strategies.

Filesystem tools use real tmp_path I/O — they're cheap and the OS
gives the most accurate behavior. DelegateTaskTool uses MagicMock for
the orchestrator + AsyncMock for process_task.
"""
import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from gptase.tools.handlers import _try_parse_json_object
from gptase.tools.handlers import BashTool
from gptase.tools.handlers import DelegateTaskTool
from gptase.tools.handlers import GlobTool
from gptase.tools.handlers import GrepTool
from gptase.tools.handlers import ReadTool


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
    """DelegateTaskTool: orchestrator/agent gating + delegation happy path."""

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

    async def test_delegates_to_agent(self):
        worker = MagicMock()
        worker.auto_resolve_artifacts = False
        worker.inputs_schema = None
        worker.output_schema = None
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


class TestDelegateTaskSchemaValidation:
    """Schema declarations on target_agent gate the DelegateTask boundary."""

    async def test_delegate_rejects_inputs_violating_schema(self):
        # Worker declares an inputs_schema that requires `x: integer`.
        worker = MagicMock()
        worker.auto_resolve_artifacts = False
        worker.inputs_schema = {
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer"
                }
            },
            "required": ["x"],
        }
        worker.output_schema = None
        worker.process_task = AsyncMock()  # must NOT be called

        orch = MagicMock()
        orch.agents = {"worker": worker}
        tool = DelegateTaskTool(orchestrator=orch)

        result_json = await tool.execute(
            agent_id="worker",
            task_description="do it",
            task_inputs={"y": "wrong key"},
        )
        result = json.loads(result_json)

        assert result["status"] == "failed"
        assert "schema violation" in result["error"]
        # Validation fires BEFORE process_task — the worker never runs.
        worker.process_task.assert_not_awaited()

    async def test_delegate_rejects_output_violating_schema(self):
        # Worker output content JSON-parses but lacks a required field.
        worker = MagicMock()
        worker.auto_resolve_artifacts = False
        worker.inputs_schema = None
        worker.output_schema = {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string"
                }
            },
            "required": ["result"],
        }
        worker.process_task = AsyncMock(return_value={
            "status": "success",
            "data": {
                "content": json.dumps({"unrelated": 1})
            },
        })

        orch = MagicMock()
        orch.agents = {"worker": worker}
        tool = DelegateTaskTool(orchestrator=orch)

        result_json = await tool.execute(agent_id="worker", task_description="x")
        result = json.loads(result_json)

        assert result["status"] == "failed"
        assert "output schema violation" in result["error"]
        assert "result" in result["error"]  # missing key surfaced
        worker.process_task.assert_awaited_once()


class TestDelegateTaskWorkspaceArtifacts:
    """workspace_dir set: full payload persisted to disk + compact reference returned."""

    async def test_workspace_writes_artifact_and_returns_compact_reference(
            self, tmp_path):
        worker = MagicMock()
        worker.auto_resolve_artifacts = False
        worker.inputs_schema = None
        worker.output_schema = None
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
        worker.auto_resolve_artifacts = False
        worker.inputs_schema = None
        worker.output_schema = None
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


class TestExtractVisionImagePaths:
    """_extract_vision_image_paths: artifact-aware base directory resolution.

    Regression: MinerU-derived markdowns put images alongside the .md file
    (e.g. <md_dir>/images/<hash>.jpg) and document-structure-analyzer writes
    image_path values relative to <md_dir>. The resolver must prefer the
    artifact's own source_file parent over workspace_dir.
    """

    def _make_artifact(self, path, source_file, image_relpath):
        envelope = {
            "agent_id":
            "document-structure-analyzer",
            "status":
            "success",
            "content":
            json.dumps({
                "source_file":
                str(source_file),
                "images": [{
                    "image_path": image_relpath,
                    "figure_id": "Table 1",
                    "is_table_image": True,
                }],
            }),
            "error":
            None,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(envelope))

    def test_resolves_image_path_relative_to_artifact_source_file(self, tmp_path):
        md_dir = tmp_path / "paper" / "main"
        (md_dir / "images").mkdir(parents=True)
        img = md_dir / "images" / "fig1.jpg"
        img.write_bytes(b"\xff\xd8\xff")  # JPEG SOI — enough for is_file()

        artifact = tmp_path / "out" / "001_dsa.json"
        self._make_artifact(artifact, md_dir / "main.md", "images/fig1.jpg")

        tool = DelegateTaskTool(orchestrator=None, workspace_dir=str(tmp_path / "out"))

        resolved = tool._extract_vision_image_paths({"images": str(artifact)})

        assert resolved == [str(img.resolve())]

    def test_workspace_dir_fallback_when_artifact_has_no_source_file(self, tmp_path):
        # Artifact missing source_file → fall back to workspace_dir.
        ws = tmp_path / "out"
        (ws / "images").mkdir(parents=True)
        img = ws / "images" / "fig.jpg"
        img.write_bytes(b"\xff\xd8\xff")

        artifact = ws / "001_dsa.json"
        envelope = {
            "agent_id": "document-structure-analyzer",
            "status": "success",
            "content": json.dumps({
                "images": [{
                    "image_path": "images/fig.jpg"
                }],
            }),
            "error": None,
        }
        artifact.write_text(json.dumps(envelope))

        tool = DelegateTaskTool(orchestrator=None, workspace_dir=str(ws))
        resolved = tool._extract_vision_image_paths({"images": str(artifact)})

        assert resolved == [str(img.resolve())]
