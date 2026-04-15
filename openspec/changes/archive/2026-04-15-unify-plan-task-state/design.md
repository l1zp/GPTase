## Context

Plan runtime state is currently represented through multiple overlapping structures:

- `task_results` for terminal outputs
- `task_traces` for terminal execution traces
- `active_tasks` for in-progress resumable task state

These structures are derived from the same underlying task lifecycle, but they are stored and exposed separately. That makes checkpoint persistence, resume logic, and status inspection harder to reason about, because one task's state is spread across multiple maps with partially overlapping fields.

The simplification goal is to converge on a single runtime state model per task while preserving:

- resumable interactive runtime support
- task output access for downstream template resolution
- enough retry/attempt history for debugging
- aggregate Plan progress reporting

## Goals / Non-Goals

**Goals:**
- Define one canonical per-task runtime state container named `tasks`
- Use the same `tasks` structure internally and in public Plan runtime/status payloads
- Preserve resume support through a per-task `resume_state`
- Preserve minimal attempt history without introducing a full event log
- Remove old public fields `task_results`, `task_traces`, and `active_tasks`

**Non-Goals:**
- Redesigning direct session storage
- Merging Plan runtime state with raw LLM conversation tracking
- Introducing append-only per-turn history persistence
- Preserving backward-compatible aliases for the removed Plan fields

## Decisions

### 1. Use `tasks` as the canonical runtime container

The unified runtime map will be named `tasks`, keyed by `task_id`. This matches existing `Task` terminology in the Plan model and avoids introducing a second concept such as `steps`.

Alternative considered:
- `steps`
  Rejected because the codebase already uses `Task` consistently.
- `task_state`
  Rejected because it is more precise but less natural as the primary top-level runtime field.

### 2. Store one latest snapshot per task, plus lightweight attempt summaries

Each `tasks[task_id]` record will store:

- latest lifecycle state
- latest terminal `output`
- latest terminal `trace`
- latest resumable `resume_state` while in progress
- lightweight `attempts` summaries

This keeps the model simple while preserving retry visibility.

Alternative considered:
- Full append-only per-attempt/per-turn history
  Rejected because it would add storage and API complexity without being necessary for the current simplification goal.
- Latest snapshot only with no attempt history
  Rejected because retry/failure debugging would become too lossy.

### 3. Replace old Plan runtime/status fields directly

The new `tasks` structure will replace:

- `task_results`
- `task_traces`
- `active_tasks`

No compatibility aliases will be returned in API or runtime payloads.

Alternative considered:
- Short-term dual-write or compatibility aliases
  Rejected because it would preserve the old mental model and prolong the complexity we are trying to remove.

### 4. Keep SQL aggregate columns for listing, but treat `checkpoint_data.tasks` as detailed truth

The relational columns in `plan_checkpoints` such as `status`, `total_steps`, and `completed_steps` remain useful for lightweight list queries. Detailed per-task runtime state will live only in `checkpoint_data.tasks`.

Alternative considered:
- Remove aggregate SQL fields and compute everything from JSON on reads
  Rejected because list/status queries would become heavier for no real design gain.

## Risks / Trade-offs

- [Breaking existing Plan API consumers] -> Make the spec explicit about the breaking field replacement and update docs/tests together with code.
- [Template/input resolution regressions] -> Define `tasks[task_id].output` as the only downstream task-output source and update resolution code in one pass.
- [Resume regressions for in-progress interactive tasks] -> Keep `resume_state` as a direct home for the current `InteractiveRuntimeSnapshot` and add targeted resume tests.
- [Losing useful retry diagnostics] -> Preserve per-attempt summaries with status, error, timestamps, and execution time.

## Migration Plan

1. Introduce the unified per-task runtime record type in execution types.
2. Refactor checkpoint save/load paths to use `tasks`.
3. Update planner execution flow to write terminal state and in-progress resume state into `tasks`.
4. Update Plan runtime/status payload shaping to expose only `tasks`.
5. Update task input resolution to read dependency outputs from `tasks[task_id].output`.
6. Rewrite tests and docs to the new shape.

## Open Questions

None. This change is decision-complete with direct field replacement and no compatibility layer.
