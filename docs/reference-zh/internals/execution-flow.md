# 执行流程 (Execution Flow)

> [首页](../README.md) → [内部原理](./) → 执行流程

**相关文件：** `gptase/core/orchestrator.py`, `gptase/agents/base.py`, `gptase/agents/runtime.py`, `gptase/agents/plan_prompt.py`, `gptase/tools/handlers.py`

---

## 两种执行模式

`dispatch` 根据参数路由到两条路径：

```
dispatch(task)
  │
  ├─ task 有 agent_id（非 orchestrator） → Agent 模式
  │   └─> _execute_agent()
  │
  └─ 默认 → Coordinator 模式
      └─> _execute_coordinator()
```

如果 `dispatch` 收到 `plan_id` / `plan_path`，CLI 层（`gptase chat -p`）
会先把 YAML 通过 `expand_plan_to_prompt` 展开为结构化 to-do 字符串，
作为 Coordinator 模式的初始 user prompt。

## Agent 模式

单个 agent 的标准 ReAct 循环。

```
agent.process_task(task)
  └─> agent.run(prompt)
        ├─ claude-* model → _run_with_sdk()
        └─ other model    → _run_with_llm() → AgentRuntime.run()
```

## Coordinator 模式

Orchestrator runtime 在外层循环中调用 `self.run`，每次返回的 trace 决定
继续/终止。最多 `_MAX_COORDINATOR_TURNS` 轮。

```
_execute_coordinator(task_id, task)
  │
  ├─ for turn in range(_MAX_COORDINATOR_TURNS):
  │     result = self.run(prompt)
  │     runtime = _runtime_trace(result)
  │     │
  │     ├─ stop_reason == "final_answer" → 返回结果（即使本 turn 有 delegation）
  │     ├─ 无 coordinator activity → 返回错误
  │     └─ 有 delegation → 构建 followup prompt → 继续
  │
  └─ 超过最大轮次 → 返回失败
```

Coordinator 通过 `DelegateTask` 工具委派 worker agent。
Runtime 通过解析 tool result 中的 `coordinator_summary` 检测委派行为。

## DelegateTask + artifact 通信

每次 Coordinator 调 `DelegateTask` 时：

1. 工具实例化对应 worker（agent_id 必须在 orchestrator 注册表中）
2. 若 worker 标记为 `deterministic: true`，绕过 LLM，直接调它唯一注册的工具，`task_inputs` 中的路径字符串自动 `Read` 解析
3. 否则按 LLM 路径走（`agent.run(task_description)`）
4. 把 worker 完整输出写到 `<workspace>/worker_results/NNN_<agent>.json`
5. 返回紧凑引用 `{output_path, content_chars, content_preview}` 给 Coordinator

下游步骤通过这些 `output_path` 字符串引用上游产物，避免把全量内容塞回
Coordinator 上下文。这是 Slice 1.18 引入的关键架构属性。

## Plan 模板的角色

`config/plans/*.yaml` 是 plan 模板，**不是** 执行计划。
`gptase chat -p <plan_id>` 在 session 起点把模板展开成 prompt：

- 顺序步骤 → "Step N — DelegateTask(agent_id=..., ...)"
- `replicas: N` → "Issue N parallel DelegateTask calls in ONE assistant message"
- `parallel_with: [other_id]` → 同一 group 渲染相邻
- `optional: true` → "IF condition X, SKIP"
- `deterministic` agent → "task_inputs 字段会自动 Read 路径"

Coordinator 按这些指示自主调度 — 不再有 PlanManager 这个执行器，
不再有 DAG 解析或 checkpoint 机制。
