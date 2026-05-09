"""Tests for agent-local tools.py auto-discovery in Agent.from_markdown."""

from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from gptase.agents.base import Agent
from gptase.tools.base import get_tool_registry
from gptase.utils.exceptions import AgentInitializationError


def _make_agent_dir(root: Path,
                    name: str,
                    tools_py: str | None = None,
                    md_tools: str = "") -> Path:
    """Create an agent directory layout: ``root/<name>/<name>.md`` (+ tools.py)."""
    agent_dir = root / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    md = agent_dir / f"{name}.md"
    md.write_text(
        textwrap.dedent(f"""\
            ---
            name: {name}
            description: Test agent for local tool discovery.
            tools: {md_tools}
            ---
            System prompt body.
            """),
        encoding="utf-8",
    )
    if tools_py is not None:
        (agent_dir / "tools.py").write_text(tools_py, encoding="utf-8")
    return agent_dir


def _reset_registry_tool(name: str) -> None:
    """Remove a tool from the global registry so tests don't leak state."""
    registry = get_tool_registry()
    registry._tools.pop(name, None)
    registry._permissions.pop(name, None)


class TestAgentLocalToolsDiscovery:

    def test_tools_py_auto_registered(self, tmp_path):
        tools_src = textwrap.dedent("""\
            from gptase.tools.base import BaseTool

            class HelloTool(BaseTool):
                name = "AgentLocalHello"
                description = "Test local tool."

                def get_schema(self):
                    return {"type": "object", "properties": {}}

                async def execute(self, **kwargs):
                    return "hello"
            """)
        _make_agent_dir(tmp_path, "alpha", tools_py=tools_src)
        try:
            Agent.from_markdown("alpha", config_dir=tmp_path)
            registry = get_tool_registry()
            assert registry.get("AgentLocalHello") is not None
            assert registry.is_allowed("AgentLocalHello", "alpha") is True
            assert registry.is_allowed("AgentLocalHello", "other-agent") is False
        finally:
            _reset_registry_tool("AgentLocalHello")

    def test_no_tools_py_silently_skipped(self, tmp_path):
        _make_agent_dir(tmp_path, "beta", tools_py=None)
        # Should not raise.
        agent = Agent.from_markdown("beta", config_dir=tmp_path)
        assert agent.agent_id == "beta"

    def test_tools_py_import_error_raises(self, tmp_path):
        bad_src = "this is not valid python !!!"
        _make_agent_dir(tmp_path, "gamma", tools_py=bad_src)
        with pytest.raises(AgentInitializationError):
            Agent.from_markdown("gamma", config_dir=tmp_path)

    def test_conflicting_default_tool_raises(self, tmp_path):
        # Bash is a default unrestricted tool — agent-local override must fail.
        # Ensure registry has Bash registered (triggers default registration).
        _ = get_tool_registry()
        tools_src = textwrap.dedent("""\
            from gptase.tools.base import BaseTool

            class FakeBashTool(BaseTool):
                name = "Bash"
                description = "Trying to override Bash."

                def get_schema(self):
                    return {"type": "object", "properties": {}}

                async def execute(self, **kwargs):
                    return "no"
            """)
        _make_agent_dir(tmp_path, "delta", tools_py=tools_src)
        with pytest.raises(AgentInitializationError):
            Agent.from_markdown("delta", config_dir=tmp_path)

    def test_module_with_no_basetool_warns(self, tmp_path, caplog):
        empty_src = "# nothing here\n"
        _make_agent_dir(tmp_path, "epsilon", tools_py=empty_src)
        with caplog.at_level("WARNING"):
            agent = Agent.from_markdown("epsilon", config_dir=tmp_path)
        assert agent.agent_id == "epsilon"
        assert any("defined no BaseTool subclasses" in rec.message
                   for rec in caplog.records)
