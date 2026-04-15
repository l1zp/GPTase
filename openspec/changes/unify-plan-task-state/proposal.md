## Why

GPTase currently records Plan runtime state through three parallel views: `task_results`, `task_traces`, and `active_tasks`. This makes the checkpoint model harder to understand and maintain, because one task's state must be reconstructed by joining multiple structures that represent the same execution lifecycle.

## What Changes

- Replace the split Plan runtime recording model with a single `tasks` state container keyed by `task_id`.
- Store each task's latest runtime state, terminal output, terminal trace, resumable runtime snapshot, and attempt summaries in one place.
- Update Plan checkpoint persistence, status APIs, and `execute_plan()` results to expose the same unified `tasks` structure.
- Keep raw LLM conversation tracking separate from Plan runtime state.
- **BREAKING**: Remove the old Plan fields `task_results`, `task_traces`, and `active_tasks` from Plan runtime/status payloads in favor of the new unified `tasks` structure.

## Capabilities

### New Capabilities
- `plan-task-runtime-state`: Defines the unified per-task runtime state model for Plan execution, checkpointing, and status reporting.

### Modified Capabilities

## Impact

- Affected code: `gptase/agents/execution_types.py`, `gptase/agents/planner.py`, `gptase/core/orchestrator.py`, and any consumers of Plan session/status payloads
- Affected APIs: Plan execution results and Plan session status payloads
- Affected tests: planner, orchestrator, and session-status coverage that currently assert `task_results`, `task_traces`, or `active_tasks`
- Documentation impact: Plan execution flow and storage docs must be updated to describe unified `tasks` state
