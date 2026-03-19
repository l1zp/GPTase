# 类型参考 (Type Reference)

> [首页](../README.md) → [内部原理](./) → 类型

**相关文件：** `gptase/agents/types.py`, `gptase/agents/execution_types.py`

---

## 核心计划类型 (Core Plan Types)

### `Plan`
代表任务有向无环图 (DAG) 的顶层执行单元。
- `plan_id`: 唯一标识符。
- `goal`: 自然语言描述的目标。
- `tasks`: `PlannedTask` 对象列表。
- `max_parallel`: 最大并行任务数。

### `PlannedTask`
执行图中的单个节点。
- `task_id`: 唯一标识符（例如 "1", "2a"）。
- `agent_id`: 执行该任务的目标智能体。
- `dependencies`: 在此任务开始前必须完成的 `task_id` 列表。
- `inputs`: 模板解析后的参数。

### `TaskStatus`
- `PENDING` (等待中), `IN_PROGRESS` (执行中), `COMPLETED` (已完成), `FAILED` (失败), `SKIPPED` (已跳过)。

---

## 执行状态类型 (Execution Types)

### `ExecutionContext`
运行计划会话的状态容器。
- `session_id`: 持久化会话标识。
- `task_results`: 已完成任务的结果映射。
- `input_data`: 初始输入参数。

### `TaskResult`
智能体执行的产出。
- `status`: "success" (成功) 或 "failed" (失败)。
- `data`: 输出字典。
- `error`: 失败时的错误消息。
