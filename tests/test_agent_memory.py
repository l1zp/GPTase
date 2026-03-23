"""Tests for agent working memory integration."""

import pytest

from gptase.agents import Agent
from gptase.memory.agent_memory import AgentMemoryService
from gptase.memory.manager import MemoryManager
from gptase.memory.storage import ConversationStorage
from gptase.models.types import ModelConfig


@pytest.fixture
async def memory_manager(tmp_path):
    """Provide an isolated MemoryManager backed by a temp SQLite db."""
    db_path = tmp_path / "agent_memory.db"
    manager = MemoryManager(
        storage=ConversationStorage(db_path=str(db_path)),
        config={"enabled": True, "max_summary_chars": 1200},
    )
    await manager.initialize()
    try:
        yield manager
    finally:
        await manager.close()


def _mock_config() -> ModelConfig:
    return ModelConfig(
        use_mock=True,
        model_name="test-model",
        api_key="test-key",
    )


class TestAgentWorkingMemory:
    @pytest.mark.asyncio
    async def test_named_agent_persists_and_reuses_memory(self, memory_manager):
        """A named agent should write memory after a run and inject it next time."""
        agent = Agent(system_prompt="Test agent",
                      model_config=_mock_config(),
                      agent_id="memory-agent",
                      memory_manager=memory_manager)

        captured_tasks = []

        async def mock_run_with_llm(task):
            captured_tasks.append(task)
            return {"status": "success", "data": {"content": "first result"}}

        agent._run_with_llm = mock_run_with_llm

        await agent.run("Remember this fact")
        stored = await memory_manager.get_agent_working_memory("memory-agent")
        assert stored is not None
        assert "Remember this fact" in stored.summary
        assert "first result" in stored.summary

        async def second_mock_run_with_llm(task):
            captured_tasks.append(task)
            return {"status": "success", "data": {"content": "second result"}}

        agent._run_with_llm = second_mock_run_with_llm
        await agent.run("Use prior context")

        assert len(captured_tasks) == 2
        assert isinstance(captured_tasks[1], str)
        assert "Agent Working Memory:" in captured_tasks[1]
        assert "Remember this fact" in captured_tasks[1]
        assert "first result" in captured_tasks[1]

    @pytest.mark.asyncio
    async def test_anonymous_agent_does_not_write_memory(self, memory_manager):
        """Agents without agent_id should skip working memory entirely."""
        agent = Agent(system_prompt="Anonymous",
                      model_config=_mock_config(),
                      memory_manager=memory_manager)

        async def mock_run_with_llm(task):
            return {"status": "success", "data": {"content": "ok"}}

        agent._run_with_llm = mock_run_with_llm
        await agent.run("Stateless task")

        assert await memory_manager.get_agent_working_memory("") is None

    @pytest.mark.asyncio
    async def test_failed_run_does_not_update_memory_by_default(self, memory_manager):
        """Errors should not pollute working memory unless explicitly enabled."""
        agent = Agent(system_prompt="Test agent",
                      model_config=_mock_config(),
                      agent_id="memory-agent",
                      memory_manager=memory_manager)

        async def mock_run_with_llm(task):
            return {"status": "error", "error": "boom"}

        agent._run_with_llm = mock_run_with_llm
        await agent.run("This should fail")

        assert await memory_manager.get_agent_working_memory("memory-agent") is None

    @pytest.mark.asyncio
    async def test_multimodal_memory_is_injected_as_text_prefix(self, memory_manager):
        """Prior memory should be prepended as a text block for multimodal tasks."""
        agent = Agent(system_prompt="Vision agent",
                      model_config=_mock_config(),
                      agent_id="vision-agent",
                      memory_manager=memory_manager)

        await memory_manager.store_agent_working_memory({
            "agent_id": "vision-agent",
            "summary": "Prior context: This image set is from experiment A.",
        })

        captured_task = None

        async def mock_run_with_llm(task):
            nonlocal captured_task
            captured_task = task
            return {"status": "success", "data": {"content": "done"}}

        agent._run_with_llm = mock_run_with_llm
        await agent.run([{
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64,abc"
            }
        }, {
            "type": "text",
            "text": "Analyze the figure"
        }])

        assert isinstance(captured_task, list)
        assert captured_task[0]["type"] == "text"
        assert "Agent Working Memory:" in captured_task[0]["text"]
        assert "experiment A" in captured_task[0]["text"]


class TestAgentMemoryService:
    @pytest.mark.asyncio
    async def test_summary_is_truncated_to_configured_limit(self, memory_manager):
        """Compressed summaries should respect the configured max length."""
        service = AgentMemoryService(memory_manager,
                                     config={"enabled": True, "max_summary_chars": 80})

        long_task = "task " * 80
        long_result = {"status": "success", "data": {"content": "result " * 80}}
        memory = await service.update_memory("short-memory-agent", long_task, long_result)

        assert memory is not None
        assert len(memory.summary) <= 80
