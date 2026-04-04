# Type Reference

> [Home](../README.md) → [Internals](./) → Types

**File:** `gptase/agents/types.py`, `gptase/agents/execution_types.py`

---

## Core Plan Types

### `Plan`
The top-level execution unit representing a DAG of tasks.
- `plan_id`: Unique identifier.
- `goal`: Natural language objective.
- `tasks`: List of `Task` objects.
- `max_parallel`: Max concurrent tasks.

### `Task`
A single node in the execution DAG.
- `task_id`: Unique identifier (e.g., "1", "2a").
- `agent_id`: Target agent to execute this task.
- `dependencies`: List of `task_id`s that must complete first.
- `inputs`: Template-resolved parameters.

### `TaskStatus`
- `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `SKIPPED`.

---

## Execution Types

### `ExecutionContext`
State container for a running plan session.
- `session_id`: Persistent session identifier.
- `task_results`: Map of results from finished tasks.
- `input_data`: Initial input parameters.

### `TaskResult`
Outcome of an agent's execution.
- `status`: "success" or "failed".
- `data`: Output dictionary.
- `error`: Error message if failed.
