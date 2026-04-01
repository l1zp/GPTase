"""Tests for one-time storage reset on schema version changes."""

import json

from gptase.memory.storage import ConversationStorage


async def _fetch_count(storage: ConversationStorage, table_name: str) -> int:
    cursor = await storage.db.execute(f"SELECT COUNT(*) FROM {table_name}")
    row = await cursor.fetchone()
    return int(row[0])


class TestStorageReset:

    async def test_initialize_clears_history_when_version_changes(self, tmp_path):
        db_path = tmp_path / "reset.db"

        storage = ConversationStorage(db_path=str(db_path))
        await storage.initialize()
        try:
            await storage.db.execute(
                """INSERT OR REPLACE INTO agent_states (agent_id, state_data, last_updated)
                   VALUES (?, ?, ?)""",
                (
                    "__storage_schema_version__",
                    json.dumps({"version": "legacy"}),
                    "2026-03-28T00:00:00",
                ),
            )
            await storage.db.execute(
                """INSERT INTO agent_working_memory
                   (agent_id, summary, metadata, last_updated)
                   VALUES (?, ?, ?, ?)""",
                (
                    "memory-agent",
                    "old summary",
                    "{}",
                    "2026-03-28T00:00:00",
                ),
            )
            await storage.db.execute(
                """INSERT INTO plan_checkpoints
                   (checkpoint_id, session_id, plan_id, created_at, updated_at,
                    checkpoint_data, status, total_steps, completed_steps)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "cp1",
                    "goal_1",
                    "demo-plan",
                    "2026-03-28T00:00:00",
                    "2026-03-28T00:00:00",
                    "{}",
                    "in_progress",
                    1,
                    0,
                ),
            )
            await storage.db.commit()
        finally:
            await storage.close()

        reopened = ConversationStorage(db_path=str(db_path))
        await reopened.initialize()
        try:
            assert await _fetch_count(reopened, "agent_working_memory") == 0
            assert await _fetch_count(reopened, "plan_checkpoints") == 0
            cursor = await reopened.db.execute(
                "SELECT state_data FROM agent_states WHERE agent_id = ?",
                ("__storage_schema_version__", ),
            )
            row = await cursor.fetchone()
            assert row is not None
            assert json.loads(row[0])["version"] != "legacy"
        finally:
            await reopened.close()
