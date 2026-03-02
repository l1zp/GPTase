"""Database connection manager for conversation tracking."""

import asyncio
from pathlib import Path
from typing import Optional

import aiosqlite

from src.core.logging import logger


class ConversationDatabase:
    """Async SQLite database manager for conversations."""

    def __init__(self, db_path: str = "data/conversations.db"):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database and create tables."""
        async with self._lock:
            if self._connection is None:
                self._connection = await aiosqlite.connect(self.db_path)
                await self._init_schema()
                logger.info(f"Conversation database initialized: {self.db_path}")

    async def _init_schema(self) -> None:
        """Read and execute schema.sql."""
        schema_path = Path(__file__).parent / "schema.sql"
        schema_sql = schema_path.read_text()

        # Split by semicolon and execute each statement
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                await self._connection.execute(statement)

        await self._connection.commit()

    async def execute(self, sql: str, params: tuple = ()):
        """Execute SQL with parameters."""
        if self._connection is None:
            await self.initialize()
        return await self._connection.execute(sql, params)

    async def executemany(self, sql: str, params_list: list):
        """Execute SQL with multiple parameter sets."""
        if self._connection is None:
            await self.initialize()
        return await self._connection.executemany(sql, params_list)

    async def commit(self) -> None:
        """Commit transaction."""
        if self._connection:
            await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        async with self._lock:
            if self._connection:
                await self._connection.close()
                self._connection = None
                logger.info("Conversation database closed")
