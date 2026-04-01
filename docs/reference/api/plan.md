# Plan API

> [Home](../README.md) → [API](.) → Plan

**Files:** `gptase/agents/planner.py`, `gptase/agents/types.py`, `gptase/agents/plan_loader.py`

---

## Orchestrator Harness

The primary user-facing entry point is now `AgentOrchestrator`, which owns a goal session.
`PlanManager` remains the internal execution engine for individual draft plans.

Important boundary:
- `AgentOrchestrator` is the harness runtime entry point
- worker agents still live in `.claude/agents/*`
- `PlanManager` and `TaskDispatcher` are internal orchestration components used by the runtime
- the orchestrator itself is not a markdown-defined agent

```python
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig

orchestrator = AgentOrchestrator(FrameworkConfig())

draft = await orchestrator.execute_task({
    "description": "Analyze this paper and compare variants",
    "auto_execute": False,
})

approved = await orchestrator.approve_plan(draft["session_id"])
```

Harness result shape:

```python
{
    "session_id": "goal_20240301_120000_abc12345",
    "status": "awaiting_approval|executing|completed|awaiting_user_input|blocked",
    "goal": "...",
    "current_plan": {...},
    "plan_history": [{...}],
    "goal_evaluation": {"goal_achieved": True, ...},
    "task_results": {...},
}
```

## PlanManager

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
# List low-level plan execution sessions from database
sessions = await plan_manager.list_sessions(
)

# Get session detail for a plan execution checkpoint
status = await plan_manager.get_session_status(session_id: str)

# Load checkpoint data
checkpoint = await plan_manager._load_checkpoint_from_db(session_id: str)
```

### Plan Generation

```python
# Create a draft plan from a natural language goal
plan = await plan_manager.create_plan(
    goal: str,
    context: str = "",
    available_agents: Optional[List[Dict[str, str]]] = None,
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
