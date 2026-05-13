# Web UI API

> [首页](../README.md) → [常见任务](../common-tasks.md) → Web UI API

GPTase Web UI 基于 FastAPI 构建，提供 REST API 和 WebSocket 接口。
系统有两种执行模式：Agent（直接执行单个 worker）、Coordinator
（orchestrator 循环 + DelegateTask 委派）。Slice 4 移除了 plan-mode 端点；
要运行 plan 模板请用 CLI `gptase chat -p <plan_id> -i <doc>`。

## 启动服务

```bash
# 构建前端（首次）
cd ui && bash build.sh

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
  {"id": "chat", "name": "chat"},
  {"id": "enzyme-kinetics-table-extractor", "name": "enzyme-kinetics-table-extractor"}
]
```

---

### 与 Agent 对话

```
POST /api/chat
```

向单个 worker agent 或 chat agent 发送一条消息。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `agent_id` | string | 是 | Agent ID（例如 `chat` 或某个 worker） |
| `query` | string | 是 | 用户消息（兼容旧字段名 `message`） |
| `session_id` | string | 否 | 已有 session ID（用于继续对话） |
| `session_type` | string | 否 | `chat`（默认）或 `agent`；`plan` 不再支持 |
| `image_paths` | string[] | 否 | 多模态消息的图片路径 |
| `auto_execute` | boolean | 否 | 保留字段，主要走流式入口 |

> **注意：** Coordinator 编排（多步 worker delegation）目前从 CLI
> `gptase chat` 进入；Web `/api/chat` 端点专门跑直接 chat / agent session。

---

### 列出 Session

```
GET /api/sessions
```

返回最近 20 条 session（chat 或 agent 模式）。

---

### 获取 Session 详情

```
GET /api/sessions/{session_id}
```

返回 session 的最新状态：消息历史、trace、状态码等。

**响应示例：**

```json
{
  "session_id": "chat_20260508_120000_abc12345",
  "session_type": "chat",
  "status": "completed",
  "goal": "分析这篇论文",
  "selected_agent_id": "chat",
  "messages": [...],
  "traces": [...],
  "created_at": "2026-05-08T12:00:00",
  "updated_at": "2026-05-08T12:00:01"
}
```

---

### Agent 工作记忆

```
GET /api/memory/{agent_id}
```

返回指定 agent 的压缩工作记忆（summary + metadata + last_updated）。

---

### Eval Trace 列表与详情

```
GET /api/evals
GET /api/evals/{agent_name}/traces
GET /api/evals/{agent_name}/traces/{filename}
```

读取 `.claude/agents/<name>/evals/output/trace_*.json` 数据，给前端
评估面板使用。

---

## WebSocket

### Chat 流式响应

```
WS /ws/chat
```

接收 chat 模式的流式输出。客户端先发一条 JSON：

```json
{
  "agent_id": "chat",
  "query": "你好",
  "session_id": "chat_20260508_...",
  "session_type": "chat"
}
```

服务端事件类型：

| `type` | 说明 |
|---|---|
| `chunk` | 增量文本块（`data.delta` 是字符串） |
| `done` | 完整 session detail |
| `error` | 错误（前端会自动 fallback 到 `POST /api/chat`） |

> **提示：** 当前只有 `session_type="chat"` 走流式；`agent` 模式直接
> 用 HTTP `POST /api/chat`。
