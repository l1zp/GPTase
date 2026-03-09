# Memory API

> [首页](../README.md) → [API](.) → Memory

**文件：** `gptase/memory/manager.py`、`gptase/memory/storage.py`

---

## MemoryManager

所有 Agent 内存操作的高层接口。底层由 `ConversationStorage`（SQLite）支持。

```python
from gptase.memory.manager import MemoryManager

memory = MemoryManager(
    storage: Optional[ConversationStorage] = None,  # 为 None 时自动创建
    config: Optional[Any] = None,                   # MemoryConfig 或字典
)

await memory.initialize()
await memory.close()   # 程序退出前必须调用
```

### 对话历史

```python
history = await memory.get_conversation_history(
    agent_id: Optional[str] = None,
    limit: int = 50,
    since: Optional[datetime] = None,
) -> List[AgentMessage]

await memory.store_message(message: AgentMessage) -> str   # 返回消息 ID
```

### 任务结果

```python
task_id = await memory.store_task_result(
    task_id: str,
    agent_id: str,
    result: Any,                        # 非字符串时自动序列化为 JSON
    status: str = "completed",
    error: Optional[str] = None,
    execution_time: Optional[float] = None,
    tools_used: Optional[List[str]] = None,
) -> str

tasks = await memory.get_task_history(
    agent_id: Optional[str] = None,
    limit: int = 20,
) -> List[AgentTask]
```

### Agent 状态

```python
await memory.store_agent_state(agent_state) -> str
# 接受字典或任何含 agent_id 属性的 Pydantic 模型。

state = await memory.get_agent_state(agent_id: str) -> Optional[Dict]
```

### Agent 间消息传递

```python
from gptase.memory.models import AgentMessage

# 发送到目标 Agent 的队列（同时持久化到 SQLite）
await memory.send_message(recipient: str, message: AgentMessage)

# 从队列接收（阻塞，带可选超时）
msg = await memory.get_next_message(
    agent_id: str,
    timeout: Optional[float] = None,  # 秒；None = 永久阻塞
) -> Optional[AgentMessage]
```

### 统计与摘要

```python
usage = await memory.get_usage() -> Dict  # has_conversations, has_tasks, storage_type

summary = await memory.create_memory_summary(
    agent_id: Optional[str] = None,   # None = 全局摘要
) -> Dict  # conversation_count, task_count, recent_conversations, recent_tasks
```

---

## SQLite 数据表

所有数据存储在单个 SQLite 数据库中（默认：`data/conversations.db`）。

| 表名 | 用途 | 关键列 |
|---|---|---|
| `conversations` | LLM 交互记录 | model, provider, status, agent_id |
| `messages` | 对话内的单条消息 | role, content, conversation_id |
| `responses` | LLM 响应 | content, reasoning_content, usage (JSON), latency_seconds |
| `stream_chunks` | 流式响应数据块 | chunk_index, content, is_thinking, is_complete |
| `extraction_sessions` | 多步骤提取会话 | plan_id, status |
| `extraction_session_steps` | 会话内的单个步骤 | step_id, agent_id, status |
| `agent_messages` | Agent 间消息（持久化队列） | sender, recipient, content, message_type |
| `agent_tasks` | 任务执行历史 | task_id, agent_id, status, execution_time |
| `agent_states` | Agent 运行时状态 | agent_id, state_data (JSON) |
| `sop_checkpoints` | SOP 执行断点 | session_id, plan_id, status, checkpoint_data (JSON) |

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
# 自动设置字段：id（UUID）、timestamp（datetime）
```

---

## ConversationStorage（底层）

直接的 SQLite 访问接口，由 `MemoryManager` 内部使用：

```python
from gptase.memory.storage import ConversationStorage

storage = ConversationStorage(db_path="data/conversations.db", enabled=True)
await storage.initialize()

# 对话管理
conv_id = await storage.start_conversation(model_name, provider, config, agent_id)
await storage.add_messages(conv_id, messages)
await storage.add_response(conv_id, response_content, reasoning_content, usage, latency_seconds)
await storage.complete_conversation(conv_id, status, error_message=None)

# 流式追踪
response_id = await storage.add_response(conv_id, "", "", None, 0, metadata={"streaming": True})
await storage.add_stream_chunk(response_id, chunk_index, content, reasoning_content, is_thinking, is_complete)
await storage.update_response(response_id, response_content, reasoning_content, usage, latency_seconds)

# 查询
conversations = await storage.list_conversations(limit=50)
await storage.close()
```

---

*相关：[Model API →](./model.md) | [Config API →](./config.md)*
