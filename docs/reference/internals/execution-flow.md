# Execution Flow

> [Home](../README.md) → [Internals](./) → Execution Flow

**Files:** `gptase/agents/base.py`, `gptase/agents/planner.py`

---

## Single-Agent Execution (Direct Mode)

Standard ReAct loop for individual tasks.

## Plan Execution Flow

The `PlanManager` handles complex multi-agent workflows using a DAG-based dependency system.

```
plan_manager.execute_plan(plan, input_data, ...)
  │
  ├─ Restore/Create ExecutionContext
  ├─ While plan not complete:
  │    ├─ next_tasks = plan.get_next_tasks()
  │    ├─ Filter by max_parallel
  │    ├─ For each task:
  │    │    └─ _execute_single_task(task, ...)
  │    │         ├─ resolve inputs via TaskDispatcher
  │    │         ├─ dispatcher.dispatch(task) -> TaskResult
  │    │         └─ if failed: failure_handler.decide()
  │    └─ asyncio.gather(execution_coros)
  │
  └─ Return final result dict
```

### Checkpointing

States are saved to SQLite after every task completion and at major status changes (start, end, failure).

1. **Session ID**: Generated as `plan_YYYYMMDD_HHMMSS_<hex>`.
2. **Resumption**: Calling `execute_plan` with an existing `session_id` restores the `ExecutionContext` and skips `COMPLETED` tasks.
