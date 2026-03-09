# SOP API

> [首页](../README.md) → [API](.) → SOP

**文件：** `gptase/sop/orchestrator_agent.py`、`gptase/sop/types.py`、`gptase/sop/loader.py`

---

## SOPOrchestratorAgent

所有 SOP 执行的主入口。继承自 `Agent`。

```python
from gptase.sop import SOPOrchestratorAgent

orchestrator = SOPOrchestratorAgent(
    config: Optional[FrameworkConfig] = None,         # 为 None 时自动创建
    memory_manager: Optional[MemoryManager] = None,   # 为 None 时自动创建
    model_manager: Optional[Model] = None,            # 为 None 时自动创建
    sop_dir: Optional[str] = None,                    # 自定义 SOP 目录
)
```

### `execute_sop()`

```python
result = await orchestrator.execute_sop(
    plan_id: str,                                    # SOP 标识符
    input_data: Dict[str, Any],                      # {"text": "...", ...}
    document_path: Optional[str] = None,             # 源文档所在目录
    session_id: Optional[str] = None,                # 恢复已有 session
    checkpoint: Optional[Dict] = None,               # 从字典恢复
    pre_completed_steps: Optional[Dict[str, StepResult]] = None,
    auto_checkpoint: bool = True,                    # 每步后保存断点
    workspace_dir: Optional[str] = None,             # Agent 输出写入此处
) -> Dict[str, Any]
```

**返回值：**
```python
{
    "plan_id": "enzyme_extraction_pipeline",
    "status": "success",
    "step_results": {
        "1":  {"content": "..."},   # 步骤 1 数据
        "2a": {"content": "..."},   # 步骤 2a 数据
        "2b": {"content": "..."},   # 步骤 2b 数据
        "3":  {"content": "..."},   # 步骤 3 数据
    },
    "session_id": "sop_20240301_120000_abc12345",
    "workspace_dir": "/path/to/workspace",
}
```

### Session 管理

```python
# 恢复中断的 session
result = await orchestrator.resume_sop(
    session_id: str,
    input_data: Optional[Dict] = None,   # 如需覆盖原始输入
)

# 列出所有 session
sessions = await orchestrator.list_sessions(
    plan_id: Optional[str] = None,
    status: Optional[str] = None,   # "in_progress" | "completed" | "failed"
    limit: int = 50,
)
# 返回：[{"session_id", "plan_id", "created_at", "updated_at",
#          "status", "total_steps", "completed_steps", "progress"}, ...]

# 获取 session 详情
status = await orchestrator.get_session_status(session_id: str)
# 返回：{"session_id", "plan_id", "status", "progress", "step_results", ...}

# 加载 checkpoint 数据
checkpoint = await orchestrator.load_checkpoint(session_id: str)

# 程序退出前必须调用
await orchestrator.close()
```

### SOP 发现

```python
orchestrator.list_available_sops() -> List[Dict[str, str]]
orchestrator.get_sop(plan_id: str) -> SOPDefinition
```

---

## YAML Schema {#yaml-schema}

```yaml
plan_id: my_pipeline              # 必填：唯一标识符
name: "我的工作流"                 # 可选：人类可读名称
description: "功能描述"           # 可选
version: "1.0"                    # 可选
default_retry_count: 0            # 可选：每步的默认重试次数
max_parallel: 10                  # 可选：并行步骤的最大并发数

workflow:
  # 顺序步骤
  - step_id: "1"                  # 必填：工作流内唯一（字符串或整数）
    agent: my-agent               # 必填：.claude/agents/ 中的 Agent 名称
    action: analyze               # 可选：作为上下文传递给 Agent（默认："process"）
    description: "步骤描述"        # 可选
    inputs:                       # 可选：运行时解析的模板变量
      text: "{{input_text}}"
    retry_count: 2                # 可选：覆盖 default_retry_count
    optional: false               # 可选：true 时失败→SKIP，而非 ABORT

  # 并行组
  - parallel:
      - step_id: "2a"
        agent: extractor-a
        inputs:
          data: "{{step1}}"
      - step_id: "2b"
        agent: extractor-b
        inputs:
          images: "{{step1.images}}"

  # 引用前序步骤
  - step_id: "3"
    agent: summarizer
    inputs:
      result_a: "{{step2a}}"
      result_b: "{{step2b.field}}"
      path: "{{document_path}}"
```

---

## 模板变量

在调度时对 `step.inputs` 中的值进行解析：

| 模板 | 解析为 |
|---|---|
| `{{input_text}}` | `input_data["text"]` |
| `{{input_data}}` | 完整 `input_data` 字典 |
| `{{document_path}}` | `context.document_path` |
| `{{stepN}}` | 步骤 `N` 的完整结果 data 字典 |
| `{{stepN.field}}` | 步骤 `N` 结果中的嵌套字段 |
| `{{stepN.a.b.c}}` | 深层嵌套访问 |
| `{{var_name}}` | `context.variables["var_name"]` |

**自动解析：** 当字段在步骤结果中直接查找失败，但结果包含含 JSON 字符串的 `content` 键（含 ` ```json ``` ` 代码块）时，调度器自动解析并重试查找。

---

## 失败处理策略

`FailureHandler.decide()` 由 AI 驱动，返回以下决策之一：

| 决策 | 效果 |
|---|---|
| `FailureDecision.ABORT` | 抛出 `SOPExecutionError`。保存 checkpoint — 可通过 `resume_sop()` 恢复。 |
| `FailureDecision.SKIP` | 步骤状态变为 `SKIPPED`，工作流继续。 |
| `FailureDecision.RETRY` | 重新调度步骤，最多重试 `step.retry_count`（或 `default_retry_count`）次。超过上限后：ABORT。 |

步骤设置 `optional: true` 时，失败自动跳过，不咨询 `FailureHandler`。

---

## 核心类型

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
    step_id: str          # 整数自动转换为字符串
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

registry = SOPRegistry.get_instance()        # 单例
sop = registry.get_sop("my_pipeline")       # 未找到时抛出异常
sops = registry.list_sops()                 # [{"plan_id", "name"}, ...]
```

自动发现 `config/sops/` 中所有 `.yaml` 和 `.json` 文件。

---

*相关：[Agent API →](./agent.md) | [内部实现：执行流程 →](../internals/execution-flow.md) | [内部实现：调度器 →](../internals/dispatcher.md)*
