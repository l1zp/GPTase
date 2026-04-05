# Execution Flow

> [Home](../README.md) → [Internals](./) → Execution Flow

**Files:** `gptase/core/orchestrator.py`, `gptase/agents/base.py`, `gptase/agents/planner.py`

---

## Three Execution Modes

`dispatch` routes to one of three paths based on task parameters:

```
dispatch(task)
  │
  ├─ task has plan/plan_id/plan_path → Plan mode
  │   └─> _execute_plan()
  │
  ├─ task has agent_id (not orchestrator) → Agent mode
  │   └─> _execute_agent()
  │
  └─ default → Coordinator mode
      └─> _execute_coordinator()
```

## Agent Mode

Standard ReAct loop for a single agent.

```
agent.process_task(task)
  └─> agent.run(prompt)
        ├─ claude-* model → _run_with_sdk()
        └─ other model    → _run_with_llm() → AgentRuntime.run()
```

## Coordinator Mode

Orchestrator agent loop, up to `_MAX_COORDINATOR_TURNS` (3) iterations.

```
_execute_coordinator(task_id, task)
  │
  ├─ for turn in range(3):
  │     result = self.run(prompt)
  │     runtime = _runtime_trace(result)
  │     │
  │     ├─ needs_plan → _execute_plan()
  │     ├─ final_answer, no delegation → return result
  │     ├─ no coordinator activity → return error
  │     └─ has delegation → merge coordinator summary → build followup → continue
  │
  └─ max turns exceeded → return failed
```

Coordinator delegates to worker agents via DelegateTask tool calls.
Runtime detects delegation by parsing coordinator_summary from tool results.

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
