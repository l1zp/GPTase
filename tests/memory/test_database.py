"""Unit tests for gptase.memory.database.ConversationDatabase.

Covers the async sqlite connection lifecycle: lazy initialization,
schema bootstrap from schema.sql, execute/executemany/commit, persistence
across close-reopen, idempotent close, and the async context manager
contract.

Async tests run under pytest-asyncio mode='auto' (configured in
pyproject.toml). The `db` fixture provides an uninitialized
ConversationDatabase pointing at a tmp_path file and closes the
connection in teardown if the test opened it — necessary because
aiosqlite uses a worker thread that leaks across tests when not
joined.
"""
import pytest

from gptase.memory.database import ConversationDatabase


@pytest.fixture
async def db(tmp_path):
    """Uninitialized ConversationDatabase under tmp_path; auto-closes."""
    database = ConversationDatabase(str(tmp_path / "test.db"))
    try:
        yield database
    finally:
        if database._connection is not None:
            await database.close()


class TestConversationDatabaseInit:
    """Constructor: resolve path + create parent dir, but no connection yet."""

    async def test_init_resolves_path_and_creates_parent_dir(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        db_path = nested / "x.db"
        assert not nested.exists()

        ConversationDatabase(str(db_path))

        # Constructor mkdirs the parent chain.
        assert nested.is_dir()
        # File itself not created until initialize() runs.
        assert not db_path.exists()

    async def test_connection_lazy_until_first_use(self, db):
        # Bare __init__ does not open the connection — initialize()
        # or any execute() call is what actually opens it.
        assert db._connection is None


class TestSchemaInitialization:
    """initialize() applies schema.sql so the conversations table exists."""

    async def test_initialize_creates_tables_from_schema_sql(self, db):
        await db.initialize()

        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        rows = await cursor.fetchall()
        table_names = {row[0] for row in rows}

        # `conversations` is the canonical table consumed by storage.py.
        assert "conversations" in table_names


class TestExecuteAndCommit:
    """execute() / executemany() persist when followed by commit()."""

    async def test_execute_then_query_round_trip(self, db):
        await db.execute(
            "INSERT INTO conversations "
            "(id, timestamp, model_name, provider, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("conv-1", "2026-05-09T00:00:00", "gpt-4", "openai", "in_progress"),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT id, model_name FROM conversations WHERE id = ?",
            ("conv-1", ),
        )
        row = await cursor.fetchone()

        assert row == ("conv-1", "gpt-4")

    async def test_executemany_inserts_multiple_rows(self, db):
        rows = [
            ("conv-a", "2026-05-09T00:00:00", "m1", "p1", "in_progress"),
            ("conv-b", "2026-05-09T00:00:01", "m2", "p2", "in_progress"),
            ("conv-c", "2026-05-09T00:00:02", "m3", "p3", "in_progress"),
        ]
        await db.executemany(
            "INSERT INTO conversations "
            "(id, timestamp, model_name, provider, status) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        await db.commit()

        cursor = await db.execute("SELECT COUNT(*) FROM conversations")
        (count, ) = await cursor.fetchone()

        assert count == 3


class TestPersistenceAcrossReopen:
    """Data committed in one instance is visible from a fresh instance."""

    async def test_data_survives_close_and_reopen(self, tmp_path):
        db_path = str(tmp_path / "persist.db")

        # First instance: write + commit + close.
        first = ConversationDatabase(db_path)
        await first.execute(
            "INSERT INTO conversations "
            "(id, timestamp, model_name, provider, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("durable", "2026-05-09T00:00:00", "x", "y", "completed"),
        )
        await first.commit()
        await first.close()

        # Second instance: read — proves the data hit disk, not just memory.
        second = ConversationDatabase(db_path)
        try:
            cursor = await second.execute(
                "SELECT id FROM conversations WHERE id = ?",
                ("durable", ),
            )
            row = await cursor.fetchone()
        finally:
            await second.close()

        assert row[0] == "durable"


class TestClose:
    """close() cleans up; double-close is a no-op."""

    async def test_close_resets_connection_to_none(self, db):
        await db.initialize()
        assert db._connection is not None

        await db.close()

        assert db._connection is None

    async def test_close_is_idempotent(self, db):
        await db.initialize()
        await db.close()

        # Second close must not raise; the lock-protected check inside
        # close() short-circuits when _connection is already None.
        await db.close()

        assert db._connection is None


class TestAsyncContextManager:
    """`async with ConversationDatabase(...) as db:` initializes and closes.

    No call sites use this pattern today (storage.py manually pairs
    initialize/close), but it is the idiomatic Python contract for a
    resource manager and pinning it keeps the option open for future
    consumers.
    """

    async def test_aenter_initializes_aexit_closes(self, tmp_path):
        database = ConversationDatabase(str(tmp_path / "ctx.db"))

        async with database as ctx_db:
            assert ctx_db is database
            assert database._connection is not None

        # __aexit__ closed the connection.
        assert database._connection is None


class TestInitializeIdempotent:
    """Calling initialize() twice keeps the same connection."""

    async def test_initialize_called_twice_keeps_same_connection(self, db):
        await db.initialize()
        first_conn = db._connection

        await db.initialize()

        assert db._connection is first_conn
