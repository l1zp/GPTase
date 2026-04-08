# Memory API

> [Home](../README.md) → [API](.) → Memory

**File:** `gptase/memory/agent_memory.py`, `gptase/memory/manager.py`, `gptase/memory/storage.py`

---

## MemoryManager

High-level interface for all agent memory operations. Backed by SQLite via `ConversationStorage`.

```python
from gptase.memory.manager import MemoryManager

memory = MemoryManager(
    storage: Optional[ConversationStorage] = None,  # auto-created if None
    config: Optional[Any] = None,                   # MemoryConfig or dict
)

await memory.initialize()
await memory.close()   # always call before program exit
```

### Conversation history

```python
history = await memory.get_conversation_history(
    agent_id: Optional[str] = None,
    limit: int = 50,
    since: Optional[datetime] = None,
) -> List[AgentMessage]

await memory.store_message(message: AgentMessage) -> str   # returns message ID
```

### Task results

```python
task_id = await memory.store_task_result(
    task_id: str,
    agent_id: str,
    result: Any,                        # auto-serialized to JSON if not str
    status: str = "completed",
    error: Optional[str] = None,
    execution_time: Optional[float] = None,
    tools_used: Optional[List[str]] = None,
) -> str

tasks = await memory.get_task_history(
    agent_id: Optional[str] = None,
    limit: int = 20,
) -> List[Task]
```

### Agent state

```python
await memory.store_agent_state(agent_state) -> str
# Accepts dict or any Pydantic model with an agent_id attribute.

state = await memory.get_agent_state(agent_id: str) -> Optional[Dict]
```

### Inter-agent messaging

```python
from gptase.memory.models import AgentMessage

# Send to an agent's queue (also persists to SQLite)
await memory.send_message(recipient: str, message: AgentMessage)

# Receive from queue (blocking with optional timeout)
msg = await memory.get_next_message(
    agent_id: str,
    timeout: Optional[float] = None,  # seconds; None = block forever
) -> Optional[AgentMessage]
```

### Stats and summaries

```python
usage = await memory.get_usage() -> Dict  # has_conversations, has_tasks, storage_type

summary = await memory.create_memory_summary(
    agent_id: Optional[str] = None,   # None = global summary
) -> Dict  # conversation_count, task_count, recent_conversations, recent_tasks
```

### Agent working memory

```python
from gptase.memory.agent_memory import AgentMemoryService

service = AgentMemoryService(memory, config)

context = await service.build_memory_context(agent_id: str) -> str
updated = await service.update_memory(
    agent_id: str,
    task_input: str | List[Dict],
    result: Dict[str, Any],
) -> AgentWorkingMemory | None
```

Named agents use this service automatically during `Agent.run()`:

- load compressed prior context before execution
- inject that context into the current task
- compress the latest task + result after a successful run
- skip working memory for anonymous agents

---

## SQLite Tables

All data is stored in a single SQLite database (default: `data/conversations.db`).

| Table | Purpose | Key columns |
|---|---|---|
| `conversations` | LLM interactions | model, provider, status, agent_id |
| `messages` | Messages within conversations | role, content, conversation_id |
| `responses` | LLM responses | content, reasoning_content, usage (JSON), latency_seconds |
| `stream_chunks` | Streaming response chunks | chunk_index, content, is_thinking, is_complete |
| `extraction_sessions` | Multi-step extraction sessions | plan_id, status |
| `extraction_session_steps` | Steps within sessions | step_id, agent_id, status |
| `agent_messages` | Inter-agent messages (persistent) | sender, recipient, content, message_type |
| `agent_tasks` | Task execution history | task_id, agent_id, status, execution_time |
| `agent_states` | Agent runtime state | agent_id, state_data (JSON) |
| `agent_working_memory` | Compressed working memory per named agent | agent_id, summary, metadata |
| `plan_checkpoints` | Plan execution checkpoints | session_id, plan_id, status, checkpoint_data (JSON) |

---

## AgentMessage

```python
from gptase.memory.models import AgentMessage

message = AgentMessage(
    sender: str,
    recipient: str,
    content: Any,
    message_type: str = "message",
    metadata: Dict = {},
)
# Fields set automatically: id (UUID), timestamp (datetime)
```

---

## ConversationStorage (low-level)

Direct SQLite access, used internally by `MemoryManager`:

```python
from gptase.memory.storage import ConversationStorage

storage = ConversationStorage(db_path="data/conversations.db", enabled=True)
await storage.initialize()

# Conversations
conv_id = await storage.start_conversation(model_name, provider, config, agent_id)
await storage.add_messages(conv_id, messages)
await storage.add_response(conv_id, response_content, reasoning_content, usage, latency_seconds)
await storage.complete_conversation(conv_id, status, error_message=None)

# Streaming
response_id = await storage.add_response(conv_id, "", "", None, 0, metadata={"streaming": True})
await storage.add_stream_chunk(response_id, chunk_index, content, reasoning_content, is_thinking, is_complete)
await storage.update_response(response_id, response_content, reasoning_content, usage, latency_seconds)

# Queries
conversations = await storage.list_conversations(limit=50)
await storage.close()
```

---

*Related: [Model API →](./model.md) | [Config API →](./config.md)*
