# Plan API

> [首页](../README.md) → [API](.) → Plan

**相关文件：** `gptase/agents/planner.py`, `gptase/agents/types.py`, `gptase/agents/plan_loader.py`, `gptase/core/orchestrator.py`

---

## Orchestrator Plan Execution

当前用户侧主入口是 `AgentOrchestrator`，它管理 Plan 的内联执行。`PlanManager`
是内部用于执行单个 Plan 的引擎，包括 runtime handoff 生成的 Plan。

### Plan 的来源

1. 用户显式提供 `plan`、`plan_id` 或 `plan_path`
2. `AgentOrchestrator` 根据自然语言目标自动生成 Plan
3. `agent_id="auto"` 的 runtime 返回 `needs_plan`，触发 Plan 执行

重要边界：
- `AgentOrchestrator` 是 orchestrator runtime 的主入口
- worker agents 仍定义在 `.claude/agents/*`
- `PlanManager` 与 `TaskDispatcher` 是 runtime 内部使用的编排组件
- orchestrator 本身不是 markdown 定义的 Agent

```python
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig

orchestrator = AgentOrchestrator(FrameworkConfig())

result = await orchestrator.execute_task({
    "description": "分析这篇论文并比较变体",
    "plan_id": "enzyme_extraction_pipeline",
    "auto_execute": True,
})
```

### Plan 执行返回结构

```python
# Draft 模式 (auto_execute=False)
{
    "status": "draft",
    "goal": "...",
    "current_plan": {...},
    "progress": {"total": 3, "completed": 0, "failed": 0},
    "preflight": {"status": "warning", "warnings": [...]},
    "timestamp": "2026-04-01T12:00:00",
}

# 完成模式
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

### Runtime handoff 流程

当 runtime 返回 `needs_plan` 时，orchestrator 会：

1. 调用 `_execute_plan()`，传入 handoff 目标
2. 通过 `PlanManager.create_plan(...)` 解析或生成 Plan
3. 根据 `auto_execute` 决定是返回 `draft` 结果还是立即执行

## PlanManager

```python
from gptase.agents.planner import PlanManager

plan_manager = PlanManager(
    agent: Agent,                                     # 父 Agent
    model: Optional[Model] = None,                    # 用于生成计划的模型
    model_config: Optional[ModelConfig] = None,       # 生成配置
)
```

### `execute_plan()`

```python
result = await plan_manager.execute_plan(
    plan: Plan,                                      # 要执行的 plan 对象
    input_data: Optional[Dict[str, Any]] = None,     # {"text": "...", ...}
    session_id: Optional[str] = None,                # 恢复现有会话
    context_checkpoint: Optional[Dict] = None,       # 从字典恢复
    workspace_dir: Optional[str] = None,             # agents 输出目录
    auto_checkpoint: bool = True,                    # 每步任务后自动保存
    on_task_complete: Optional[Callable] = None,     # 任务完成后的回调
) -> Dict[str, Any]
```

**返回结果：**

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

### 会话管理

```python
sessions = await plan_manager.list_sessions()
status = await plan_manager.get_session_status(session_id)
checkpoint = await plan_manager._load_checkpoint_from_db(session_id)
```

### 计划生成

```python
plan = await plan_manager.create_plan(
    goal: str,
    context: str = "",
    available_agents: Optional[List[Dict[str, str]]] = None,
)
```

这既用于普通的 draft 生成，也用于 `AgentOrchestrator` 中 runtime handoff 产生的 draft。

---

## YAML 配置架构

统一的 Plan 使用 DAG 结构，通过显式 `dependencies` 声明依赖。旧格式仍可通过
`PlanLoader` 兼容加载。

```yaml
plan_id: my_pipeline
goal: "提取数据"
tasks:
  - task_id: "1"
    agent_id: document_analyzer
    description: "分析"
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

## 模板变量

在任务调度时解析 `task.inputs`：

| 模式 | 解析为 |
|---|---|
| `{{input_text}}` | `input_data["text"]` |
| `{{taskN}}` | 任务 `N` 的完整结果数据 |
| `{{taskN.field}}` | 任务 `N` 结果中的嵌套字段 |
| `{{document_path}}` | 源文档路径 |

---

## 失败处理

由 `FailureHandler` 管理，支持三种决策：

| 决策 | 效果 |
|---|---|
| `FailureDecision.ABORT` | 停止计划执行并抛出 `PlanExecutionError` |
| `FailureDecision.SKIP` | 任务标记为 `SKIPPED`，计划继续 |
| `FailureDecision.RETRY` | 重新调度该任务 |

---

## 核心类型

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
