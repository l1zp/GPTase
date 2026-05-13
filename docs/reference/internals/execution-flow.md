# Execution Flow

> [Home](../README.md) → [Internals](./) → Execution flow

**Related files:** `gptase/core/orchestrator.py`, `gptase/agents/base.py`, `gptase/agents/runtime.py`, `gptase/agents/plan_prompt.py`, `gptase/tools/handlers.py`

---

## Two execution modes

`dispatch` routes to one of two paths based on its arguments:

```
dispatch(task)
  │
  ├─ task has agent_id (not orchestrator) → Agent mode
  │   └─> _execute_agent()
  │
  └─ default → Coordinator mode
      └─> _execute_coordinator()
```

When `dispatch` receives `plan_id` / `plan_path`, the CLI layer
(`gptase chat -p`) first expands the YAML via
`expand_plan_to_prompt` into a structured to-do string used as the
seed user prompt for Coordinator mode.

## Agent mode

Standard ReAct loop for a single agent.

```
agent.process_task(task)
  └─> agent.run(prompt)
        ├─ claude-* model → _run_with_sdk()
        └─ other model    → _run_with_llm() → AgentRuntime.run()
```

## Coordinator mode

The orchestrator runtime calls `self.run` in an outer loop; each
returned trace decides continue / terminate. Capped at
`_MAX_COORDINATOR_TURNS`.

```
_execute_coordinator(task_id, task)
  │
  ├─ for turn in range(_MAX_COORDINATOR_TURNS):
  │     result = self.run(prompt)
  │     runtime = _runtime_trace(result)
  │     │
  │     ├─ stop_reason == "final_answer" → return result (terminal even with delegations)
  │     ├─ no coordinator activity → return error
  │     └─ has delegation → build followup prompt → continue
  │
  └─ exceeds cap → return failure
```

The Coordinator delegates via the `DelegateTask` tool. The runtime
detects delegation by parsing `coordinator_summary` from the tool
result.

## DelegateTask + artifact-based communication

Each `DelegateTask` invocation:

1. Resolves the target worker (agent_id must be registered in the orchestrator)
2. Builds a `Task` (carrying `task_inputs` so worker hooks can read structured fields) and calls `agent.process_task` → `agent.run`
3. Inside `Agent.run`, an optional sibling `hooks.py` may short-circuit the LLM by returning a result dict from `pre_run` (this is how the `enzyme-variant-normalizer` works: its hook parses the JSON inputs, expands upstream artifact paths, and calls `normalize_variant_payload` directly)
4. Otherwise the LLM path runs (`_run_with_sdk` for Claude, `_run_with_llm` for everything else)
5. Write the full worker output to `<workspace>/worker_results/NNN_<agent>.json`
6. Return a compact ref `{output_path, content_chars, content_preview}` to the Coordinator

Downstream steps reference upstream results by passing these
`output_path` strings, so the Coordinator's context never carries
full worker payloads. This artifact-based comms model was introduced
in Slice 1.18 and is the key reason the outer prompt stays bounded
across multi-step pipelines.

## Role of plan templates

`config/plans/*.yaml` files are plan **templates**, not execution
schedules. `gptase chat -p <plan_id>` expands the template into a
prompt at session start:

- Sequential steps → "Step N — DelegateTask(agent_id=..., ...)"
- `replicas: N` → "Issue N parallel DelegateTask calls in ONE assistant message"
- `parallel_with: [other_id]` → siblings rendered in the same group
- `optional: true` → "IF condition X, SKIP"
- Deterministic agents → "task_inputs paths are auto-loaded"

The Coordinator then schedules autonomously from those instructions.
There is no PlanManager executor, no DAG resolver, and no checkpoint
mechanism in the live runtime.
