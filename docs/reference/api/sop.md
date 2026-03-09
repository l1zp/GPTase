# SOP API

> [Home](../README.md) → [API](.) → SOP

**Files:** `gptase/sop/orchestrator_agent.py`, `gptase/sop/types.py`, `gptase/sop/loader.py`

---

## SOPOrchestratorAgent

Main entry point for all SOP execution. Extends `Agent`.

```python
from gptase.sop import SOPOrchestratorAgent

orchestrator = SOPOrchestratorAgent(
    config: Optional[FrameworkConfig] = None,         # auto-created if None
    memory_manager: Optional[MemoryManager] = None,   # auto-created if None
    model_manager: Optional[Model] = None,            # auto-created if None
    sop_dir: Optional[str] = None,                    # custom SOP directory
)
```

### `execute_sop()`

```python
result = await orchestrator.execute_sop(
    plan_id: str,                                    # SOP identifier
    input_data: Dict[str, Any],                      # {"text": "...", ...}
    document_path: Optional[str] = None,             # dir of source document
    session_id: Optional[str] = None,                # resume existing session
    checkpoint: Optional[Dict] = None,               # restore from dict
    pre_completed_steps: Optional[Dict[str, StepResult]] = None,
    auto_checkpoint: bool = True,                    # save after each step
    workspace_dir: Optional[str] = None,             # agents write output here
) -> Dict[str, Any]
```

**Returns:**
```python
{
    "plan_id": "enzyme_extraction_pipeline",
    "status": "success",
    "step_results": {
        "1":  {"content": "..."},   # data from step 1
        "2a": {"content": "..."},   # data from step 2a
        "2b": {"content": "..."},   # data from step 2b
        "3":  {"content": "..."},   # data from step 3
    },
    "session_id": "sop_20240301_120000_abc12345",
    "workspace_dir": "/path/to/workspace",
}
```

### Session management

```python
# Resume an interrupted session
result = await orchestrator.resume_sop(
    session_id: str,
    input_data: Optional[Dict] = None,  # override original input if needed
)

# List sessions
sessions = await orchestrator.list_sessions(
    plan_id: Optional[str] = None,
    status: Optional[str] = None,   # "in_progress" | "completed" | "failed"
    limit: int = 50,
)
# Returns: [{"session_id", "plan_id", "created_at", "updated_at",
#             "status", "total_steps", "completed_steps", "progress"}, ...]

# Get session detail
status = await orchestrator.get_session_status(session_id: str)
# Returns: {"session_id", "plan_id", "status", "progress", "step_results", ...}

# Load checkpoint data
checkpoint = await orchestrator.load_checkpoint(session_id: str)

# Must call before program exit
await orchestrator.close()
```

### SOP discovery

```python
orchestrator.list_available_sops() -> List[Dict[str, str]]
orchestrator.get_sop(plan_id: str) -> SOPDefinition
```

---

## YAML Schema

```yaml
plan_id: my_pipeline              # required: unique identifier
name: "My Pipeline"               # optional: human-readable name
description: "What this does"     # optional
version: "1.0"                    # optional
default_retry_count: 0            # optional: default retries per step
max_parallel: 10                  # optional: max concurrent parallel steps

workflow:
  # Sequential step
  - step_id: "1"                  # required: unique within workflow (string or int)
    agent: my-agent               # required: name from .claude/agents/
    action: analyze               # optional: passed to agent as context (default: "process")
    description: "Step desc"      # optional: human-readable
    inputs:                       # optional: template variables resolved at runtime
      text: "{{input_text}}"
    retry_count: 2                # optional: overrides default_retry_count
    optional: false               # optional: if true, failure → SKIP not ABORT

  # Parallel group
  - parallel:
      - step_id: "2a"
        agent: extractor-a
        inputs:
          data: "{{step1}}"
      - step_id: "2b"
        agent: extractor-b
        inputs:
          images: "{{step1.images}}"

  # Reference previous steps
  - step_id: "3"
    agent: summarizer
    inputs:
      result_a: "{{step2a}}"
      result_b: "{{step2b.field}}"
      path: "{{document_path}}"
```

---

## Template Variables

Resolved in `step.inputs` values at dispatch time:

| Pattern | Resolves to |
|---|---|
| `{{input_text}}` | `input_data["text"]` |
| `{{input_data}}` | full `input_data` dict |
| `{{document_path}}` | `context.document_path` |
| `{{stepN}}` | full result `data` dict from step `N` |
| `{{stepN.field}}` | nested field from step `N` result |
| `{{stepN.a.b.c}}` | deep nested access |
| `{{var_name}}` | `context.variables["var_name"]` |

**Auto-parsing:** when a field is not found directly in a step result but the result has a `content` key containing a JSON string (including ` ```json ``` ` blocks), the dispatcher parses it and retries the field lookup automatically.

---

## Failure Handling

`FailureHandler.decide()` is AI-driven and returns one of:

| Decision | Effect |
|---|---|
| `FailureDecision.ABORT` | Raises `SOPExecutionError`. Checkpoint is saved — run is resumable via `resume_sop()`. |
| `FailureDecision.SKIP` | Step status becomes `SKIPPED`. Workflow continues. |
| `FailureDecision.RETRY` | Step re-dispatched. Up to `step.retry_count` (or `default_retry_count`) times. After max retries: `ABORT`. |

Setting `optional: true` on a step causes failures to auto-skip without consulting `FailureHandler`.

---

## Key Types

```python
class SOPDefinition(BaseModel):
    plan_id: str
    name: str
    workflow: List[Union[SOPStep, ParallelStep]]
    default_retry_count: int = 0
    max_parallel: int = 10

    def get_all_steps() -> List[SOPStep]
    def get_step_by_id(step_id) -> Optional[SOPStep]

class SOPStep(BaseModel):
    step_id: str          # auto-converted from int
    agent: str
    action: str = "process"
    inputs: Dict[str, Any]
    retry_count: int = 0
    optional: bool = False

class ParallelStep(BaseModel):
    parallel: List[SOPStep]

class TaskResult(BaseModel):
    agent_id: str
    step_id: Optional[str]
    status: str           # "success" | "failed"
    data: Optional[Dict]
    error: Optional[str]
    execution_time: Optional[float]

    def is_success() -> bool
    def is_failed() -> bool

class StepResult(BaseModel):
    step_id: str
    status: StepStatus    # PENDING|RUNNING|SUCCESS|FAILED|SKIPPED
    result: Optional[TaskResult]
    retry_attempts: int
    failure_decision: Optional[FailureDecision]

class ExecutionContext(BaseModel):
    plan_id: str
    input_data: Dict
    step_results: Dict[str, StepResult]
    variables: Dict
    current_step: Optional[str]
    session_id: Optional[str]
    document_path: Optional[str]
    workspace_dir: Optional[str]

    def get_step_data(step_id) -> Optional[Dict]
    def set_variable(name, value)
    def to_result() -> Dict
    def to_checkpoint() -> Dict
    @classmethod
    def from_checkpoint(checkpoint, validate_sop=None) -> ExecutionContext
```

---

## SOPRegistry

```python
from gptase.sop import SOPRegistry

registry = SOPRegistry.get_instance()        # singleton
sop = registry.get_sop("my_pipeline")       # raises if not found
sops = registry.list_sops()                 # [{"plan_id", "name"}, ...]
```

Auto-discovers all `.yaml` and `.json` files in `config/sops/`.

---

*Related: [Agent API →](./agent.md) | [Internals: Execution Flow →](../internals/execution-flow.md) | [Internals: Dispatcher →](../internals/dispatcher.md)*
