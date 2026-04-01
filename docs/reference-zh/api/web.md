# Web UI API

> [首页](../README.md) → [常见任务](../common-tasks.md) → Web UI API

GPTase Web UI 基于 FastAPI 构建，提供 REST API 和 WebSocket 接口。
当前最重要的运行时差异是：`agent_id="auto"` 不再只有一种结果，而可能是直接回答、
经过 coordinator loop 后回答，或者 runtime handoff 成 harness session。

## 启动服务

```bash
# 构建前端（首次）
cd ui && ./build.sh

# 启动服务
gptase web --port 8000 --host 127.0.0.1
```

默认地址：`http://127.0.0.1:8000`

---

## REST API

### 列出 Agent

```
GET /api/agents
```

返回所有可用 Agent，第一个是 Auto orchestrator。

**响应示例：**

```json
[
  {"id": "orchestrator", "name": "Orchestrator"},
  {"id": "enzyme-kinetics-extractor", "name": "enzyme-kinetics-extractor"},
  {"id": "vision-image-analyzer", "name": "vision-image-analyzer"}
]
```

---

### 列出 Plan

```
GET /api/plans
```

返回所有可用 draft plan 工作流。

---

### 获取 Plan 定义

```
GET /api/plans/{plan_id}
```

返回指定 Plan 的完整定义。

---

### 与 Agent 对话

```
POST /api/chat
```

向指定 worker agent 发送消息，或将任务提交给 orchestrator runtime。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `agent_id` | string | 是 | Agent ID。使用 `auto` 启用 Auto orchestrator |
| `message` | string | 是 | 用户消息 |
| `image_paths` | string[] | 否 | 多模态任务的图片路径 |
| `auto_execute` | boolean | 否 | 仅在 `agent_id="auto"` 时生效。如果 runtime handoff 到 plan，`true` 表示直接执行，`false` 表示先返回 draft session 等审核 |

### `agent_id="auto"` 的行为

Auto orchestrator 会先运行 interactive runtime，再走以下三条路径之一：

1. 直接返回最终答案
   `execution_mode="auto"`
2. 经过 coordinator loop 和 worker delegation 后返回最终答案
   `execution_mode="coordinator"`
3. runtime 判断需要结构化执行，handoff 成 harness session / draft plan
   `execution_mode="harness"`

只有第三条路径会创建 harness session。前两条路径都会直接返回结果，不带 `session_id`。

### 值得关注的响应字段

| 字段 | 位置 | 含义 |
|---|---|---|
| `execution_mode` | 顶层 | `direct`、`auto`、`coordinator` 或 `harness` |
| `trace.runtime.stop_reason` | `trace.runtime` | runtime 的结束原因，例如 `final_answer` 或 `needs_plan` |
| `trace.runtime.turn_count` | `trace.runtime` | interactive runtime 的轮次数 |
| `trace.runtime.turns` | `trace.runtime` | 每轮 assistant/tool 调用轨迹 |
| `trace.runtime.plan_handoff` | `trace.runtime` | runtime 返回 `needs_plan` 时的结构化 handoff proposal |
| `trace.runtime.coordinator` | `trace.runtime` | coordinator summary，包含 delegated workers 和 coordinator turns |
| `handoff` | harness 顶层响应 | 持久化到 session 里的 handoff proposal |
| `coordinator` | harness 顶层响应 | 持久化到 session 里的 coordinator summary |

### 示例：Auto 直接回答

```json
{
  "task_id": "task_1710000000.0",
  "status": "success",
  "data": {
    "content": "Direct answer"
  },
  "trace": {
    "runtime": {
      "stop_reason": "final_answer",
      "turn_count": 1,
      "turns": [],
      "resume_supported": true,
      "plan_handoff": null,
      "coordinator": null
    }
  },
  "agent_id": "auto",
  "execution_mode": "auto",
  "timestamp": "2026-04-01T12:00:00"
}
```

### 示例：Auto handoff 成 draft harness session

```json
{
  "session_id": "goal_20260401_120000_abc12345",
  "status": "awaiting_approval",
  "goal": "Ship the feature",
  "draft_source": "runtime_handoff",
  "current_plan": {
    "plan_id": "draft_from_handoff"
  },
  "handoff": {
    "reason": "Need a DAG",
    "goal": "Ship the feature",
    "planning_context": "Found multiple dependent steps",
    "evidence_summary": "Need staged execution",
    "suggested_next_step": "Create a plan"
  },
  "coordinator": {
    "turn_count": 2,
    "delegation_count": 2,
    "delegated_agents": ["code-analyzer", "document-structure-analyzer"],
    "worker_results": [],
    "turns": []
  },
  "preflight": {
    "status": "warning",
    "warnings": [],
    "errors": []
  },
  "execution_mode": "harness",
  "timestamp": "2026-04-01T12:00:00"
}
```

---

### 从 Draft Plan 启动 Harness Session

```
POST /api/plan/run
```

从显式提供的 draft plan 启动 harness session。这个接口用于用户明确指定的
`plan_id` 工作流；它和 `POST /api/chat` 中 `agent_id="auto"` 触发的 runtime
handoff 路径是两回事。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `plan_id` | string | 是 | Draft plan 工作流 ID |
| `input_data` | object | 是 | 输入数据字典 |
| `document_path` | string | 否 | 工作目录 / 文档路径 |
| `auto_execute` | boolean | 否 | 是否立即执行，而不是停在审核状态 |
| `auto_replan` | boolean | 否 | 目标未达成时是否允许自动补充后续 draft |

**响应说明：**

返回 harness session payload，常见字段包括 `session_id`、`status`、`current_plan`、
`draft_source`、`preflight`、`task_results`、`task_traces`、`handoff`、
`coordinator` 和 `execution_mode`。

---

### 列出 Session

```
GET /api/sessions
```

返回最近的 harness session。

---

### 获取 Session 状态

```
GET /api/sessions/{session_id}
```

返回指定 harness session 的最新持久化状态。

**响应示例：**

```json
{
  "session_id": "goal_20260401_120000_abc12345",
  "status": "completed",
  "goal": "分析这篇论文",
  "draft_source": "provided",
  "current_plan": {
    "plan_id": "enzyme_extraction_pipeline"
  },
  "plan_history": [],
  "progress": {"total": 3, "completed": 3, "failed": 0},
  "goal_evaluation": {"goal_achieved": true, "next_action": "complete"},
  "task_results": {"1": {}, "2a": {}, "2b": {}},
  "task_traces": {"1": {}, "2a": {}, "2b": {}},
  "active_tasks": {},
  "latest_error": null,
  "handoff": null,
  "coordinator": null,
  "preflight": {"status": "ok", "warnings": [], "errors": []},
  "execution_mode": "harness",
  "timestamp": "2026-04-01T12:00:00"
}
```

---

### 审核 Draft Plan

```
POST /api/sessions/{session_id}/approve
```

可选请求体：

```json
{"feedback": "先修订 draft 再执行"}
```

---

### 继续 Session 并提供反馈

```
POST /api/sessions/{session_id}/input
```

请求体：

```json
{"feedback": "目标还没达到，再增加一轮汇总"}
```

---

## WebSocket

### Harness 实时更新

```
WS /ws/plan/{session_id}
```

用于接收已经创建好的 harness session 的状态更新。它不会流式返回 direct `auto`
请求或 coordinator-only 请求，因为这两条路径本身不会创建 session。
