# Plan API

> [首页](../README.md) → [API](.) → Plan

**相关文件：** `gptase/agents/planner.py`, `gptase/agents/types.py`, `gptase/agents/plan_loader.py`

---

## Orchestrator Harness

当前用户侧主入口是 `AgentOrchestrator`，它持有 goal session。
`PlanManager` 仍然是内部用于执行单个 draft plan 的引擎。

重要边界：
- `AgentOrchestrator` 是 harness runtime 的主入口
- worker agents 仍定义在 `.claude/agents/*`
- `PlanManager` 与 `TaskDispatcher` 是 runtime 内部使用的编排组件
- orchestrator 本身不是 markdown 定义的 Agent

```python
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig

orchestrator = AgentOrchestrator(FrameworkConfig())

draft = await orchestrator.execute_task({
    "description": "分析这篇论文并比较变体",
    "auto_execute": False,
})

approved = await orchestrator.approve_plan(draft["session_id"])
```

Harness 返回结果示例：

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
    agent: Agent,                                     # 父 Agent
    model: Optional[Model] = None,                    # 用于生成计划的模型
    model_config: Optional[ModelConfig] = None,       # 生成配置
)
```

### `execute_plan()`

```python
result = await plan_manager.execute_plan(
    plan: Plan,                                      # 要执行的 Plan 对象
    input_data: Optional[Dict[str, Any]] = None,     # 输入数据 {"text": "...", ...}
    session_id: Optional[str] = None,                # 恢复现有会话
    context_checkpoint: Optional[Dict] = None,       # 从字典恢复
    workspace_dir: Optional[str] = None,             # 智能体输出目录
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
        "1":  {"content": "..."},   # 任务 1 的数据
        "2a": {"content": "..."},   # 任务 2a 的数据
    },
    "session_id": "plan_20240301_120000_abc12345",
    "workspace_dir": "/path/to/workspace",
    "progress": {"total": 4, "completed": 4, "failed": 0, ...}
}
```

### 会话管理

```python
# 从数据库列出底层 plan 执行会话
sessions = await plan_manager.list_sessions(
)

# 获取会话详细状态
status = await plan_manager.get_session_status(session_id: str)

# 加载断点数据
checkpoint = await plan_manager._load_checkpoint_from_db(session_id: str)
```

### 计划生成

```python
# 根据自然语言目标创建 draft plan
plan = await plan_manager.create_plan(
    goal: str,
    context: str = "",
    available_agents: Optional[List[Dict[str, str]]] = None,
)
```

---

## YAML 配置架构

统一的 Plan 使用基于有向无环图 (DAG) 的结构，通过 `dependencies` 显式声明依赖。

```yaml
plan_id: my_pipeline              # 必填：唯一标识符
goal: "提取数据"                    # 可选：高水平目标
tasks:
  - task_id: "1"                  # 必填：计划内唯一标识（字符串或数字）
    agent_id: document_analyzer   # 必填：.claude/agents/ 中的智能体名称
    description: "分析文档"           # 可选
    inputs:                       # 可选：运行时解析的模板变量
      text: "{{input_text}}"
    retry_count: 2                # 可选：重试次数
    optional: false               # 如果为 true，失败将标记为 SKIPPED 而非中断

  - task_id: "2"
    agent_id: extractor
    dependencies: ["1"]           # 显式依赖项
    inputs:
      data: "{{task1}}"
```

---

## 模板变量

在任务调度时解析 `task.inputs` 中的值：

| 模式 | 解析为 |
|---|---|
| `{{input_text}}` | `input_data["text"]` |
| `{{taskN}}` | 任务 `N` 的完整结果字典 |
| `{{taskN.field}}` | 任务 `N` 结果中的嵌套字段 |
| `{{document_path}}` | 源文档路径 |

---

## 失败处理 (Failure Handling)

由 `FailureHandler` 管理，支持三种决策：

| 决策 | 效果 |
|---|---|
| `FailureDecision.ABORT` | 停止计划执行，抛出 `PlanExecutionError`。 |
| `FailureDecision.SKIP` | 任务标记为 `SKIPPED`，计划继续执行。 |
| `FailureDecision.RETRY` | 重新调度该任务。 |

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
