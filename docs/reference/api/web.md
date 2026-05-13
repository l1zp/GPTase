# Web UI API

> [Home](../README.md) → [Common Tasks](../common-tasks.md) → Web UI API

GPTase Web UI is built on FastAPI and exposes both REST and WebSocket
endpoints. There are two execution modes: Agent (run a single worker
directly) and Coordinator (orchestrator loop with DelegateTask). Slice 4
removed the plan-mode endpoints; to run a plan template, use the CLI:
`gptase chat -p <plan_id> -i <doc>`.

## Starting the server

```bash
# Build the frontend (first time)
cd ui && bash build.sh

# Start the server
gptase web --port 8000 --host 127.0.0.1
```

Default address: `http://127.0.0.1:8000`

---

## REST API

### List agents

```
GET /api/agents
```

Returns the available agents. The first entry is `orchestrator`
(the coordinator entry point).

**Example response:**

```json
[
  {"id": "orchestrator", "name": "Orchestrator"},
  {"id": "chat", "name": "chat"},
  {"id": "enzyme-kinetics-table-extractor", "name": "enzyme-kinetics-table-extractor"}
]
```

---

### Chat with an agent

```
POST /api/chat
```

Send a single message to a worker agent or the chat agent.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | Agent ID (e.g. `chat` or any worker) |
| `query` | string | Yes | User message (legacy `message` field also accepted) |
| `session_id` | string | No | Existing session ID for continuation |
| `session_type` | string | No | `chat` (default) or `agent`; `plan` is rejected |
| `image_paths` | string[] | No | Image paths for multimodal messages |
| `auto_execute` | boolean | No | Reserved; streaming WS is the primary path |

> **Note:** Multi-step Coordinator workflows currently enter through
> the CLI (`gptase chat`); the web `/api/chat` endpoint is dedicated to
> direct chat / agent sessions.

---

### List sessions

```
GET /api/sessions
```

Returns the most recent 20 sessions (chat or agent mode).

---

### Get session detail

```
GET /api/sessions/{session_id}
```

Returns the latest snapshot for a session: messages, traces, status.

**Example response:**

```json
{
  "session_id": "chat_20260508_120000_abc12345",
  "session_type": "chat",
  "status": "completed",
  "goal": "Analyze this paper",
  "selected_agent_id": "chat",
  "messages": [...],
  "traces": [...],
  "created_at": "2026-05-08T12:00:00",
  "updated_at": "2026-05-08T12:00:01"
}
```

---

### Agent working memory

```
GET /api/memory/{agent_id}
```

Returns the compressed working memory for an agent (summary + metadata
+ last_updated).

---

### Eval traces

```
GET /api/evals
GET /api/evals/{agent_name}/traces
GET /api/evals/{agent_name}/traces/{filename}
```

Reads `.claude/agents/<name>/evals/output/trace_*.json` for the
frontend's eval panel.

---

## WebSocket

### Streaming chat

```
WS /ws/chat
```

Streaming output for chat mode. The client first sends a JSON payload:

```json
{
  "agent_id": "chat",
  "query": "Hello",
  "session_id": "chat_20260508_...",
  "session_type": "chat"
}
```

Server-side event types:

| `type` | Meaning |
|---|---|
| `chunk` | Incremental text chunk (`data.delta` is a string) |
| `done` | Full session detail |
| `error` | Error (the frontend automatically falls back to `POST /api/chat`) |

> **Tip:** Only `session_type="chat"` streams; `agent` mode uses
> HTTP `POST /api/chat` directly.
