"""Tests for TodoTool, TodoStore, TodoItem and reset_session_todos."""

from copy import deepcopy
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from gptase.models.types import ModelResponse
from gptase.models.types import ToolCall
from gptase.tools.executor import ToolExecutor
from gptase.tools.handlers import reset_session_todos
from gptase.tools.handlers import TodoItem
from gptase.tools.handlers import TodoStore
from gptase.tools.handlers import TodoTool

# ---------------------------------------------------------------------------
# Shared cleanup: ensure the module-level _todo_store is clean before each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_todo_store():
    """Reset the shared in-memory todo store before and after every test."""
    reset_session_todos()
    yield
    reset_session_todos()


# ---------------------------------------------------------------------------
# TestTodoItem
# ---------------------------------------------------------------------------


class TestTodoItem:
    """Tests for the TodoItem dataclass."""

    def test_fields_are_stored(self):
        item = TodoItem(id="abc12345", content="do work", status="pending", priority="high")

        assert item.id == "abc12345"
        assert item.content == "do work"
        assert item.status == "pending"
        assert item.priority == "high"

    def test_status_is_mutable(self):
        item = TodoItem(id="abc12345", content="do work", status="pending", priority="medium")

        item.status = "completed"

        assert item.status == "completed"


# ---------------------------------------------------------------------------
# TestTodoStore
# ---------------------------------------------------------------------------


class TestTodoStore:
    """Tests for TodoStore CRUD operations."""

    def test_create_returns_item_with_id_and_defaults(self):
        store = TodoStore()

        item = store.create("analyze data")

        assert item.content == "analyze data"
        assert item.status == "pending"
        assert item.priority == "medium"
        assert len(item.id) == 8

    def test_create_respects_priority(self):
        store = TodoStore()

        item = store.create("urgent task", priority="high")

        assert item.priority == "high"

    def test_create_assigns_unique_ids(self):
        store = TodoStore()

        ids = {store.create(f"task {i}").id for i in range(10)}

        assert len(ids) == 10

    def test_update_existing_item_returns_updated_item(self):
        store = TodoStore()
        item = store.create("step 1")

        result = store.update(item.id, "in_progress")

        assert result is not None
        assert result.status == "in_progress"
        assert result.id == item.id

    def test_update_nonexistent_id_returns_none(self):
        store = TodoStore()

        result = store.update("badid00", "completed")

        assert result is None

    def test_update_mutates_in_place(self):
        store = TodoStore()
        item = store.create("step 1")

        store.update(item.id, "completed")

        assert store.list_all()[0].status == "completed"

    def test_list_all_empty_on_new_store(self):
        store = TodoStore()

        assert store.list_all() == []

    def test_list_all_returns_all_created_items(self):
        store = TodoStore()
        store.create("a")
        store.create("b")

        items = store.list_all()

        assert len(items) == 2
        contents = {i.content for i in items}
        assert contents == {"a", "b"}

    def test_list_all_returns_copy_not_internal_reference(self):
        store = TodoStore()
        store.create("a")

        items = store.list_all()
        items.clear()

        assert len(store.list_all()) == 1

    def test_reset_clears_all_items(self):
        store = TodoStore()
        store.create("a")
        store.create("b")

        store.reset()

        assert store.list_all() == []


# ---------------------------------------------------------------------------
# TestResetSessionTodos
# ---------------------------------------------------------------------------


class TestResetSessionTodos:
    """Tests for the module-level reset_session_todos function."""

    def test_clears_items_created_via_todo_tool(self):
        # Arrange: create todos through the tool (uses shared _todo_store)
        tool = TodoTool()
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            tool.execute(action="create", content="item A")
        )

        # Act
        reset_session_todos()

        # Assert: list is empty
        result = asyncio.get_event_loop().run_until_complete(tool.execute(action="list"))
        assert result == "[INFO] No todos."

    def test_does_not_raise_on_empty_store(self):
        # Should be idempotent
        reset_session_todos()
        reset_session_todos()


# ---------------------------------------------------------------------------
# TestTodoTool — action: create
# ---------------------------------------------------------------------------


class TestTodoToolCreate:
    """Tests for TodoTool action='create'."""

    async def test_create_returns_ok_with_id(self):
        tool = TodoTool()

        result = await tool.execute(action="create", content="extract Km values")

        assert result.startswith("[OK] Created todo [")
        assert "extract Km values" in result
        assert "(medium)" in result

    async def test_create_with_high_priority(self):
        tool = TodoTool()

        result = await tool.execute(action="create", content="urgent", priority="high")

        assert "(high)" in result

    async def test_create_missing_content_returns_error(self):
        tool = TodoTool()

        result = await tool.execute(action="create")

        assert result.startswith("[ERROR]")
        assert "content" in result

    async def test_create_multiple_items_are_independent(self):
        tool = TodoTool()

        r1 = await tool.execute(action="create", content="step 1")
        r2 = await tool.execute(action="create", content="step 2")

        id1 = r1.split("Created todo [")[1].split("]")[0]
        id2 = r2.split("Created todo [")[1].split("]")[0]
        assert id1 != id2


# ---------------------------------------------------------------------------
# TestTodoTool — action: update
# ---------------------------------------------------------------------------


class TestTodoToolUpdate:
    """Tests for TodoTool action='update'."""

    async def test_update_changes_status(self):
        tool = TodoTool()
        create_result = await tool.execute(action="create", content="step 1")
        todo_id = create_result.split("Created todo [")[1].split("]")[0]

        result = await tool.execute(action="update", todo_id=todo_id, status="in_progress")

        assert "[OK]" in result
        assert "in_progress" in result

    async def test_update_through_full_lifecycle(self):
        tool = TodoTool()
        create_result = await tool.execute(action="create", content="step 1")
        todo_id = create_result.split("Created todo [")[1].split("]")[0]

        await tool.execute(action="update", todo_id=todo_id, status="in_progress")
        result = await tool.execute(action="update", todo_id=todo_id, status="completed")

        assert "completed" in result

    async def test_update_nonexistent_id_returns_error(self):
        tool = TodoTool()

        result = await tool.execute(action="update", todo_id="notexist", status="completed")

        assert result.startswith("[ERROR]")
        assert "notexist" in result

    async def test_update_missing_todo_id_returns_error(self):
        tool = TodoTool()

        result = await tool.execute(action="update", status="completed")

        assert result.startswith("[ERROR]")
        assert "todo_id" in result

    async def test_update_missing_status_returns_error(self):
        tool = TodoTool()

        result = await tool.execute(action="update", todo_id="abc12345")

        assert result.startswith("[ERROR]")
        assert "status" in result


# ---------------------------------------------------------------------------
# TestTodoTool — action: list
# ---------------------------------------------------------------------------


class TestTodoToolList:
    """Tests for TodoTool action='list'."""

    async def test_list_empty_store(self):
        tool = TodoTool()

        result = await tool.execute(action="list")

        assert result == "[INFO] No todos."

    async def test_list_shows_all_items(self):
        tool = TodoTool()
        await tool.execute(action="create", content="task A")
        await tool.execute(action="create", content="task B")

        result = await tool.execute(action="list")

        assert "task A" in result
        assert "task B" in result

    async def test_list_shows_correct_status_icons(self):
        tool = TodoTool()
        r = await tool.execute(action="create", content="pending task")
        todo_id = r.split("Created todo [")[1].split("]")[0]

        pending_list = await tool.execute(action="list")
        await tool.execute(action="update", todo_id=todo_id, status="in_progress")
        in_progress_list = await tool.execute(action="list")
        await tool.execute(action="update", todo_id=todo_id, status="completed")
        completed_list = await tool.execute(action="list")
        await tool.execute(action="update", todo_id=todo_id, status="cancelled")
        cancelled_list = await tool.execute(action="list")

        assert "[ ]" in pending_list
        assert "[~]" in in_progress_list
        assert "[x]" in completed_list
        assert "[-]" in cancelled_list

    async def test_list_shows_priority(self):
        tool = TodoTool()
        await tool.execute(action="create", content="hp task", priority="high")

        result = await tool.execute(action="list")

        assert "(high)" in result


# ---------------------------------------------------------------------------
# TestTodoTool — unknown action
# ---------------------------------------------------------------------------


class TestTodoToolUnknownAction:
    """Tests for unrecognised action values."""

    async def test_unknown_action_returns_error(self):
        tool = TodoTool()

        result = await tool.execute(action="delete")

        assert result.startswith("[ERROR]")
        assert "delete" in result
        assert "create, update, list" in result


# ---------------------------------------------------------------------------
# TestExecutorResetsTodos
# ---------------------------------------------------------------------------


class TestExecutorResetsTodos:
    """Verify that ToolExecutor.execute() resets the todo store at the start."""

    async def test_reset_session_todos_called_at_execute_start(self):
        # Arrange: a model that returns immediately with no tool calls
        model = MagicMock()
        model.default_config = None
        model.generate = AsyncMock(
            return_value=ModelResponse(
                content="done",
                usage={"prompt_tokens": 5, "completion_tokens": 2},
                model="test-model",
                provider="test-provider",
                tool_calls=None,
                finish_reason="stop",
            )
        )

        executor = ToolExecutor(model=model, max_iterations=1)

        with patch("gptase.tools.executor.reset_session_todos") as mock_reset:
            await executor.execute([{"role": "user", "content": "hello"}])

        mock_reset.assert_called_once()

    async def test_todos_from_previous_run_do_not_bleed_into_next(self):
        """Todos created in one execution should not appear in the next."""
        tool = TodoTool()

        # First run: create a todo
        await tool.execute(action="create", content="leftover todo")
        list_after_first = await tool.execute(action="list")
        assert "leftover todo" in list_after_first

        # Simulate what ToolExecutor does at the start of the next run
        reset_session_todos()

        list_after_reset = await tool.execute(action="list")
        assert list_after_reset == "[INFO] No todos."
