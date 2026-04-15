# Memory 与 Session 存储

这是一份面向开发者的说明文档，用来描述 GPTase 当前如何存储对话轨迹、
direct session 和 plan checkpoint。

本文描述的是代码库当前的真实实现，粒度比 API 参考文档更低。

## 范围

本文覆盖：

- 物理存储位置
- 涉及的 SQLite 表
- LLM tracking、direct session、plan checkpoint 的区别
- 每一层对应的读写代码路径
- Web/API 目前只暴露了哪一部分存储状态

本文不覆盖：

- `data/output/...` 下的工作目录产物
- 各个 plan 自己定义的业务输出 schema

## 一个数据库，多个逻辑层

GPTase 当前默认使用单个 SQLite 数据库：

```text
data/conversations.db
```

数据库连接与 schema 位于：

- `gptase/memory/database.py`
- `gptase/memory/schema.sql`

高层结构如下：

```text
data/conversations.db
  |
  +-- LLM tracking 表
  |     conversations
  |     messages
  |     responses
  |     stream_chunks
  |     model_parameters
  |
  +-- workflow / extraction 表
  |     extraction_sessions
  |     extraction_session_steps
  |     extraction_results
  |
  +-- memory / messaging 表
  |     agent_messages
  |     agent_tasks
  |     agent_states
  |
  +-- plan checkpoint 表
        plan_checkpoints
```

关键点是：GPTase 当前并不是“每个 session 一个文件”的组织方式，而是把多种
JSON 形态的数据存进 SQLite 行里。

## 第 1 层：原始 LLM 对话追踪

这是最低层的轨迹记录，用来保存模型调用及其输入输出。

相关数据表：

- `conversations`
- `messages`
- `responses`
- `stream_chunks`
- `model_parameters`

主要代码路径：

- `gptase/models/model.py`
- `gptase/memory/storage.py`

典型写入流程：

```text
Model.generate() / generate_stream()
  -> ConversationStorage.start_conversation()
  -> ConversationStorage.add_messages()
  -> ConversationStorage.add_response()
  -> ConversationStorage.add_stream_chunk()   # 仅 streaming
  -> ConversationStorage.complete_conversation()
```

这一层的用途：

- 审计模型请求/响应
- 调试模型调用过程
- 重建消息输入与最终输出
- 在原始 response chunk 粒度上回放流式输出

这一层不等于：

- 用户可见的 chat session
- 可恢复的 plan session

一个 direct session 或一个 plan step 可以对应这里的一次或多次 LLM 记录。

## 第 2 层：Direct Session

Direct session 是 Web UI 和 `/api/chat` 返回的那种 chat 风格会话。

运行时模型定义在：

- `gptase/agents/types.py` 中的 `DirectSession`

字段包括：

- `session_id`
- `session_type`
- `title`
- `status`
- `agent_id`
- `messages`
- `traces`
- `metadata`
- `created_at`
- `updated_at`

### Direct session 存在哪里

Direct session 会序列化为 JSON，然后存进 `agent_states`：

```text
agent_states.agent_id   = chat_session:<session_id>
agent_states.state_data = { ... DirectSession JSON ... }
```

或者：

```text
agent_states.agent_id   = agent_session:<session_id>
agent_states.state_data = { ... DirectSession JSON ... }
```

对应的 orchestrator 方法在 `gptase/core/orchestrator.py`：

- `_generate_direct_session_id()`
- `_direct_session_state_key()`
- `_save_direct_session()`
- `_load_direct_session()`
- `_load_any_direct_session()`
- `list_sessions()`
- `get_session_status()`

### Direct session 里的 message 和 trace 如何组织

每个 direct session 内部会存：

- `messages`: 面向 UI 的消息线程
- `traces`: 从 runtime 输出里提炼出来的执行轨迹项

它们不是分表追加写入，而是整个 `DirectSession` 对象每次一起重写进
`agent_states.state_data`。

也就是说当前 direct session 的存储模型是：

```text
只保留最新快照
```

而不是：

```text
完整的 append-only 事件流
```

### 这意味着什么

优点：

- 读写路径简单
- 很容易直接返回给 Web API
- 和 UI 会话状态一一对应

代价：

- 没有单独的 direct session 事件日志
- 不能对这类 UI session 做逐消息行级查询
- 改动一条消息时，实际上会重写整个 session 快照

## 第 3 层：Plan Checkpoint

Plan 执行使用的是另一套存储模型，不同于 direct session。

运行时上下文定义在：

- `gptase/agents/execution_types.py`

重要类型：

- `ExecutionContext`
- `TaskExecutionResult`
- `PlanCheckpoint`

### Plan checkpoint 存在哪里

Plan checkpoint 保存在 `plan_checkpoints` 表里。

关键列：

- `session_id`
- `plan_id`
- `status`
- `total_steps`
- `completed_steps`
- `checkpoint_data`

其中 `checkpoint_data` 是最新 checkpoint 的 JSON 快照。

主要代码路径：

- `gptase/agents/planner.py`

相关方法：

- `_save_checkpoint_to_db()`
- `_load_checkpoint_from_db()`
- `list_sessions()`
- `get_session_status()`
- `execute_plan()`

### checkpoint_data 里有什么

checkpoint 快照通常包含：

- `plan_id`
- `session_id`
- `input_data`
- `document_path`
- `tasks`
- `variables`
- `workspace_dir`
- 进度信息，如总任务数 / 已完成任务数

其中 `tasks[task_id]` 会统一保存：

- 最新生命周期 `status`
- 终态 `output`
- 终态 `trace`
- 运行中的 `resume_state`
- 轻量的 `attempts` 摘要

这就是 plan 能够 resume 的基础。

### Direct session 和 plan checkpoint 的区别

这两者很容易混淆，但实际上是两套东西：

```text
Direct session
  -> 存在 agent_states
  -> 用于 chat / worker session API
  -> 里面是 messages + traces

Plan checkpoint
  -> 存在 plan_checkpoints
  -> 用于 plan resume / status 逻辑
  -> 里面是统一的每任务运行态
```

当前 Web API 只直接暴露前者。

## Web/API 视角下能看到什么

Web API 并不会对所有存储层做对称暴露。

相关文件：

- `gptase/web/server.py`

当前行为：

- `GET /api/sessions` 只返回 recent direct sessions
- `GET /api/sessions/{session_id}` 只返回 direct session 状态
- 对于 plan session ID，这个 direct session 状态接口返回 `null`
- plan 的状态查询和 resume 走的是 plan checkpoint 路径

所以外部看到的 session 模型，比内部存储模型要窄：

```text
内部存储：
  direct sessions + checkpoints + raw conversations

Web session API：
  direct sessions only
```

## 当前存储模式总结

代码库现在混用了两种持久化风格：

1. 关系表行存储
   例如：
   - `conversations`
   - `messages`
   - `responses`
   - `stream_chunks`

2. SQLite 行内 JSON 快照存储
   例如：
   - `agent_states.state_data`
   - `plan_checkpoints.checkpoint_data`

这意味着 GPTase 其实已经有结构化的 JSON session 状态，只是这些 JSON 目前
嵌在 SQLite 里，而不是单独写成 session 文件。

## 实际排查时怎么找

如果你要看用户可见的 chat / agent session：

- 查 `agent_states`
- 找 `chat_session:` 或 `agent_session:` 前缀
- 反序列化 `state_data`

如果你要看可恢复的 plan 运行状态：

- 查 `plan_checkpoints`
- 按 `session_id` 找行
- 反序列化 `checkpoint_data`

如果你要看原始模型调用轨迹：

- 看 `conversations`、`messages`、`responses`、`stream_chunks`

## 代码地图

存储和 schema：

- `gptase/memory/schema.sql`
- `gptase/memory/database.py`
- `gptase/memory/storage.py`

高层 memory 接口：

- `gptase/memory/manager.py`

Direct session：

- `gptase/agents/types.py`
- `gptase/core/orchestrator.py`

Plan checkpoint：

- `gptase/agents/execution_types.py`
- `gptase/agents/planner.py`

Web 暴露层：

- `gptase/web/server.py`

## 当前设计的空白与约束

当前值得记住的约束：

- direct session 是快照式存储，不是事件流式存储
- plan checkpoint 保存的是“最新可恢复状态”，不是按 task turn 追加的完整历史
- 原始 LLM tracking 和用户可见 session 状态有关联，但没有统一成一个共享 session artifact
- 当前没有类似 transcript 系统那样的 per-session 文件树

如果以后要演进到下面这些方向，这些约束都很重要：

- per-session JSON artifact
- append-only event log
- session export/import
- 基于文件的 resume
