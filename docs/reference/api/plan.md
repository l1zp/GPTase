# Plan API

> [Home](../README.md) → [API](.) → Plan

**Files:** `gptase/agents/planner.py`, `gptase/agents/types.py`, `gptase/agents/plan_loader.py`, `gptase/core/orchestrator.py`

---

## Orchestrator Plan Execution

The primary user-facing entry point is `AgentOrchestrator`, which manages
plan execution inline. `PlanManager` is the internal execution engine for
individual plans, including plans created by runtime handoff.

### Where plans can come from

1. User-provided `plan`, `plan_id`, or `plan_path`
2. `AgentOrchestrator` generating a plan from a natural-language goal
3. `agent_id="auto"` runtime returning `needs_plan`, which triggers plan execution

Important boundary:
- `AgentOrchestrator` is the orchestrator runtime entry point
- worker agents still live in `.claude/agents/*`
- `PlanManager` and `TaskDispatcher` are internal orchestration components used by the runtime
- the orchestrator itself is not a markdown-defined agent

```python
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig

orchestrator = AgentOrchestrator(FrameworkConfig())

result = await orchestrator.execute_task({
    "description": "Analyze this paper and compare variants",
    "plan_id": "enzyme_extraction_pipeline",
    "auto_execute": True,
})
```

### Plan execution result shape

```python
# Draft mode (auto_execute=False)
{
    "status": "draft",
    "goal": "...",
    "current_plan": {...},
    "progress": {"total": 3, "completed": 0, "failed": 0},
    "preflight": {"status": "warning", "warnings": [...]},
    "timestamp": "2026-04-01T12:00:00",
}

# Completed mode
{
    "status": "completed",
    "goal": "...",
    "current_plan": {...},
    "plan_history": [{...}],
    "progress": {"total": 3, "completed": 3, "failed": 0},
    "task_results": {...},
    "goal_evaluation": {"goal_achieved": True, ...},
    "preflight": {"status": "ok", "warnings": [], "errors": []},
    "timestamp": "2026-04-01T12:00:00",
}
```

### Runtime handoff flow

When runtime returns `needs_plan`, the orchestrator:

1. Calls `_execute_plan()` with the handoff goal
2. Resolves or generates a plan via `PlanManager.create_plan(...)`
3. Either returns a `draft` result or immediately executes if `auto_execute=True`

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
    plan: Plan,                                      # plan object to execute
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
        "1": {"content": "..."},
        "2a": {"content": "..."},
    },
    "task_traces": {
        "1": {"steps": [], "runtime": {...}},
        "2a": {"steps": [], "runtime": {...}},
    },
    "session_id": "plan_20260401_120000_abc12345",
    "workspace_dir": "/path/to/workspace",
    "active_tasks": {},
    "progress": {"total": 4, "completed": 4, "failed": 0, ...}
}
```

### Session management

```python
sessions = await plan_manager.list_sessions()
status = await plan_manager.get_session_status(session_id)
checkpoint = await plan_manager._load_checkpoint_from_db(session_id)
```

### Plan generation

```python
plan = await plan_manager.create_plan(
    goal: str,
    context: str = "",
    available_agents: Optional[List[Dict[str, str]]] = None,
)
```

This is used both for normal draft generation and for drafts created from
runtime handoff inside `AgentOrchestrator`.

---

## YAML Schema

Unified Plans use a DAG structure with explicit dependencies. Legacy formats are
still supported through `PlanLoader`.

```yaml
plan_id: my_pipeline
goal: "Extract data"
tasks:
  - task_id: "1"
    agent_id: document_analyzer
    description: "Analyze"
    inputs:
      text: "{{input_text}}"
    retry_count: 2
    optional: false

  - task_id: "2"
    agent_id: extractor
    dependencies: ["1"]
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
| `FailureDecision.ABORT` | Plan execution stops and raises `PlanExecutionError` |
| `FailureDecision.SKIP` | Task becomes `SKIPPED`, plan continues |
| `FailureDecision.RETRY` | Task is re-dispatched |

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
