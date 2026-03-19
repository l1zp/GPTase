# Dispatcher Internals

> [Home](../README.md) → [Internals](./) → Dispatcher

**File:** `gptase/agents/plan_dispatcher.py`

---

## TaskDispatcher

`TaskDispatcher` bridges the `PlanManager` and individual agents. It is instantiated by the `PlanManager`.

```python
from gptase.agents.plan_dispatcher import TaskDispatcher

dispatcher = TaskDispatcher(
    memory_manager=memory_manager,
    model=model,
)
```

### Agent Caching

Agents are created on demand and cached:

```python
async def _get_agent(agent_id: str) -> Agent:
    if agent_id in self._agents:
        return self._agents[agent_id]   # reuse
    agent = Agent.from_markdown(agent_id, ...)
    self._agents[agent_id] = agent
    return agent
```

---

## `dispatch()` Step-by-Step

```
dispatch(task, context)
  │
  ├─ 1. _get_agent(task.agent_id or self.agent.agent_id)
  │
  ├─ 2. Set agent.workspace_dir = context.workspace_dir
  │
  ├─ 3. Resolve inputs via _resolve_inputs()
  │
  ├─ 4. agent.run(**resolved_inputs) -> TaskResult
  │
  └─ 5. _post_process_result(task, task_result)
```

---

## Template Variable Resolution

| Pattern | Resolves to |
|---|---|
| `{{taskN}}` | Full result from task `N` |
| `{{taskN.field}}` | Nested field from task `N` result |

### JSON Auto-parsing

If a task result's `content` contains a JSON block, the dispatcher automatically parses it to resolve nested fields like `{{task1.my_key}}`.

---

## Parallel Dispatch

`dispatch_parallel(tasks, context, max_concurrent=5)` use `asyncio.Semaphore` to bound concurrency.
