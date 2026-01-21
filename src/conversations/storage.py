"""Conversation storage for tracking LLM interactions."""

import json
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.conversations.database import ConversationDatabase
from src.conversations.models import (
    Conversation,
    ConversationStatus,
    Message,
    ModelParameters,
    Response,
)
from src.core.logging import logger


class ConversationStorage:
    """Storage manager for conversation tracking.

    This class provides a high-level interface for storing and retrieving
    conversation data, separate from the existing MemoryManager system.

    Attributes:
        db: Database connection manager.
        enabled: Whether tracking is enabled.
    """

    def __init__(self, db_path: str = "data/conversations.db", enabled: bool = True):
        self.db = ConversationDatabase(db_path)
        self.enabled = enabled
        self._current_conversation: Optional[str] = None

    async def initialize(self) -> None:
        """Initialize storage."""
        if self.enabled:
            await self.db.initialize()

    async def start_conversation(
        self,
        model_name: str,
        provider: str,
        config: Any,
        agent_id: Optional[str] = None,
    ) -> str:
        """Start a new conversation and return its ID.

        Args:
            model_name: Name of the model being used.
            provider: LLM provider name.
            config: Model configuration.
            agent_id: Optional agent ID that initiated the conversation.

        Returns:
            Conversation ID (UUID).
        """
        if not self.enabled:
            return "tracking_disabled"

        conv = Conversation(
            model_name=model_name,
            provider=provider,
            agent_id=agent_id,
        )

        await self.db.execute(
            """INSERT INTO conversations
               (id, timestamp, model_name, provider, agent_id, status, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                conv.id,
                conv.timestamp.isoformat(),
                conv.model_name,
                conv.provider,
                conv.agent_id,
                conv.status.value,
                "{}",
            ),
        )
        await self.db.commit()

        # Store model parameters
        params = ModelParameters(
            conversation_id=conv.id,
            temperature=getattr(config, "temperature", None),
            max_tokens=getattr(config, "max_tokens", None),
            top_p=getattr(config, "provider_config", {}).get("top_p") if hasattr(config, "provider_config") else None,
            enable_thinking=getattr(config, "enable_thinking", False),
            system_prompt=getattr(config, "system_prompt", None),
        )

        await self.db.execute(
            """INSERT INTO model_parameters
               (id, conversation_id, temperature, max_tokens, top_p, enable_thinking, system_prompt)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (params.id, params.conversation_id, params.temperature,
             params.max_tokens, params.top_p, params.enable_thinking,
             params.system_prompt),
        )
        await self.db.commit()

        self._current_conversation = conv.id
        logger.debug(f"Started conversation: {conv.id}")
        return conv.id

    async def add_messages(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
    ) -> None:
        """Store input messages.

        Args:
            conversation_id: Conversation ID.
            messages: List of message dicts with 'role' and 'content'.
        """
        if not self.enabled or conversation_id == "tracking_disabled":
            return

        message_records = [
            (
                str(uuid4()),
                conversation_id,
                msg["role"],
                msg["content"],
                i,
                time.time_ns(),
            )
            for i, msg in enumerate(messages)
        ]

        await self.db.executemany(
            """INSERT INTO messages
               (id, conversation_id, role, content, sequence_number, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            message_records,
        )
        await self.db.commit()

    async def add_response(
        self,
        conversation_id: str,
        response_content: str,
        reasoning_content: Optional[str] = None,
        usage: Optional[Dict[str, int]] = None,
        latency_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store LLM response.

        Args:
            conversation_id: Conversation ID.
            response_content: Response text.
            reasoning_content: Optional thinking/reasoning content.
            usage: Token usage dict.
            latency_seconds: Request latency.
            metadata: Additional metadata.

        Returns:
            Response ID.
        """
        if not self.enabled or conversation_id == "tracking_disabled":
            return "tracking_disabled"

        resp = Response(
            conversation_id=conversation_id,
            content=response_content,
            reasoning_content=reasoning_content,
            prompt_tokens=usage.get("prompt_tokens") if usage else None,
            completion_tokens=usage.get("completion_tokens") if usage else None,
            total_tokens=usage.get("total_tokens") if usage else None,
            latency_seconds=latency_seconds,
            metadata=metadata or {},
        )

        await self.db.execute(
            """INSERT INTO responses
               (id, conversation_id, content, reasoning_content,
                prompt_tokens, completion_tokens, total_tokens,
                latency_seconds, metadata, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                resp.id,
                resp.conversation_id,
                resp.content,
                resp.reasoning_content,
                resp.prompt_tokens,
                resp.completion_tokens,
                resp.total_tokens,
                resp.latency_seconds,
                json.dumps(resp.metadata),
                resp.timestamp.isoformat(),
            ),
        )
        await self.db.commit()

        return resp.id

    async def add_stream_chunk(
        self,
        response_id: str,
        chunk_index: int,
        content: str = "",
        reasoning_content: str = "",
        is_thinking: bool = False,
        is_complete: bool = False,
    ) -> None:
        """Store a streaming chunk for real-time replay.

        Args:
            response_id: Parent response ID.
            chunk_index: Chunk sequence number.
            content: Content chunk.
            reasoning_content: Reasoning content chunk.
            is_thinking: Whether this is a thinking chunk.
            is_complete: Whether this is the final chunk.
        """
        if not self.enabled or response_id == "tracking_disabled":
            return

        await self.db.execute(
            """INSERT INTO stream_chunks
               (id, response_id, chunk_index, content, reasoning_content, is_thinking, is_complete, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid4()),
                response_id,
                chunk_index,
                content,
                reasoning_content,
                1 if is_thinking else 0,
                1 if is_complete else 0,
                time.time_ns(),
            ),
        )
        await self.db.commit()

    async def complete_conversation(
        self,
        conversation_id: str,
        status: ConversationStatus = ConversationStatus.COMPLETED,
        error_message: Optional[str] = None,
    ) -> None:
        """Mark conversation as completed.

        Args:
            conversation_id: Conversation ID.
            status: Final status.
            error_message: Optional error message if status is ERROR.
        """
        if not self.enabled or conversation_id == "tracking_disabled":
            return

        await self.db.execute(
            """UPDATE conversations SET status = ?, error_message = ? WHERE id = ?""",
            (status.value, error_message, conversation_id),
        )
        await self.db.commit()
        self._current_conversation = None

    async def get_conversation(
        self,
        conversation_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get full conversation details with messages and response.

        Args:
            conversation_id: Conversation ID.

        Returns:
            Dictionary with conversation data, or None if not found.
        """
        if not self.enabled:
            return None

        # Get conversation
        cursor = await self.db.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        conv_row = await cursor.fetchone()
        if not conv_row:
            return None

        # Get messages
        cursor = await self.db.execute(
            """SELECT role, content, sequence_number FROM messages
               WHERE conversation_id = ? ORDER BY sequence_number""",
            (conversation_id,),
        )
        message_rows = await cursor.fetchall()

        # Get response
        cursor = await self.db.execute(
            """SELECT * FROM responses WHERE conversation_id = ?""",
            (conversation_id,),
        )
        response_row = await cursor.fetchone()

        return {
            "conversation": conv_row,
            "messages": message_rows,
            "response": response_row,
        }

    async def list_conversations(
        self,
        limit: int = 100,
        offset: int = 0,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List conversations with pagination.

        Args:
            limit: Maximum number to return.
            offset: Pagination offset.
            agent_id: Optional filter by agent ID.

        Returns:
            List of conversation dictionaries.
        """
        if not self.enabled:
            return []

        sql = "SELECT * FROM conversations"
        params = []

        if agent_id:
            sql += " WHERE agent_id = ?"
            params.append(agent_id)

        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self.db.execute(sql, tuple(params))
        rows = await cursor.fetchall()

        # Convert to list of dicts
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def search_conversations(
        self,
        query: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search conversations by content.

        Args:
            query: Search term.
            limit: Maximum results.

        Returns:
            List of matching conversations.
        """
        if not self.enabled:
            return []

        pattern = f"%{query}%"
        cursor = await self.db.execute(
            """SELECT DISTINCT c.* FROM conversations c
               INNER JOIN messages m ON c.id = m.conversation_id
               WHERE m.content LIKE ?
               ORDER BY c.timestamp DESC
               LIMIT ?""",
            (pattern, limit),
        )
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics.

        Returns:
            Dictionary with stats.
        """
        if not self.enabled:
            return {"tracking_enabled": False}

        cursor = await self.db.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                 SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                 SUM(total_tokens) as total_tokens,
                 SUM(total_duration_seconds) as total_duration
               FROM conversations"""
        )
        row = await cursor.fetchone()

        return {
            "tracking_enabled": True,
            "total_conversations": row[0],
            "completed": row[1],
            "errors": row[2],
            "total_tokens": row[3],
            "total_duration_seconds": row[4],
        }
