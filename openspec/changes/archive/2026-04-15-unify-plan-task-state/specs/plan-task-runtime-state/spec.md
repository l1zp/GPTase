## ADDED Requirements

### Requirement: Plan runtime state SHALL use a single per-task container
The system SHALL represent Plan runtime state through a single `tasks` container keyed by `task_id`, where each task record is the authoritative source of that task's runtime status.

#### Scenario: Completed task state is self-contained
- **WHEN** a Plan task completes successfully
- **THEN** the corresponding `tasks[task_id]` record MUST contain the task's terminal status, latest output payload, latest terminal trace, and no active resume state

#### Scenario: In-progress task state is self-contained
- **WHEN** a Plan task is checkpointed while still running
- **THEN** the corresponding `tasks[task_id]` record MUST contain the task's in-progress status and its latest resumable runtime snapshot in `resume_state`

### Requirement: Plan runtime payloads SHALL expose unified task state only
The system SHALL expose unified per-task runtime state through Plan execution and Plan session status payloads, and SHALL not expose separate `task_results`, `task_traces`, or `active_tasks` fields.

#### Scenario: Plan execution result exposes unified tasks
- **WHEN** `execute_plan()` returns a result
- **THEN** the result MUST expose per-task runtime data through `tasks`
- **THEN** the result MUST NOT expose parallel `task_results`, `task_traces`, or `active_tasks` fields

#### Scenario: Plan session status exposes unified tasks
- **WHEN** a Plan session status is read from checkpoint state
- **THEN** the status payload MUST expose per-task runtime data through `tasks`
- **THEN** the status payload MUST NOT expose parallel `task_results`, `task_traces`, or `active_tasks` fields

### Requirement: Plan task records SHALL preserve minimal attempt history
The system SHALL preserve lightweight attempt summaries for each task without persisting a full append-only event history.

#### Scenario: Retry history is preserved as summaries
- **WHEN** a task fails and is retried
- **THEN** its `tasks[task_id]` record MUST preserve per-attempt summaries including status, timing, and error context as available

#### Scenario: Successful tasks do not require full historical traces
- **WHEN** a task completes successfully
- **THEN** its `tasks[task_id]` record MAY preserve attempt summaries
- **THEN** it MUST NOT require a full append-only per-turn history to be considered complete

### Requirement: Dependency resolution SHALL read from unified task output
The system SHALL resolve downstream task inputs from the unified task runtime state.

#### Scenario: Task output is used for template resolution
- **WHEN** a later Plan task references a prior task's output
- **THEN** the dispatcher/runtime MUST resolve that value from `tasks[task_id].output`

#### Scenario: Resume state is not treated as task output
- **WHEN** a task is still in progress and only has `resume_state`
- **THEN** downstream dependency resolution MUST NOT treat `resume_state` as completed task output
