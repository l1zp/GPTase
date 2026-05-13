"""Unit tests for gptase.agents.base.Agent.

Cases covering the live surface:
- Init + model routing (Claude vs LLM path)
- from_markdown frontmatter parsing + skill loading + error paths
- Agent file lookup (flat + directory layouts)
- Sibling tools.py auto-registration
- Multimodal: base64 image encoding + OpenAI->Claude conversion
- process_task + image extraction + user prompt building
- list_agent_md_files discovery
- run() LLM-path routing (AgentRuntime monkeypatched)
- run() memory injection + update_memory wiring
- run_stream() fallback when tools or Claude model

The Claude-SDK path (_run_with_sdk) is intentionally not tested — it
is a thin wrapper around claude_agent_sdk.query and the heavy mock
needed to exercise it belongs in L3 integration tests.
"""
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from gptase.agents.base import Agent
from gptase.agents.base import list_agent_md_files
from gptase.agents.runtime_types import InteractiveRuntimeResult
from gptase.agents.runtime_types import InteractiveRuntimeSnapshot
from gptase.agents.runtime_types import RuntimeStopReason
from gptase.agents.types import Task
from gptase.models.types import ModelConfig
from gptase.tools.base import BaseTool
from gptase.utils.exceptions import AgentInitializationError


def _make_md(
    tmp_path: Path,
    name: str,
    *,
    description: str = "Test agent",
    tools: Optional[List[str]] = None,
    body: str = "You are a helpful test assistant.",
    extra_frontmatter: str = "",
) -> Path:
    """Write an agent .md to tmp_path/<name>.md and return the path."""
    tools_str = ""
    if tools is not None:
        tools_str = f"tools: {tools}\n"
    md = f"""---
name: {name}
description: {description}
{tools_str}{extra_frontmatter}---
{body}
"""
    path = tmp_path / f"{name}.md"
    path.write_text(md, encoding="utf-8")
    return path


def _config(model_name: str = "gpt-4") -> ModelConfig:
    return ModelConfig(model_name=model_name,
                       api_key="sk-test",
                       base_url="https://test.local")


class TestAgentInit:
    """__init__ stores attributes; logger namespaced by agent_id."""

    def test_init_stores_basic_attributes(self):
        cfg = _config()
        agent = Agent(
            system_prompt="You help.",
            tools=["Read", "Bash"],
            model_config=cfg,
            agent_id="my-agent",
            workspace_dir="/tmp/work",
            max_iterations=5,
        )

        assert agent.system_prompt == "You help."
        assert agent.tools == ["Read", "Bash"]
        assert agent.model_config is cfg
        assert agent.agent_id == "my-agent"
        assert agent.workspace_dir == "/tmp/work"
        assert agent.max_iterations == 5


class TestModelRouting:
    """is_claude_model + model_name property."""

    def test_model_name_from_explicit_override(self):
        agent = Agent(system_prompt="x", model_name="claude-opus-4-7")

        assert agent.model_name == "claude-opus-4-7"

    def test_is_claude_model_for_claude_prefix_vs_other(self):
        claude_agent = Agent(system_prompt="x", model_name="claude-opus-4-7")
        gpt_agent = Agent(system_prompt="x", model_name="gpt-4-turbo")

        assert claude_agent.is_claude_model() is True
        assert gpt_agent.is_claude_model() is False


class TestFromMarkdownParsing:
    """from_markdown reads frontmatter + body + skills + error paths."""

    def test_from_markdown_parses_frontmatter_and_body(self, tmp_path):
        md = _make_md(tmp_path,
                      "alpha",
                      description="Alpha agent",
                      tools=["Read"],
                      body="Alpha system prompt body.")
        cfg = _config()
        model_manager = MagicMock()
        model_manager.get_config_for_agent.return_value = cfg

        agent = Agent.from_markdown(str(md), model_manager=model_manager)

        assert agent.agent_id == "alpha"
        assert agent.description == "Alpha agent"
        assert agent.tools == ["Read"]
        assert "Alpha system prompt body" in agent.system_prompt

    def test_from_markdown_loads_skills_into_system_prompt(self, tmp_path):
        # Set up a skills dir with one skill SKILL.md.
        skills_dir = tmp_path / "skills"
        skill_dir = skills_dir / "biochem_databases"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: biochem_databases\n---\n"
            "Skill body content for biochem.\n",
            encoding="utf-8",
        )

        md = _make_md(
            tmp_path,
            "beta",
            tools=["Read"],
            extra_frontmatter="skills:\n  - biochem_databases\n",
        )

        agent = Agent.from_markdown(str(md), skills_dir=skills_dir)

        assert "Skill body content for biochem" in agent.system_prompt

    def test_from_markdown_raises_when_file_not_found(self, tmp_path):
        with pytest.raises(AgentInitializationError, match="not found"):
            Agent.from_markdown("nonexistent-agent-xyz", config_dir=tmp_path)

    def test_from_markdown_rejects_invalid_frontmatter(self, tmp_path):
        path = tmp_path / "bad.md"
        path.write_text("no frontmatter here\n", encoding="utf-8")

        with pytest.raises(AgentInitializationError, match="Failed to parse"):
            Agent.from_markdown(str(path))


class TestFindAgentFileLayouts:
    """Agent file lookup supports flat + directory layouts."""

    def test_find_agent_file_flat_layout(self, tmp_path):
        md = _make_md(tmp_path, "flat", tools=["Read"])

        result = Agent._find_agent_file("flat", tmp_path)

        assert result == md

    def test_find_agent_file_directory_layout(self, tmp_path):
        # config_dir/agent-x/agent-x.md
        agent_dir = tmp_path / "agent-x"
        agent_dir.mkdir()
        nested = agent_dir / "agent-x.md"
        nested.write_text("---\nname: agent-x\n---\nbody\n", encoding="utf-8")

        result = Agent._find_agent_file("agent-x", tmp_path)

        assert result == nested


class TestRegisterAgentLocalTools:
    """Sibling tools.py auto-discovery + permission scoping."""

    def test_local_tools_registered_with_allowed_agents(self, tmp_path, monkeypatch):
        # Build directory layout: tmp_path/myagent/{myagent.md, tools.py}.
        agent_dir = tmp_path / "myagent"
        agent_dir.mkdir()
        (agent_dir / "myagent.md").write_text(
            "---\nname: myagent\ndescription: x\ntools: [LocalEcho]\n---\nbody\n",
            encoding="utf-8",
        )
        (agent_dir / "tools.py").write_text(
            "from gptase.tools.base import BaseTool\n"
            "class LocalEcho(BaseTool):\n"
            "    name = 'LocalEcho'\n"
            "    description = 'echo'\n"
            "    def get_schema(self): return {'type': 'object'}\n"
            "    async def execute(self, **k): return 'echoed'\n",
            encoding="utf-8",
        )

        # Use a fresh registry so other tests aren't polluted.
        from gptase.tools import base as base_module
        from gptase.tools.base import ToolRegistry
        fresh_registry = ToolRegistry()
        monkeypatch.setattr(base_module, "_global_registry", fresh_registry)

        Agent.from_markdown(str(agent_dir / "myagent.md"))

        registered = fresh_registry.get("LocalEcho")
        assert registered is not None
        assert fresh_registry._permissions.get("LocalEcho") == ["myagent"]


class TestImageHandling:
    """_load_image_as_content base64-encodes image + detects MIME."""

    def test_load_image_returns_base64_data_url(self, tmp_path, sample_image_png):
        agent = Agent(system_prompt="x", model_name="gpt-4")

        content = agent._load_image_as_content(sample_image_png)

        assert content is not None
        assert content["type"] == "image_url"
        url = content["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")

    def test_load_image_returns_none_for_missing_file(self, tmp_path):
        agent = Agent(system_prompt="x", model_name="gpt-4")

        result = agent._load_image_as_content(str(tmp_path / "missing.png"))

        assert result is None


class TestConvertToClaudeContent:
    """OpenAI multimodal format -> Claude API content blocks."""

    def test_openai_multimodal_converted_to_claude_blocks(self):
        agent = Agent(system_prompt="x", model_name="claude-opus-4-7")
        openai_content = [
            {
                "type": "text",
                "text": "Describe this:"
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,abc123"
                }
            },
        ]

        claude_content = agent._convert_to_claude_content(openai_content)

        assert len(claude_content) == 2
        # Image block reshaped for Claude.
        image_block = next(b for b in claude_content if b.get("type") == "image")
        assert image_block["source"]["type"] == "base64"
        assert image_block["source"]["media_type"] == "image/png"
        assert image_block["source"]["data"] == "abc123"
        # Text block preserved.
        text_block = next(b for b in claude_content if b.get("type") == "text")
        assert text_block["text"] == "Describe this:"


class TestProcessTask:
    """process_task extracts images + builds prompt + calls run()."""

    async def test_process_task_calls_run_with_image_paths(self, tmp_path):
        agent = Agent(system_prompt="x", model_name="gpt-4", agent_id="proc")
        task = Task(
            description="describe",
            image_paths=[str(tmp_path / "a.png"),
                         str(tmp_path / "b.png")],
        )

        agent.run = AsyncMock(return_value={
            "status": "success",
            "data": {
                "content": "ok"
            }
        })

        result = await agent.process_task(task)

        assert result["status"] == "success"
        # run() called with extracted image paths.
        agent.run.assert_awaited_once()
        kwargs = agent.run.await_args.kwargs
        assert kwargs.get("image_paths") == [
            str(tmp_path / "a.png"), str(tmp_path / "b.png")
        ]

    def test_extract_image_paths_dedups_and_resolves_workspace_relative(self, tmp_path):
        agent = Agent(system_prompt="x", model_name="gpt-4")
        # task.images uses relative paths + workspace_dir; image_paths uses
        # absolute path duplicated to test dedup.
        abs_path = str(tmp_path / "absolute.png")
        task = Task(
            description="x",
            workspace_dir=str(tmp_path),
            image_path=abs_path,
            image_paths=[abs_path],  # duplicate of image_path
            images=["relative.png"],  # workspace-relative
        )

        paths = agent._extract_image_paths(task)

        # Dedup keeps absolute path once; relative path resolved to
        # workspace prefix.
        assert abs_path in paths
        assert str(tmp_path / "relative.png") in paths
        # No duplicate of abs_path.
        assert paths.count(abs_path) == 1


class TestBuildUserPrompt:
    """_build_user_prompt formats task data + workspace note."""

    def test_build_user_prompt_includes_task_data_and_workspace_note(self, tmp_path):
        agent = Agent(system_prompt="x", model_name="gpt-4")
        task = Task(
            description="extract enzymes",
            workspace_dir=str(tmp_path),
            inputs={"k": "v"},
        )

        prompt = agent._build_user_prompt(task)

        assert "Task: extract enzymes" in prompt
        assert "Input Data:" in prompt
        assert "extract enzymes" in prompt
        assert str(tmp_path) in prompt
        assert "workspace directory" in prompt


class TestListAgentMdFiles:
    """list_agent_md_files supports both flat + directory layouts."""

    def test_list_agent_md_files_supports_both_layouts(self, tmp_path):
        # Flat layout file.
        flat = tmp_path / "flat-agent.md"
        flat.write_text("---\nname: flat-agent\n---\nbody\n", encoding="utf-8")
        # Directory layout file.
        nested_dir = tmp_path / "nested-agent"
        nested_dir.mkdir()
        nested = nested_dir / "nested-agent.md"
        nested.write_text("---\nname: nested-agent\n---\nbody\n", encoding="utf-8")
        # Directory without matching md (should be skipped).
        empty_dir = tmp_path / "empty-dir"
        empty_dir.mkdir()

        results = list_agent_md_files(tmp_path)

        assert flat in results
        assert nested in results


class TestRunLLMPath:
    """run() routes non-Claude models through _run_with_llm + AgentRuntime."""

    async def test_run_with_non_claude_model_routes_through_llm_path(self, monkeypatch):
        agent = Agent(system_prompt="x",
                      model_config=_config(),
                      model_name="gpt-4-turbo",
                      agent_id="")

        # Patch AgentRuntime so we don't actually call openai. Returns a
        # canned InteractiveRuntimeResult shaped like FINAL_ANSWER.
        snap = InteractiveRuntimeSnapshot(messages=[], turns=[], steps=[])
        canned_result = InteractiveRuntimeResult(
            content="answer",
            stop_reason=RuntimeStopReason.FINAL_ANSWER,
            turn_count=1,
            usage={
                "prompt_tokens": 1,
                "completion_tokens": 2,
                "total_tokens": 3
            },
            snapshot=snap,
        )

        fake_runtime = MagicMock()
        fake_runtime.run = AsyncMock(return_value=canned_result)
        # Patch both AgentRuntime and Model so Model construction doesn't
        # touch FrameworkConfig disk loading.
        fake_model_cls = MagicMock(return_value=MagicMock(
            initialize_tracking=AsyncMock(),
            shutdown=AsyncMock(),
        ))
        monkeypatch.setattr("gptase.agents.base.AgentRuntime",
                            MagicMock(return_value=fake_runtime))
        monkeypatch.setattr("gptase.agents.base.Model", fake_model_cls)

        result = await agent.run("hi")

        assert result["status"] == "success"
        assert result["data"]["content"] == "answer"
        fake_runtime.run.assert_awaited_once()


class TestRunMemoryIntegration:
    """run() loads memory context before LLM call + updates after."""

    async def test_run_injects_prior_memory_then_updates_after_completion(
            self, monkeypatch):
        agent = Agent(system_prompt="x",
                      model_config=_config(),
                      model_name="gpt-4-turbo",
                      agent_id="memory-agent")

        # Stub the memory service: returns canned context, records updates.
        fake_service = MagicMock()
        fake_service.build_memory_context = AsyncMock(
            return_value="Prior context: prior work")
        fake_service.update_memory = AsyncMock()
        agent._memory_service = fake_service
        agent._memory_service_initialized = True

        # Patch the LLM execution path so it returns success quickly.
        async def _fake_llm_run(self, task, **kwargs):
            self._observed_task = task  # noqa: SLF001 — capture for assertion
            return {"status": "success", "data": {"content": "done"}}

        monkeypatch.setattr(Agent, "_run_with_llm", _fake_llm_run)

        result = await agent.run("Original task")

        assert result["status"] == "success"
        # Memory context injected -> task carries the prior-context prefix.
        observed = agent._observed_task
        assert isinstance(observed, str)
        assert "Prior context: prior work" in observed
        assert "Original task" in observed
        # Memory update called with the ORIGINAL prompt + result.
        fake_service.update_memory.assert_awaited_once()
        update_args = fake_service.update_memory.await_args.args
        assert update_args[1] == "Original task"  # original_prompt


class TestRunStreamFallback:
    """run_stream falls back to run() when tools or Claude model present."""

    async def test_run_stream_with_tools_falls_back_to_run_and_yields_final_chunk(self):
        agent = Agent(system_prompt="x", model_name="gpt-4-turbo", tools=["Read"])
        agent.run = AsyncMock(return_value={
            "status": "success",
            "data": {
                "content": "final-text"
            }
        })

        events = []
        async for ev in agent.run_stream("hello"):
            events.append(ev)

        assert len(events) == 1
        assert events[0]["content"] == "final-text"
        assert events[0]["is_complete"] is True
        assert events[0]["metadata"]["stream_mode"] == "fallback"
        agent.run.assert_awaited_once()
