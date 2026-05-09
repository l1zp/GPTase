"""Tests for the deterministic-agent shortcut in DelegateTaskTool."""

from __future__ import annotations

import json
from pathlib import Path
import textwrap

import pytest

from gptase.agents.base import Agent
from gptase.tools.base import BaseTool
from gptase.tools.base import get_tool_registry
from gptase.tools.handlers import _try_parse_json_object
from gptase.tools.handlers import DelegateTaskTool


def _reset(name: str) -> None:
    reg = get_tool_registry()
    reg._tools.pop(name, None)
    reg._permissions.pop(name, None)


class _FakeOrchestrator:

    def __init__(self, agent: Agent):
        self.agents = {agent.agent_id: agent}


class TestDeterministicDispatch:

    async def test_skips_llm_and_calls_tool_with_task_inputs(self, tmp_path):
        # Build a deterministic agent with a single in-process tool.
        captured: dict = {}

        tools_src = textwrap.dedent("""\
            from gptase.tools.base import BaseTool

            class FakeNormalizerTool(BaseTool):
                name = "FakeNormalizer"
                description = "Echo inputs."

                def get_schema(self):
                    return {
                        "type": "object",
                        "properties": {"x": {"type": "integer"}},
                        "required": ["x"],
                    }

                async def execute(self, **kwargs):
                    return f"called with x={kwargs.get('x')}"
            """)
        agent_dir = tmp_path / "fake-norm"
        agent_dir.mkdir()
        (agent_dir / "fake-norm.md").write_text(
            textwrap.dedent("""\
                ---
                name: fake-norm
                description: Test deterministic agent.
                tools: FakeNormalizer
                deterministic: true
                ---
                body
                """),
            encoding="utf-8",
        )
        (agent_dir / "tools.py").write_text(tools_src, encoding="utf-8")

        try:
            agent = Agent.from_markdown("fake-norm", config_dir=tmp_path)
            assert agent.deterministic is True

            orch = _FakeOrchestrator(agent)
            tool = DelegateTaskTool(orchestrator=orch)
            raw = await tool.execute(
                agent_id="fake-norm",
                task_description="ignored when task_inputs present",
                task_inputs={"x": 42},
            )
            payload = json.loads(raw)
            assert payload["status"] == "success"
            assert "x=42" in payload["content"]
        finally:
            _reset("FakeNormalizer")

    async def test_falls_back_to_json_in_task_description(self, tmp_path):
        tools_src = textwrap.dedent("""\
            from gptase.tools.base import BaseTool

            class JSONFallbackTool(BaseTool):
                name = "JSONFallback"
                description = "Echo."

                def get_schema(self):
                    return {"type": "object", "properties": {"y": {"type": "string"}}}

                async def execute(self, **kwargs):
                    return f"y={kwargs.get('y')}"
            """)
        agent_dir = tmp_path / "json-fb"
        agent_dir.mkdir()
        (agent_dir / "json-fb.md").write_text(
            textwrap.dedent("""\
                ---
                name: json-fb
                description: t
                tools: JSONFallback
                deterministic: true
                ---
                body
                """),
            encoding="utf-8",
        )
        (agent_dir / "tools.py").write_text(tools_src, encoding="utf-8")
        try:
            agent = Agent.from_markdown("json-fb", config_dir=tmp_path)
            orch = _FakeOrchestrator(agent)
            tool = DelegateTaskTool(orchestrator=orch)

            # Coordinator emits ```json fenced block as task_description.
            desc = '```json\n{"y": "hello"}\n```'
            raw = await tool.execute(
                agent_id="json-fb",
                task_description=desc,
                task_inputs=None,
            )
            payload = json.loads(raw)
            assert payload["status"] == "success"
            assert "y=hello" in payload["content"]
        finally:
            _reset("JSONFallback")

    async def test_deterministic_with_zero_or_many_tools_rejected(self, tmp_path):
        agent_dir = tmp_path / "bad-det"
        agent_dir.mkdir()
        (agent_dir / "bad-det.md").write_text(
            textwrap.dedent("""\
                ---
                name: bad-det
                description: invalid deterministic config
                tools: ToolA, ToolB
                deterministic: true
                ---
                body
                """),
            encoding="utf-8",
        )
        from gptase.utils.exceptions import AgentInitializationError
        with pytest.raises(AgentInitializationError):
            Agent.from_markdown("bad-det", config_dir=tmp_path)


class TestJSONParseHelper:

    def test_parses_fenced_json(self):
        result = _try_parse_json_object('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_parses_raw_object(self):
        assert _try_parse_json_object('{"a": 1, "b": 2}') == {"a": 1, "b": 2}

    def test_extracts_embedded_object(self):
        text = 'preamble {"k": "v"} trailing'
        assert _try_parse_json_object(text) == {"k": "v"}

    def test_returns_none_when_no_object(self):
        assert _try_parse_json_object("just text") is None

    def test_returns_none_for_array_top_level(self):
        # Top-level array is not a dict; helper requires a dict.
        assert _try_parse_json_object("[1, 2, 3]") is None


class TestArtifactBasedDelegation:
    """Slice 1.18: DelegateTask should write artifacts and return refs
    when a workspace_dir is configured, so Coordinator context stays
    bounded regardless of worker output size."""

    async def test_writes_artifact_and_returns_compact_ref(self, tmp_path):
        from gptase.tools.handlers import DelegateTaskTool

        # Standard (non-deterministic) worker stub
        class FakeAgent:

            def __init__(self):
                self.deterministic = False
                self.agent_id = "noisy"

            async def process_task(self, task):
                return {
                    "status": "success",
                    "data": {
                        "content": "X" * 5000  # would otherwise inline 5KB
                    },
                }

        class FakeOrch:

            def __init__(self):
                self.agents = {"noisy": FakeAgent()}

        tool = DelegateTaskTool(orchestrator=FakeOrch(), workspace_dir=str(tmp_path))
        raw = await tool.execute(agent_id="noisy", task_description="ignored")
        payload = json.loads(raw)

        # Compact reference shape
        assert payload["status"] == "success"
        assert payload["agent_id"] == "noisy"
        assert "output_path" in payload
        assert payload["content_chars"] == 5000
        assert len(payload["content_preview"]) <= 1501  # +1 for ellipsis
        assert "content" not in payload  # full content NOT inlined

        # Artifact file exists with full content
        art = Path(payload["output_path"])
        assert art.exists()
        assert art.parent.name == "worker_results"
        envelope = json.loads(art.read_text())
        assert envelope["agent_id"] == "noisy"
        assert envelope["content"] == "X" * 5000

    async def test_no_workspace_falls_back_to_inline_content(self, tmp_path):
        """Backward compatibility: without workspace, full content inlined."""
        from gptase.tools.handlers import DelegateTaskTool

        class FakeAgent:

            def __init__(self):
                self.deterministic = False
                self.agent_id = "x"

            async def process_task(self, task):
                return {"status": "success", "data": {"content": "hi"}}

        class FakeOrch:

            def __init__(self):
                self.agents = {"x": FakeAgent()}

        tool = DelegateTaskTool(orchestrator=FakeOrch(), workspace_dir=None)
        raw = await tool.execute(agent_id="x", task_description="ignored")
        payload = json.loads(raw)
        assert payload["content"] == "hi"
        assert "output_path" not in payload

    async def test_deterministic_resolves_output_path_in_task_inputs(self, tmp_path):
        """task_inputs string fields pointing at artifact files get
        unwrapped before being passed to the deterministic tool."""
        # Build an upstream artifact (as if a previous DelegateTask
        # wrote one).
        results_dir = tmp_path / "worker_results"
        results_dir.mkdir()
        artifact = results_dir / "001_upstream.json"
        artifact.write_text(
            json.dumps({
                "agent_id": "upstream-extractor",
                "status": "success",
                "content": json.dumps({"reactions": [{
                    "variant_name": "A"
                }]}),
                "error": None,
            }))

        # Deterministic agent that echoes whatever it receives
        captured: dict = {}

        tools_src = textwrap.dedent("""\
            from gptase.tools.base import BaseTool

            class EchoTool(BaseTool):
                name = "ArtifactEcho"
                description = "Echo inputs."

                def get_schema(self):
                    return {"type": "object", "properties": {}}

                async def execute(self, **kwargs):
                    import json
                    return json.dumps(kwargs)
            """)
        agent_dir = tmp_path / "echo"
        agent_dir.mkdir()
        (agent_dir / "echo.md").write_text(
            textwrap.dedent("""\
                ---
                name: echo
                description: t
                tools: ArtifactEcho
                deterministic: true
                ---
                body
                """),
            encoding="utf-8",
        )
        (agent_dir / "tools.py").write_text(tools_src, encoding="utf-8")
        try:
            from gptase.tools.handlers import DelegateTaskTool
            agent = Agent.from_markdown("echo", config_dir=tmp_path)

            class FakeOrch:

                def __init__(self):
                    self.agents = {"echo": agent}

            tool = DelegateTaskTool(orchestrator=FakeOrch(),
                                    workspace_dir=str(tmp_path))
            # Coordinator passes the artifact path string instead of
            # inline data.
            raw = await tool.execute(
                agent_id="echo",
                task_description="run",
                task_inputs={
                    "extractor_results": [str(artifact)],
                    "document_path": "/data/paper.md",  # plain string, pass-through
                },
            )
            payload = json.loads(raw)
            assert payload["status"] == "success"

            # The Echo tool's output is the kwargs it received.
            # output_path leads to the artifact for the echo'd kwargs.
            art_path = Path(payload["output_path"])
            envelope = json.loads(art_path.read_text())
            echoed = json.loads(envelope["content"])

            # Path was resolved to the parsed artifact content
            assert echoed["extractor_results"] == [{
                "reactions": [{
                    "variant_name": "A"
                }]
            }]
            # Plain string passed through unchanged
            assert echoed["document_path"] == "/data/paper.md"
        finally:
            _reset("ArtifactEcho")

    async def test_artifact_filename_contains_counter_and_agent_id(self, tmp_path):
        from gptase.tools.handlers import DelegateTaskTool

        class FakeAgent:

            def __init__(self):
                self.deterministic = False
                self.agent_id = "an-agent"

            async def process_task(self, task):
                return {"status": "success", "data": {"content": "ok"}}

        class FakeOrch:

            def __init__(self):
                self.agents = {"an-agent": FakeAgent()}

        tool = DelegateTaskTool(orchestrator=FakeOrch(), workspace_dir=str(tmp_path))
        await tool.execute(agent_id="an-agent", task_description="t1")
        await tool.execute(agent_id="an-agent", task_description="t2")
        files = sorted((tmp_path / "worker_results").glob("*.json"))
        assert len(files) == 2
        # Counter + agent_id present, monotonically increasing
        assert files[0].name == "001_an-agent.json"
        assert files[1].name == "002_an-agent.json"
