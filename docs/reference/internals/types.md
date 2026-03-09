# Type Reference

> [Home](../README.md) → [Internals](./) → Types

All Pydantic models, dataclasses, enums, and exceptions in the framework.

---

## Agent Types

**File:** `gptase/agents/types.py`

```python
@dataclass
class AgentDefinition:
    name: str
    description: str = ""
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""

    @property
    def agent_id(self) -> str:  # alias for name

class AgentTask(BaseModel):          # extra="allow"
    description: str = "Process the following data"
    workspace_dir: Optional[str] = None
    image_path: Optional[str] = None      # single image
    image_paths: Optional[List[str]] = None
    images: Optional[List[str]] = None    # alternate field

    def to_dict() -> Dict              # excludes None values
    def get_extra_fields() -> Dict     # only undeclared extra fields
    def get_image_paths() -> List[str] # merged + deduplicated
    @classmethod def from_dict(data) -> AgentTask

class AgentState(BaseModel):
    agent_id: str
    status: str = "idle"
    current_task: Optional[str] = None
```

---

## Model Types

**File:** `gptase/models/types.py`

```python
class ModelProvider(str, Enum):
    OPENAI = "openai"
    LOCAL  = "local"

class ThinkingConfig(BaseModel):
    type: str = "disabled"    # "enabled" | "disabled"

class ModelConfig(BaseModel):
    provider: str = "openai"
    model_name: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 2000
    timeout: int = 30
    max_retries: int = 3
    thinking: Optional[ThinkingConfig] = None
    enable_thinking: bool = False        # legacy
    provider_config: Dict[str, Any] = {}
    persist_response: bool = False
    system_prompt: Optional[str] = None

    def is_thinking_enabled() -> bool
    # Checks in order:
    # 1. thinking.type == "enabled"
    # 2. enable_thinking == True
    # 3. provider_config["extra_body"]["enable_thinking"] == True

class ModelResponse(BaseModel):
    content: str
    reasoning_content: Optional[str]
    usage: Dict[str, int]               # prompt_tokens, completion_tokens
    model: str
    provider: str
    tool_calls: Optional[List[ToolCall]]
    finish_reason: Optional[str]        # "stop" | "tool_calls"
    metadata: Dict[str, Any]

class StreamChunk(BaseModel):
    content: str = ""
    reasoning_content: str = ""
    is_thinking: bool = False
    is_complete: bool = False
    chunk_index: int = 0
    metadata: Dict[str, Any]

    def save_json(file_path) -> str

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]

# Multimodal types
class TextContent(BaseModel):
    type: str = "text"
    text: str

class ImageUrlContent(BaseModel):
    type: str = "image_url"
    image_url: Dict[str, str]   # {"url": "data:image/png;base64,..."}

MultimodalContent = Union[TextContent, ImageUrlContent, Dict[str, Any]]
```

---

## SOP Types

**File:** `gptase/sop/types.py`

### Enums

```python
class StepStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    SUCCESS  = "success"
    FAILED   = "failed"
    SKIPPED  = "skipped"

class FailureDecision(str, Enum):
    ABORT = "abort"
    SKIP  = "skip"
    RETRY = "retry"
```

### Workflow Definition

```python
class SOPStep(BaseModel):
    step_id: str          # int auto-converted to str via field_validator
    agent: str
    action: str = "process"
    description: str = ""
    inputs: Dict[str, Any] = {}
    retry_count: int = 0  # >= 0
    optional: bool = False

class ParallelStep(BaseModel):
    parallel: List[SOPStep]

WorkflowItem = Union[SOPStep, ParallelStep]

class SOPDefinition(BaseModel):
    plan_id: str
    name: str = ""
    description: str = ""
    version: str = "1.0"
    workflow: List[WorkflowItem]
    default_retry_count: int = 0
    max_parallel: int = 10     # >= 1

    def get_all_steps() -> List[SOPStep]   # flattens parallel groups
    def get_step_by_id(step_id) -> Optional[SOPStep]
```

Note: `SOPDefinition.workflow` uses a `field_validator` (`parse_workflow`) that converts raw dicts to `SOPStep` or `ParallelStep` based on the presence of a `"parallel"` key.

### Execution State

```python
class TaskResult(BaseModel):
    agent_id: str
    step_id: Optional[str] = None
    action: str = "process"
    status: str = "success"    # "success" | "failed"
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None

    def is_success() -> bool
    def is_failed() -> bool

class StepResult(BaseModel):
    step_id: str
    status: StepStatus = StepStatus.PENDING
    result: Optional[TaskResult] = None
    retry_attempts: int = 0
    failure_decision: Optional[FailureDecision] = None

class ExecutionContext(BaseModel):
    plan_id: str
    input_data: Dict[str, Any] = {}
    step_results: Dict[str, StepResult] = {}   # keyed by step_id
    variables: Dict[str, Any] = {}
    current_step: Optional[str] = None
    session_id: Optional[str] = None
    document_path: Optional[str] = None
    workspace_dir: Optional[str] = None

    def get_step_result(step_id) -> Optional[StepResult]
    def get_step_data(step_id) -> Optional[Dict]   # shortcut to result.data
    def update_step_result(step_id, result) -> None
    def set_variable(name, value) -> None
    def get_variable(name, default=None) -> Any
    def to_result() -> Dict          # final output dict
    def to_checkpoint() -> Dict      # serializable checkpoint dict
    @classmethod def from_checkpoint(checkpoint, validate_sop=None) -> ExecutionContext

class FailureContext(BaseModel):
    step: SOPStep
    error: str
    context: ExecutionContext
    attempt: int = 0
    max_retries: int = 3

    def can_retry() -> bool

class SOPCheckpoint(BaseModel):
    checkpoint_version: str = "1.0"
    checkpoint_id: str            # UUID
    created_at: datetime
    session_id: str
    plan_id: str
    input_data: Dict[str, Any]
    document_path: Optional[str]
    step_results: Dict[str, StepResult]
    variables: Dict[str, Any]
    current_step: Optional[str]
    workspace_dir: Optional[str]
    total_steps: int = 0
    completed_steps: int = 0
    status: str = "in_progress"   # "in_progress" | "completed" | "failed"
    sop_hash: Optional[str]       # MD5[:16] for compatibility check

    def is_step_completed(step_id) -> bool
    def get_progress() -> float    # 0-100
```

### `ExecutionContext.from_checkpoint()` Deserialization

When restoring from a checkpoint dict, the method:
1. Rebuilds each `StepResult` from its `model_dump()` form, including `TaskResult` and enum values
2. If `validate_sop` is provided, removes any `step_id` keys not present in the current SOP (guards against SOP edits)
3. Does not raise on missing steps — silently drops unknown step IDs

---

## Memory Types

**File:** `gptase/memory/models.py`

```python
class AgentMessage(BaseModel):
    id: str                          # UUID, auto-set
    sender: str
    recipient: str
    content: Any
    message_type: str = "message"
    timestamp: datetime              # auto-set
    metadata: Dict = {}

class AgentTask(BaseModel):          # memory layer, distinct from agents.types.AgentTask
    task_id: str
    agent_id: str
    result: Any
    status: str = "completed"
    error: Optional[str] = None
    execution_time: Optional[float] = None
    tools_used: Optional[List[str]] = None
    timestamp: datetime
```

---

## Config Types

**File:** `gptase/utils/config.py`

```python
class MemoryConfig(BaseModel):
    type: str = "local"
    max_history: int = 1000

class FrameworkConfig(BaseModel):
    llm_provider: str = "openai"
    llm_model: str = "gpt-4"
    llm_api_key: Optional[str]       # fallback: OPENAI_API_KEY env var
    llm_base_url: Optional[str] = None
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000
    llm_timeout: Optional[int] = None   # None → 600 in to_model_config()
    llm_thinking: Optional[ThinkingConfig] = None
    llm_provider_config: Dict = {}
    agent_models: Dict[str, Dict] = {}
    memory: MemoryConfig = MemoryConfig()
    log_level: str = "INFO"

    def to_model_config() -> ModelConfig
    def get_config_for_agent(agent_name) -> Optional[ModelConfig]
    def to_dict() -> Dict
```

---

## Exception Hierarchy

**File:** `gptase/sop/exceptions.py`

```
Exception
└── SOPError(message, details={})
    ├── SOPNotFoundError(plan_id, search_path=None)
    ├── SOPValidationError(plan_id, reason, field=None)
    ├── SOPExecutionError(plan_id, step_id=None, reason="", original_error=None)
    ├── AgentDispatchError(agent_id, action=None, reason="", original_error=None)
    └── CheckpointError
        ├── CheckpointNotFoundError(session_id)
        ├── CheckpointCorruptedError(session_id, reason)
        └── CheckpointVersionMismatchError(session_id, checkpoint_version, expected_version)
```

All `SOPError` subclasses store context in `self.details: Dict`. `SOPExecutionError.details` is enriched with `session_id` by the orchestrator before re-raising, enabling `resume_sop()` recovery.

**File:** `gptase/core/exceptions.py` (framework-level)

```
Exception
└── GPTaseError
    ├── ConfigurationError
    ├── ProviderError
    ├── ModelError
    └── ToolError
```

---

*Related: [Execution Flow →](./execution-flow.md) | [Dispatcher Internals →](./dispatcher.md)*
