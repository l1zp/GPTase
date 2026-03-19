# 调度器内部原理 (Dispatcher Internals)

> [首页](../README.md) → [内部原理](./) → 调度器

**相关文件：** `gptase/agents/plan_dispatcher.py`

---

## TaskDispatcher

`TaskDispatcher` 是 `PlanManager` 与各个智能体之间的桥梁。它由 `PlanManager` 实例化。

```python
from gptase.agents.plan_dispatcher import TaskDispatcher

dispatcher = TaskDispatcher(
    memory_manager=memory_manager,
    model=model,
)
```

### 智能体缓存

智能体按需创建并缓存：

```python
async def _get_agent(agent_id: str) -> Agent:
    if agent_id in self._agents:
        return self._agents[agent_id]   # 复用
    agent = Agent.from_markdown(agent_id, ...)
    self._agents[agent_id] = agent
    return agent
```

---

## `dispatch()` 步骤详解

```
dispatch(task, context)
  │
  ├─ 1. _get_agent(task.agent_id or self.agent.agent_id)
  │
  ├─ 2. 设置 agent.workspace_dir = context.workspace_dir
  │
  ├─ 3. 通过 _resolve_inputs() 解析输入变量
  │
  ├─ 4. agent.run(**resolved_inputs) -> TaskResult
  │
  └─ 5. _post_process_result(task, task_result)
```

---

## 模板变量解析

| 模式 | 解析为 |
|---|---|
| `{{taskN}}` | 任务 `N` 的完整结果 |
| `{{taskN.field}}` | 任务 `N` 结果中的嵌套字段 |

### JSON 自动解析

如果任务结果的 `content` 包含 JSON 块，调度器会自动解析它以支持类似 `{{task1.my_key}}` 的嵌套字段引用。

---

## 并行调度

`dispatch_parallel(tasks, context, max_concurrent=5)` 使用 `asyncio.Semaphore` 限制并发数。
