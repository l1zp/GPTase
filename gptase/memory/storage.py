"""Conversation storage for tracking LLM interactions."""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)
from gptase.memory.database import ConversationDatabase
from gptase.memory.models import AgentWorkingMemory
from gptase.memory.models import Conversation
from gptase.memory.models import ConversationStatus
from gptase.memory.models import ExtractionSession
from gptase.memory.models import ExtractionSessionStatus
from gptase.memory.models import ExtractionSessionStep
from gptase.memory.models import ExtractionStepStatus
from gptase.memory.models import Message
from gptase.memory.models import Response

_STORAGE_SCHEMA_VERSION = "2026_03_session_split_v1"


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
            await self._ensure_storage_schema_version()

    async def close(self) -> None:
        """Close database connection.

        Must be called before program exit to prevent aiosqlite
        'Event loop is closed' errors.
        """
        if self.enabled and self.db:
            await self.db.close()

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

        message_records = []
        for i, msg in enumerate(messages):
            content = msg["content"]
            # Serialize list-type content (e.g., multimodal vision messages)
            if isinstance(content, list):
                content = json.dumps(content)
            message_records.append((
                str(uuid4()),
                conversation_id,
                msg["role"],
                content,
                i,
                time.time_ns(),
            ))

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

    async def update_response(
        self,
        response_id: str,
        response_content: Optional[str] = None,
        reasoning_content: Optional[str] = None,
        usage: Optional[Dict[str, int]] = None,
        latency_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update an existing response.

        Args:
            response_id: Response ID to update.
            response_content: New response content.
            reasoning_content: New reasoning content.
            usage: Token usage dict.
            latency_seconds: Request latency.
            metadata: Additional metadata.
        """
        if not self.enabled or response_id == "tracking_disabled":
            return

        # Build update query dynamically based on provided fields
        updates = []
        params = []

        if response_content is not None:
            updates.append("content = ?")
            params.append(response_content)
        if reasoning_content is not None:
            updates.append("reasoning_content = ?")
            params.append(reasoning_content)
        if usage is not None:
            params.extend([
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                usage.get("total_tokens"),
            ])
            updates.append("prompt_tokens = ?")
            updates.append("completion_tokens = ?")
            updates.append("total_tokens = ?")
        if latency_seconds is not None:
            updates.append("latency_seconds = ?")
            params.append(latency_seconds)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return

        params.append(response_id)
        query = f"UPDATE responses SET {', '.join(updates)} WHERE id = ?"

        await self.db.execute(query, tuple(params))
        await self.db.commit()

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
        # NOTE: no commit here — stream chunks are batched and committed
        # when streaming completes (via update_response / complete_conversation)

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
            (conversation_id, ),
        )
        conv_row = await cursor.fetchone()
        if not conv_row:
            return None

        # Get messages
        cursor = await self.db.execute(
            """SELECT role, content, sequence_number FROM messages
               WHERE conversation_id = ? ORDER BY sequence_number""",
            (conversation_id, ),
        )
        message_rows = await cursor.fetchall()

        # Get response
        cursor = await self.db.execute(
            """SELECT * FROM responses WHERE conversation_id = ?""",
            (conversation_id, ),
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

    # ===== Extraction Session Management =====

    async def start_extraction_session(
        self,
        document_path: str,
        extraction_type: str,
        agent_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new extraction session and return session ID.

        Args:
            document_path: Path or identifier of the document being processed.
            extraction_type: Type of extraction (e.g., 'kinetics', 'design').
            agent_id: Agent ID performing the extraction.
            metadata: Optional metadata for the session.

        Returns:
            Session ID (UUID).
        """
        if not self.enabled:
            return "tracking_disabled"

        session = ExtractionSession(
            document_path=document_path,
            extraction_type=extraction_type,
            agent_id=agent_id,
            metadata=metadata or {},
        )

        await self.db.execute(
            """INSERT INTO extraction_sessions
               (id, timestamp, document_path, extraction_type, agent_id, status,
                total_llm_calls, phase, metadata, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.id,
                session.timestamp.isoformat(),
                session.document_path,
                session.extraction_type,
                session.agent_id,
                session.status.value,
                session.total_llm_calls,
                session.phase,
                json.dumps(session.metadata),
                session.started_at.isoformat(),
            ),
        )
        await self.db.commit()

        logger.info(f"Started extraction session: {session.id} for {document_path}")
        return session.id

    async def update_session_phase(
        self,
        session_id: str,
        phase: str,
    ) -> None:
        """Update the current phase of a session.

        Args:
            session_id: Session ID to update.
            phase: New phase identifier (e.g., 'structure_analysis', 'extraction').
        """
        if not self.enabled or session_id == "tracking_disabled":
            return

        await self.db.execute(
            """UPDATE extraction_sessions SET phase = ? WHERE id = ?""",
            (phase, session_id),
        )
        await self.db.commit()

    async def complete_extraction_session(
        self,
        session_id: str,
        status: ExtractionSessionStatus = ExtractionSessionStatus.COMPLETED,
    ) -> None:
        """Mark session as completed/failed/partial.

        Args:
            session_id: Session ID to complete.
            status: Final status.
        """
        if not self.enabled or session_id == "tracking_disabled":
            return

        from datetime import datetime

        await self.db.execute(
            """UPDATE extraction_sessions
               SET status = ?, completed_at = ?
               WHERE id = ?""",
            (status.value, datetime.now().isoformat(), session_id),
        )
        await self.db.commit()
        logger.info(
            f"Completed extraction session: {session_id} with status {status.value}")

    async def _ensure_storage_schema_version(self) -> None:
        """Reset persisted history once when the storage layout version changes."""
        current_version = await self._get_storage_schema_version()
        if current_version == _STORAGE_SCHEMA_VERSION:
            return

        await self._reset_legacy_history()
        await self.db.execute(
            """INSERT OR REPLACE INTO agent_states
               (agent_id, state_data, last_updated)
               VALUES (?, ?, ?)""",
            (
                "__storage_schema_version__",
                json.dumps({"version": _STORAGE_SCHEMA_VERSION}),
                time.strftime("%Y-%m-%dT%H:%M:%S"),
            ),
        )
        await self.db.commit()

    async def _get_storage_schema_version(self) -> Optional[str]:
        cursor = await self.db.execute(
            "SELECT state_data FROM agent_states WHERE agent_id = ?",
            ("__storage_schema_version__", ),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        try:
            payload = json.loads(row[0])
        except Exception:
            return None
        if isinstance(payload, dict):
            return payload.get("version")
        return None

    async def _reset_legacy_history(self) -> None:
        """Clear historical tracking data before switching to the new layout."""
        tables = [
            "conversations",
            "messages",
            "responses",
            "stream_chunks",
            "model_parameters",
            "extraction_sessions",
            "extraction_session_steps",
            "extraction_results",
            "agent_messages",
            "agent_tasks",
            "agent_states",
            "agent_working_memory",
            "plan_checkpoints",
        ]
        for table in tables:
            await self.db.execute(f"DELETE FROM {table}")
        await self.db.commit()

    async def start_session_step(
        self,
        session_id: str,
        step_name: str,
        step_phase: str,
        step_order: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Start a new step within a session and return step ID.

        Args:
            session_id: Parent session ID.
            step_name: Human-readable step name.
            step_phase: Phase identifier for the step.
            step_order: Sequential order of the step.
            metadata: Optional metadata for the step.

        Returns:
            Step ID (UUID).
        """
        if not self.enabled or session_id == "tracking_disabled":
            return "tracking_disabled"

        from datetime import datetime

        step = ExtractionSessionStep(
            session_id=session_id,
            step_name=step_name,
            step_phase=step_phase,
            step_order=step_order,
            metadata=metadata or {},
            status=ExtractionStepStatus.IN_PROGRESS,
            started_at=datetime.now(),
        )

        await self.db.execute(
            """INSERT INTO extraction_session_steps
               (id, session_id, step_name, step_phase, conversation_id,
                status, started_at, error_message, step_order, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                step.id,
                step.session_id,
                step.step_name,
                step.step_phase,
                step.conversation_id,
                step.status.value,
                step.started_at.isoformat() if step.started_at else None,
                step.error_message,
                step.step_order,
                json.dumps(step.metadata),
            ),
        )
        await self.db.commit()

        logger.debug(f"Started step: {step.step_name} ({step.id})")
        return step.id

    async def link_step_to_conversation(
        self,
        step_id: str,
        conversation_id: str,
    ) -> None:
        """Link a step to a conversation after it's created.

        Args:
            step_id: Step ID to link.
            conversation_id: Conversation ID to link to.
        """
        if not self.enabled or step_id == "tracking_disabled":
            return

        await self.db.execute(
            """UPDATE extraction_session_steps
               SET conversation_id = ?
               WHERE id = ?""",
            (conversation_id, step_id),
        )
        await self.db.commit()

        logger.debug(f"Linked step {step_id} to conversation {conversation_id}")

    async def complete_session_step(
        self,
        step_id: str,
        status: ExtractionStepStatus = ExtractionStepStatus.COMPLETED,
        error_message: Optional[str] = None,
    ) -> None:
        """Mark a step as completed/failed.

        Args:
            step_id: Step ID to complete.
            status: Final status.
            error_message: Optional error message if status is FAILED.
        """
        if not self.enabled or step_id == "tracking_disabled":
            return

        from datetime import datetime

        await self.db.execute(
            """UPDATE extraction_session_steps
               SET status = ?, completed_at = ?, error_message = ?
               WHERE id = ?""",
            (status.value, datetime.now().isoformat(), error_message, step_id),
        )
        await self.db.commit()

        logger.debug(f"Completed step {step_id} with status {status.value}")

    async def save_extraction_result(
        self,
        session_id: str,
        result_type: str,
        content: str,
    ) -> str:
        """Save an extraction result for a session.

        Args:
            session_id: Session ID.
            result_type: Type of result (e.g., 'reactions', 'pipeline', 'document_analysis').
            content: JSON string content.

        Returns:
            Result ID (UUID).
        """
        if not self.enabled or session_id == "tracking_disabled":
            return "tracking_disabled"

        from datetime import datetime
        from uuid import uuid4

        result_id = str(uuid4())
        created_at = datetime.now().isoformat()

        await self.db.execute(
            """INSERT INTO extraction_results
               (id, session_id, result_type, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (result_id, session_id, result_type, content, created_at),
        )
        await self.db.commit()

        logger.info(f"Saved extraction result: {result_type} for session {session_id}")
        return result_id

    # ===== Agent Memory & Task Methods (Merged from MemoryManager) =====

    async def store_agent_task(self, task: "AgentTask") -> str:
        """Store an agent task execution record.

        Args:
            task: AgentTask object to store.
        """
        if not self.enabled:
            return "tracking_disabled"

        await self.db.execute(
            """INSERT INTO agent_tasks
               (id, task_id, agent_id, content, status, error, execution_time, tools_used, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.id,
                task.task_id,
                task.agent_id,
                task.content,
                task.status,
                task.error,
                task.execution_time,
                json.dumps(task.tools_used),
                task.timestamp.isoformat(),
            ),
        )
        await self.db.commit()
        return task.id

    async def get_agent_tasks(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve task execution history.

        Args:
            agent_id: Optional filter by agent ID.
            limit: Maximum number of tasks to return.
        """
        if not self.enabled:
            return []

        sql = "SELECT * FROM agent_tasks"
        params = []
        if agent_id:
            sql += " WHERE agent_id = ?"
            params.append(agent_id)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = await self.db.execute(sql, tuple(params))
        rows = await cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in rows:
            data = dict(zip(columns, row))
            data["tools_used"] = json.loads(
                data["tools_used"]) if data.get("tools_used") else []
            results.append(data)
        return results

    async def store_agent_state(self, state: "PersistedAgentState") -> str:
        """Upsert the cached runtime state of an agent.

        Args:
            state: PersistedAgentState object to store.
        """
        if not self.enabled:
            return "tracking_disabled"

        await self.db.execute(
            """INSERT OR REPLACE INTO agent_states
               (agent_id, state_data, last_updated)
               VALUES (?, ?, ?)""",
            (
                state.agent_id,
                state.state_data,
                state.last_updated.isoformat(),
            ),
        )
        await self.db.commit()
        return state.agent_id

    async def get_agent_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the latest cached state of an agent.

        Args:
            agent_id: Agent identifier to look up.
        """
        if not self.enabled:
            return None

        cursor = await self.db.execute(
            "SELECT state_data FROM agent_states WHERE agent_id = ?", (agent_id, ))
        row = await cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None

    async def store_agent_message(self, message: "AgentMessage") -> str:
        """Store an inter-agent message.

        Args:
            message: AgentMessage object to store.
        """
        if not self.enabled:
            return "tracking_disabled"

        await self.db.execute(
            """INSERT INTO agent_messages
               (id, sender, recipient, content, message_type, metadata, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                message.id,
                message.sender,
                message.recipient,
                str(message.content)
                if not isinstance(message.content, str) else message.content,
                message.message_type,
                json.dumps(message.metadata),
                message.timestamp.isoformat(),
            ),
        )
        await self.db.commit()
        return message.id

    async def get_agent_messages(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
        since: Optional["datetime"] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve message history for an agent.

        Args:
            agent_id: Optional filter by agent participation (speaker or recipient).
            limit: Maximum number of messages to return.
            since: Only return messages after this timestamp.
        """
        if not self.enabled:
            return []

        sql = "SELECT * FROM agent_messages"
        params = []
        conditions = []

        if agent_id:
            conditions.append("(sender = ? OR recipient = ?)")
            params.extend([agent_id, agent_id])

        if since:
            conditions.append("timestamp > ?")
            params.append(since.isoformat())

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)

        cursor = await self.db.execute(sql, tuple(params))
        rows = await cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in rows:
            data = dict(zip(columns, row))
            data["metadata"] = json.loads(
                data["metadata"]) if data.get("metadata") else {}
            results.append(data)
        return results

    async def store_agent_working_memory(self, memory: AgentWorkingMemory) -> str:
        """Upsert compressed working memory for an agent."""
        if not self.enabled:
            return "tracking_disabled"

        await self.db.execute(
            """INSERT OR REPLACE INTO agent_working_memory
               (agent_id, summary, metadata, last_updated)
               VALUES (?, ?, ?, ?)""",
            (
                memory.agent_id,
                memory.summary,
                json.dumps(memory.metadata),
                memory.last_updated.isoformat(),
            ),
        )
        await self.db.commit()
        return memory.agent_id

    async def get_agent_working_memory(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve compressed working memory for an agent."""
        if not self.enabled:
            return None

        cursor = await self.db.execute(
            """SELECT agent_id, summary, metadata, last_updated
               FROM agent_working_memory
               WHERE agent_id = ?""",
            (agent_id, ),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        return {
            "agent_id": row[0],
            "summary": row[1],
            "metadata": json.loads(row[2]) if row[2] else {},
            "last_updated": row[3],
        }
