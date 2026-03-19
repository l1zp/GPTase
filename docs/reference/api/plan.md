# Plan API

> [Home](../README.md) → [API](.) → Plan

**Files:** `gptase/agents/planner.py`, `gptase/agents/types.py`, `gptase/agents/plan_loader.py`

---

## PlanManager

Main entry point for plan generation and execution. Integrated into the `Agent` class as `agent.planner`.

```python
from gptase.agents.planner import PlanManager

plan_manager = PlanManager(
    agent: Agent,                                     # parent agent
    model: Optional[Model] = None,                    # for plan generation
    model_config: Optional[ModelConfig] = None,       # generation config
)
```

### `execute_plan()`

```python
result = await plan_manager.execute_plan(
    plan: Plan,                                      # Plan object to execute
    input_data: Optional[Dict[str, Any]] = None,     # {"text": "...", ...}
    session_id: Optional[str] = None,                # resume existing session
    context_checkpoint: Optional[Dict] = None,       # restore from dict
    workspace_dir: Optional[str] = None,             # agents write output here
    auto_checkpoint: bool = True,                    # save after each task
    on_task_complete: Optional[Callable] = None,     # callback after each task
) -> Dict[str, Any]
```

**Returns:**
```python
{
    "plan_id": "plan_abc123",
    "status": "completed",
    "task_results": {
        "1":  {"content": "..."},   # data from task 1
        "2a": {"content": "..."},   # data from task 2a
    },
    "session_id": "plan_20240301_120000_abc12345",
    "workspace_dir": "/path/to/workspace",
    "progress": {"total": 4, "completed": 4, "failed": 0, ...}
}
```

### Session management

```python
# List sessions from database
sessions = await plan_manager.list_sessions(
    plan_id: Optional[str] = None,
    status: Optional[str] = None,   # "in_progress" | "completed" | "failed"
)

# Get session detail
status = await plan_manager.get_session_status(session_id: str)

# Load checkpoint data
checkpoint = await plan_manager._load_checkpoint_from_db(session_id: str)
```

### Plan Generation

```python
# Create a plan from a natural language goal
plan = await plan_manager.create_plan(
    goal: str,
    input_text: Optional[str] = None,
)
```

---

## YAML Schema

Unified Plans use a DAG structure with explicit dependencies. Supports legacy Plan formats via `PlanLoader`.

```yaml
plan_id: my_pipeline              # required: unique identifier
goal: "Extract data"              # optional: high-level goal
tasks:
  - task_id: "1"                  # required: unique within plan
    agent_id: document_analyzer   # required: agent name
    description: "Analyze"        # optional
    inputs:                       # optional: template variables
      text: "{{input_text}}"
    retry_count: 2                # optional
    optional: false               # if true, failure -> SKIPPED

  - task_id: "2"
    agent_id: extractor
    dependencies: ["1"]           # explicit dependency
    inputs:
      data: "{{task1}}"
```

---

## Template Variables

Resolved in `task.inputs` at dispatch time:

| Pattern | Resolves to |
|---|---|
| `{{input_text}}` | `input_data["text"]` |
| `{{taskN}}` | full result data from task `N` |
| `{{taskN.field}}` | nested field from task `N` result |
| `{{document_path}}` | source document path |

---

## Failure Handling

Managed by `FailureHandler` with three possible decisions:

| Decision | Effect |
|---|---|
| `FailureDecision.ABORT` | Plan execution stops, raises `PlanExecutionError`. |
| `FailureDecision.SKIP` | Task becomes `SKIPPED`. Plan continues. |
| `FailureDecision.RETRY` | Task re-dispatched. |

---

## Key Types

```python
class Plan(BaseModel):
    plan_id: str
    goal: str
    tasks: List[PlannedTask]
    max_parallel: int = 5

class PlannedTask(BaseModel):
    task_id: str
    agent_id: str
    description: str
    dependencies: List[str] = []
    inputs: Dict[str, Any] = {}
    status: TaskStatus = TaskStatus.PENDING
```
