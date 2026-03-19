# 执行流程 (Execution Flow)

> [首页](../README.md) → [内部原理](./) → 执行流程

**相关文件：** `gptase/agents/base.py`, `gptase/agents/planner.py`

---

## 单智能体执行 (直接模式)

单个任务的标准 ReAct 循环。

## 计划执行流程 (Plan Execution Flow)

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
