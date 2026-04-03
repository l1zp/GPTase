# Runtime Input Assembly: align with Claude Code-style layered prompt assembly

## Summary
目标不是把 `tools + memory + context` 粗暴拼成一个大 user prompt，而是引入一个分层输入装配器，像 `claude-code` 一样区分：

1. 稳定系统层：`system_prompt` + 低频变化的 runtime addendum
2. 会话消息层：真实的多轮 `messages`
3. 动态上下文层：working memory、session context addendum、后续可扩展 attachments
4. 工具层：可执行 `tools schema`

本次 direct chat / direct agent session 的实现目标：
- `tools` 继续走 schema，但同步生成一段简短的 capability summary
- `memory` 不再直接糊到 task 前缀，而是作为独立注入段
- `context` 优先保留为原生会话消息回放，不先转成 transcript 文本
- 为长会话加入显式预算、裁剪和压缩边界，避免输入无限膨胀

## Key Changes

### 1. 引入统一输入装配器
- 新增 `gptase/agents/runtime_input.py`，负责生成一次模型调用的完整输入蓝图，而不是只返回一段字符串。
- 装配器输出建议包含：
  - `system_prompt: str`
  - `messages: List[Dict[str, Any]]`
  - `tools: Optional[List[Dict[str, Any]]]`
  - `sections: Dict[str, str]`
  - `char_budget_report: Dict[str, Any]`
- 该模块只负责装配、裁剪、去重，不执行模型调用。

### 2. 重新定义三部分落点
- `tools`
  - 继续通过 `Model.generate(..., tools=tool_schemas)` 传入。
  - 同时生成一个稳定的 `Tools Summary`，放到 system addendum，而不是 user message。
  - `Tools Summary` 只包含当前 agent 可用工具的名称和一句话描述，不展开 schema 细节。

- `memory`
  - `Agent Working Memory` 作为单独的 context block 注入到消息层之前，默认以一条 `system` 或 `developer-style` 内部消息形式加入；在当前实现里可先用 `system` 消息。
  - 不再通过 `inject_memory_context(task)` 把 memory 拼成 `Current Task` 前缀。
  - memory 注入前先做去重：如果 memory 文本与最近会话上下文高度重复，则裁掉重复段。

- `context`
  - direct session 的历史优先保留为原生 `messages` 回放，而不是渲染为 `Session Context:` 大段文本。
  - 只有在非 session 调用，或需要压缩历史时，才降级生成文本版 `Session Context Summary`。
  - 当前轮 user 输入仍单独作为最后一条 user message，绝不混进历史摘要里。

### 3. direct session 改为真实多轮消息输入
- `AgentOrchestrator.execute_direct_session()` 和 `stream_direct_session()` 在调用 agent 时，传入当前 `DirectSession`。
- `Agent.run()` / `run_stream()` 增加内部参数，例如 `_session: Optional[DirectSession] = None`。
- 当 `_session` 存在时，构造 messages 顺序固定为：
  - 顶部 `system_prompt`
  - 可选 `system` memory message
  - 可选 `system` runtime/context addendum
  - 历史 session messages，按时间正序回放，但不包含当前轮刚追加的 user message副本
  - 当前轮 user message
- `SessionMessage.role` 到 OpenAI message role 的映射要固定：
  - `user -> user`
  - `agent -> assistant`
  - `system -> system`
- 如果历史消息中存在 tool trace 或运行日志，只保留面向对话的消息，不把 trace 混入 conversation messages。

### 4. system prompt 采用“稳定前缀 + 动态尾部”结构
- 保持 agent markdown 里的 `system_prompt` 作为主干。
- 新增 runtime system addendum，顺序固定为：
  - environment summary
  - tools summary
  - optional capability notes
  - optional session-mode notes
- 把稳定、低变化内容放前面，动态内容放后面，便于后续做 prompt caching。
- 不把 session 历史、memory、当前 task 塞进 system prompt。

### 5. 引入 token/char budget 与压缩边界
- 新增 `RuntimeInputConfig`，建议挂到 `FrameworkConfig.runtime_input`：
  - `include_tools_summary: true`
  - `include_working_memory: true`
  - `include_session_history: true`
  - `max_total_input_chars: 32000`
  - `max_session_history_chars: 24000`
  - `max_memory_chars: 1200`
  - `max_tools_summary_chars: 1500`
  - `history_trim_strategy: "drop_oldest"`
  - `history_compaction_strategy: "summary_boundary"`
  - `dedupe_memory_against_history: true`
- 超长时裁剪顺序固定：
  1. 先裁最旧的 session history
  2. 再裁 memory
  3. 最后裁 tools summary
  4. 当前轮 user message 和 system prompt 不裁
- 当 session history 超过上限时，不做“硬全量回放”，而是插入一条压缩边界消息，例如：
  - `Earlier conversation summary: ...`
  - 然后只保留边界之后的原始消息
- 这对应 `claude-code` 的 compaction boundary 思路，避免长会话无限增长。

### 6. 为后续 attachments 预留接口
- 装配器结构预留 `attachments` 字段，但本次先不引入完整 attachment 系统。
- working memory、document context、retrieval context 未来都可挂到这个扩展点，而不是继续扩散到 prompt 拼接逻辑。
- 这样后续如果要做：
  - document snippets
  - relevant memory retrieval
  - compacted tool-result references
  都能接到同一入口。

## Public Interfaces / Types
- `FrameworkConfig` 增加：
  - `runtime_input: RuntimeInputConfig`
- `Agent.run()` / `run_stream()` 增加内部参数：
  - `_session: Optional[DirectSession] = None`
- 新增：
  - `RuntimeInputConfig`
  - `RuntimeInputBundle`
  - `SessionHistoryCompactionResult`
- `AgentMemoryService` 调整为返回结构化 memory block，而不只是裸字符串，便于去重和预算统计。

## Test Plan
- direct session 第二轮调用时，模型收到上一轮 `user/assistant` 原生消息，而不是一整段 transcript 文本。
- 当前轮 user 输入只出现一次，始终是最后一条 user message。
- tools 启用时：
  - `Model.generate(..., tools=...)` 仍收到真实 schema
  - system addendum 同时包含 `Tools Summary`
- memory 存在时，作为独立注入消息出现，不再嵌进 `Current Task`。
- multimodal 调用时：
  - 非 session 模式下仍能得到统一装配后的 user content
  - 如果后续允许 multimodal session，文本说明必须仍是首个 text item
- 历史过长时，最旧消息被裁掉，并插入 summary boundary；当前轮消息和最近消息保留。
- history 与 memory 有重复内容时，memory 会被去重或缩短，不重复占用预算。
- `run()` 与 `run_stream()` 使用相同的输入装配器，避免行为分叉。

## Assumptions
- 本次只改 direct chat / direct agent session，不改 Plan 执行链路。
- `tools + memory + context` 的含义保留，但不要求三者都落在同一个 user prompt 文本里。
- “参考 claude-code 优化”优先体现在分层、预算、压缩边界、去重和缓存友好的结构，而不是逐字模仿其 attachment 体系。
- 现阶段先用字符预算实现，后续如需更精确，可替换为 token 预算估算器。
