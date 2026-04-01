# Plan API

> [Home](../README.md) → [API](.) → Plan

**Files:** `gptase/agents/planner.py`, `gptase/agents/types.py`, `gptase/agents/plan_loader.py`, `gptase/core/orchestrator.py`

---

## Orchestrator Harness

The primary user-facing entry point is `AgentOrchestrator`, which owns the goal
session. `PlanManager` remains the internal execution engine for individual draft
plans, including drafts created by runtime handoff.

### Where draft plans can come from

1. User-provided `plan`, `plan_id`, or `plan_path`
2. `AgentOrchestrator` generating a draft plan from a natural-language goal
3. `agent_id="auto"` runtime returning `needs_plan`, which creates a
   `runtime_handoff` draft session

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

### Harness result shape

```python
{
    "session_id": "goal_20260401_120000_abc12345",
    "status": "awaiting_approval|executing|completed|awaiting_user_input|blocked",
    "goal": "...",
    "draft_source": "provided|generated|runtime_handoff|revised",
    "current_plan": {...},
    "plan_history": [{...}],
    "progress": {"total": 3, "completed": 2, "failed": 0},
    "goal_evaluation": {"goal_achieved": False, ...},
    "task_results": {...},
    "task_traces": {...},
    "handoff": None or {...},
    "coordinator": None or {...},
    "preflight": {"status": "warning", "warnings": [...]},
    "execution_mode": "harness",
}
```

### Runtime handoff flow

```python
draft = await orchestrator.execute_task({
    "description": "Ship the feature",
    "auto_execute": False,
})

# Runtime may return a runtime_handoff draft session instead of a direct answer.
approved = await orchestrator.approve_plan(draft["session_id"])
```

When runtime returns `needs_plan`, the orchestrator:

1. Creates a goal session with `draft_source="runtime_handoff"`
2. Stores the structured `handoff` proposal
3. Stores `coordinator` summary when delegation happened before handoff
4. Calls `PlanManager.create_plan(...)`
5. Either returns `awaiting_approval` or immediately executes if `auto_execute=True`

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
