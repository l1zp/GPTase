# Web UI API

> [首页](../README.md) → [常见任务](../common-tasks.md) → Web UI API

GPTase Web UI 基于 FastAPI 构建，提供 REST API 和 WebSocket 接口。
系统有三种执行模式：Agent（直接执行）、Coordinator（orchestrator 循环 + 委派 + Plan handoff）、
Plan（结构化工作流执行）。

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

返回所有可用 Agent，第一个是 Orchestrator（coordinator agent）。

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

返回所有可用 Plan 工作流。

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
| `agent_id` | string | 是 | Agent ID。使用 `auto` 启用 Coordinator 模式 |
| `message` | string | 是 | 用户消息 |
| `image_paths` | string[] | 否 | 多模态任务的图片路径 |
| `auto_execute` | boolean | 否 | 仅在 `agent_id="auto"` 时生效。如果 runtime handoff 到 plan，`true` 表示直接执行，`false` 表示先返回 draft 结果 |

### `agent_id="auto"` 的行为

Coordinator 模式运行 orchestrator agent 循环，可以走以下三条路径之一：

1. 直接返回最终答案
   `execution_mode="auto"`
2. 经过 coordinator loop 和 worker delegation 后返回最终答案
   `execution_mode="coordinator"`
3. runtime 判断需要结构化执行，handoff 成 Plan 执行 / draft plan
   响应中不包含 `execution_mode`，而是包含 `status: "draft"` 或 `status: "completed"`

前两条路径都会直接返回结果，不带 `session_id`。Plan 执行结果直接内联返回（不做 session 持久化）。

### 值得关注的响应字段

| 字段 | 位置 | 含义 |
|---|---|---|
| `execution_mode` | 顶层 | `direct`、`auto` 或 `coordinator` |
| `status` | Plan 执行响应 | `draft`（审核模式）或 `completed` / `blocked` / `needs_input` |
| `current_plan` | Plan 执行响应 | 解析后的 Plan 对象 |
| `goal_evaluation` | 已完成的 Plan 响应 | 目标是否达成 |
| `trace.runtime.stop_reason` | `trace.runtime` | runtime 的结束原因，例如 `final_answer` 或 `needs_plan` |
| `trace.runtime.turn_count` | `trace.runtime` | interactive runtime 的轮次数 |
| `trace.runtime.turns` | `trace.runtime` | 每轮 assistant/tool 调用轨迹 |
| `trace.runtime.plan_handoff` | `trace.runtime` | runtime 返回 `needs_plan` 时的结构化 handoff proposal |
| `trace.runtime.coordinator` | `trace.runtime` | coordinator summary，包含 delegated workers 和 coordinator turns |

### 示例：Coordinator 直接回答

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
  "execution_mode": "coordinator",
  "timestamp": "2026-04-01T12:00:00"
}
```

### 示例：Coordinator handoff 成 draft plan

```json
{
  "status": "draft",
  "goal": "Ship the feature",
  "current_plan": {
    "plan_id": "draft_from_handoff"
  },
  "progress": {"total": 1, "completed": 0, "failed": 0},
  "preflight": {
    "status": "warning",
    "warnings": [],
    "errors": []
  },
  "timestamp": "2026-04-01T12:00:00"
}
```

---

### 执行 Plan

```
POST /api/plan/run
```

从显式提供的 `plan_id` 执行 Plan。这个接口用于用户明确指定的
工作流；它和 `POST /api/chat` 中 `agent_id="auto"` 触发的 coordinator
handoff 路径是两回事。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `plan_id` | string | 是 | Plan 工作流 ID |
| `input_data` | object | 是 | 输入数据字典 |
| `document_path` | string | 否 | 工作目录 / 文档路径 |
| `auto_execute` | boolean | 否 | 是否立即执行（默认 `true`） |
| `auto_replan` | boolean | 否 | 目标未达成时是否允许自动补充后续 Plan |

**响应说明：**

返回 Plan 执行结果，常见字段包括 `status`、`goal`、`current_plan`、`progress`、
`task_results`、`goal_evaluation` 和 `preflight`。

---

### 列出 Session

```
GET /api/sessions
```

返回最近的 chat 和 agent session。Plan session 不做持久化。

---

### 获取 Session 状态

```
GET /api/sessions/{session_id}
```

返回指定直接 session（chat 或 agent）的最新状态。
Plan session 不做持久化，对 plan session ID 返回 `null`。

**响应示例（直接 session）：**

```json
{
  "session_id": "chat_20260401_120000_abc12345",
  "session_type": "chat",
  "status": "completed",
  "goal": "分析这篇论文",
  "selected_agent_id": "chat",
  "messages": [...],
  "traces": [...],
  "created_at": "2026-04-01T12:00:00",
  "updated_at": "2026-04-01T12:00:01"
}
```

---

### 审核 Draft Plan

```
POST /api/sessions/{session_id}/approve
```

可选请求体：

```json
{"feedback": "先修订 plan 再执行"}
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

### Plan 实时更新

```
WS /ws/plan/{session_id}
```

接收 Plan 执行的状态更新。不会流式返回 coordinator 直接回答或 coordinator loop
请求，因为这两条路径直接内联返回结果。
