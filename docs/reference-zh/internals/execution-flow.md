# 执行流程 (Execution Flow)

> [首页](../README.md) → [内部原理](./) → 执行流程

**相关文件：** `gptase/core/orchestrator.py`, `gptase/agents/base.py`, `gptase/agents/planner.py`

---

## 三种执行模式

`dispatch` 根据参数路由到三条路径：

```
dispatch(task)
  │
  ├─ task 有 plan/plan_id/plan_path → Plan 模式
  │   └─> _execute_plan()
  │
  ├─ task 有 agent_id（非 orchestrator） → Agent 模式
  │   └─> _execute_agent()
  │
  └─ 默认 → Coordinator 模式
      └─> _execute_coordinator()
```

## Agent 模式

单个 agent 的标准 ReAct 循环。

```
agent.process_task(task)
  └─> agent.run(prompt)
        ├─ claude-* model → _run_with_sdk()
        └─ other model    → _run_with_llm() → AgentRuntime.run()
```

## Coordinator 模式

Orchestrator agent 循环，最多 `_MAX_COORDINATOR_TURNS`（3）轮。

```
_execute_coordinator(task_id, task)
  │
  ├─ for turn in range(3):
  │     result = self.run(prompt)
  │     runtime = _runtime_trace(result)
  │     │
  │     ├─ needs_plan → _execute_plan()
  │     ├─ final_answer 且无 delegation → 返回结果
  │     ├─ 无 coordinator activity → 返回错误
  │     └─ 有 delegation → 合并 coordinator summary → 构建 followup prompt → 继续
  │
  └─ 超过最大轮次 → 返回失败
```

Coordinator 可通过 DelegateTask tool call 委派 worker agent。
Runtime 通过解析 tool result 中的 coordinator_summary 检测委派行为。

## Plan 执行流程 (Plan Execution Flow)

`PlanManager` 使用基于有向无环图 (DAG) 的依赖系统管理复杂的多智能体工作流。

```
plan_manager.execute_plan(plan, input_data, ...)
  │
  ├─ 恢复/创建 ExecutionContext
  ├─ 当计划未完成时：
  │    ├─ next_tasks = plan.get_next_tasks()
  │    ├─ 根据 max_parallel 进行过滤
  │    ├─ 对每个任务：
  │    │    └─ _execute_single_task(task, ...)
  │    │         ├─ 通过 TaskDispatcher 解析输入
  │    │         ├─ dispatcher.dispatch(task) -> TaskResult
  │    │         └─ 如果失败：failure_handler.decide()
  │    └─ asyncio.gather(execution_coros)
  │
  └─ 返回最终结果字典
```

### 断点保存 (Checkpointing)

状态在每项任务完成以及主要状态变更（开始、结束、失败）时保存到 SQLite 数据库。

1. **会话 ID (Session ID)**: 生成格式为 `plan_YYYYMMDD_HHMMSS_<hex>`。
2. **恢复执行**: 使用现有的 `session_id` 调用 `execute_plan` 会恢复 `ExecutionContext` 并自动跳过已完成 (`COMPLETED`) 的任务。
