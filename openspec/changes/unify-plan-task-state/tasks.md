## 1. Unify Plan Runtime Types

- [x] 1.1 Introduce a single per-task runtime state model in `gptase/agents/execution_types.py`
- [x] 1.2 Replace split `task_results` and `active_tasks` storage in `ExecutionContext` with a unified `tasks` container
- [x] 1.3 Define lightweight per-attempt summaries for retries/failures without adding full event-history persistence

## 2. Refactor Planner and Checkpoint Flow

- [x] 2.1 Update `PlanManager.execute_plan()` and task execution paths to write task lifecycle state into `tasks[task_id]`
- [x] 2.2 Refactor checkpoint save/load and session status logic to persist and restore unified `tasks` state
- [x] 2.3 Update resume handling so in-progress interactive runtime snapshots live in `tasks[task_id].resume_state`
- [x] 2.4 Update dependency/output resolution so downstream tasks read prior output from `tasks[task_id].output`

## 3. Replace Public Plan Payloads

- [x] 3.1 Update Plan execution result payloads to expose only `tasks` instead of `task_results`, `task_traces`, and `active_tasks`
- [x] 3.2 Update Plan session status payloads to expose only `tasks` and recomputed progress/active-agent summaries
- [x] 3.3 Remove tests and code paths that still assert the old split Plan fields

## 4. Validate and Document the New Model

- [x] 4.1 Update Plan/session storage documentation to describe the unified `tasks` runtime model
- [x] 4.2 Add or rewrite tests for completed tasks, resumable in-progress tasks, retries, and dependency resolution under the new shape
- [x] 4.3 Run targeted planner, orchestrator, and Plan session-status tests to confirm the new model works end to end
