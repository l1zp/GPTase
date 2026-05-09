"""Unit tests for gptase.memory.agent_memory.AgentMemoryService.

Covers the working-memory compression service: enable gate, prompt
context rendering, the update flow (skip/write decisions, summary
composition, multimodal task handling, configured truncation,
non-recursive prior-context wrapping), and the standalone
inject_memory_context helper.

Agent integration tests (Agent.run() driving update + context injection
end-to-end) are out of scope here — they belong to L2 #25
gptase/agents/base.py cycle.
"""
import pytest

from gptase.memory.agent_memory import AgentMemoryService
from gptase.memory.agent_memory import inject_memory_context
from gptase.memory.manager import MemoryManager
from gptase.memory.storage import ConversationStorage


@pytest.fixture
async def memory_manager(tmp_path):
    """Initialized MemoryManager backed by a tmp sqlite db."""
    storage = ConversationStorage(db_path=str(tmp_path / "agent_memory.db"))
    m = MemoryManager(storage=storage)
    await m.initialize()
    try:
        yield m
    finally:
        await m.close()


@pytest.fixture
def service(memory_manager):
    """AgentMemoryService backed by the tmp sqlite memory_manager."""
    return AgentMemoryService(
        memory_manager,
        config={
            "enabled": True,
            "max_summary_chars": 1200
        },
    )


class TestIsEnabledFor:
    """Bool gate combining agent_id presence + config.enabled."""

    def test_disabled_when_no_agent_id_or_config_disabled(self, memory_manager):
        # No agent_id at all:
        s_default = AgentMemoryService(memory_manager, config={"enabled": True})
        assert s_default.is_enabled_for(None) is False
        assert s_default.is_enabled_for("") is False
        assert s_default.is_enabled_for("a") is True

        # config.enabled=False trumps a real agent_id:
        s_off = AgentMemoryService(memory_manager, config={"enabled": False})
        assert s_off.is_enabled_for("a") is False


class TestBuildMemoryContext:
    """Render stored working memory as a prompt-context string block."""

    async def test_returns_empty_when_disabled_or_no_memory(self, service,
                                                            memory_manager):
        # Disabled (no agent_id) -> empty.
        assert await service.build_memory_context(None) == ""

        # Enabled but no memory stored -> empty.
        assert await service.build_memory_context("never-stored") == ""

    async def test_renders_stored_memory_as_prompt_block(self, service, memory_manager):
        await memory_manager.store_agent_working_memory({
            "agent_id":
            "vision",
            "summary":
            "Prior work on experiment A.",
        })

        context = await service.build_memory_context("vision")

        # The contract: "Agent Working Memory:\n{summary}\n\n<usage hint>".
        assert context.startswith("Agent Working Memory:\n")
        assert "Prior work on experiment A." in context
        assert "Prefer the current task" in context


class TestUpdateMemory:
    """update_memory: skip/write decisions + composed summary shape."""

    async def test_returns_none_when_disabled(self, service):
        # No agent_id => disabled => no write, return None.
        result = await service.update_memory(None, "task", {
            "status": "success",
            "data": {
                "content": "x"
            }
        })

        assert result is None

    async def test_skips_failed_status_by_default(self, service, memory_manager):
        result = await service.update_memory("agent-x", "task", {
            "status": "error",
            "error": "boom"
        })

        assert result is None
        assert await memory_manager.get_agent_working_memory("agent-x") is None

    async def test_writes_failed_status_when_update_on_failure_enabled(
            self, memory_manager):
        # Opt in via config flag — pin the only path that persists errors.
        s = AgentMemoryService(
            memory_manager,
            config={
                "enabled": True,
                "update_on_failure": True,
                "max_summary_chars": 1200
            },
        )

        result = await s.update_memory("agent-y", "task that failed", {
            "status": "error",
            "error": "boom"
        })

        assert result is not None
        stored = await memory_manager.get_agent_working_memory("agent-y")
        assert stored is not None
        assert "boom" in stored.summary

    async def test_first_run_creates_initial_summary(self, service):
        result = await service.update_memory("agent-1", "Analyze the dataset", {
            "status": "success",
            "data": {
                "content": "Found 3 trends"
            }
        })

        assert result is not None
        assert "Latest task:" in result.summary
        assert "Analyze the dataset" in result.summary
        assert "Latest result:" in result.summary
        assert "Found 3 trends" in result.summary
        # First run has no Recent context section.
        assert "Recent context:" not in result.summary

    async def test_subsequent_run_no_recursive_prior_context(self, service):
        # The classic regression: the FIRST summary ends up wrapped with
        # "Agent Working Memory: ... Use this as prior context ..." when
        # rendered via build_memory_context. If update_memory didn't strip
        # those wrappers from the EXISTING memory before composing the
        # NEW summary, prior context would nest indefinitely.
        await service.update_memory("memory-agent", "Remember alpha", {
            "status": "success",
            "data": {
                "content": "First result"
            }
        })

        second = await service.update_memory("memory-agent", "Use beta", {
            "status": "success",
            "data": {
                "content": "Second result"
            }
        })

        assert second is not None
        # No nested "Prior context:" (the wrapper from build_memory_context).
        assert second.summary.count("Prior context:") == 0
        # Recent context summarizes the previous Latest result.
        assert "Recent context:" in second.summary
        assert "Previous result: First result" in second.summary
        # New sections from the latest run.
        assert "Latest task:" in second.summary
        assert "Latest result:" in second.summary

    async def test_truncates_to_configured_max_chars(self, memory_manager):
        # Tight budget makes the truncation observable.
        s = AgentMemoryService(
            memory_manager,
            config={
                "enabled": True,
                "max_summary_chars": 80
            },
        )

        result = await s.update_memory("short-agent", "task " * 80, {
            "status": "success",
            "data": {
                "content": "result " * 80
            }
        })

        assert result is not None
        assert len(result.summary) <= 80

    async def test_summarizes_multimodal_task_with_image_count(self, service):
        # Multimodal task list: text parts joined + image URLs counted.
        task = [
            {
                "type": "text",
                "text": "Describe this figure"
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,a"
                }
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,b"
                }
            },
        ]

        result = await service.update_memory("vision-agent", task, {
            "status": "success",
            "data": {
                "content": "ok"
            }
        })

        assert result is not None
        assert "Describe this figure" in result.summary
        assert "[includes 2 image(s)]" in result.summary


class TestInjectMemoryContext:
    """inject_memory_context module function: prepend memory to a task."""

    def test_no_op_when_memory_context_empty(self):
        # Empty memory -> task returned untouched (preserves identity).
        text_task = "Just a task"
        list_task = [{"type": "text", "text": "x"}]

        assert inject_memory_context(text_task, "") is text_task
        assert inject_memory_context(list_task, "") is list_task

    def test_string_task_prepended_with_current_task_label(self):
        result = inject_memory_context("Analyze this", "Memory: prior work")

        assert isinstance(result, str)
        assert result == "Memory: prior work\n\nCurrent Task:\nAnalyze this"

    def test_list_task_gets_text_block_prepended(self):
        original = [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:..."
                }
            },
            {
                "type": "text",
                "text": "Describe"
            },
        ]

        result = inject_memory_context(original, "Memory: prior work")

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == {"type": "text", "text": "Memory: prior work"}
        # Original items preserved in order after the injected text block.
        assert result[1:] == original
