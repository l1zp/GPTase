# Web UI API

> [Home](../README.md) → [Common Tasks](../common-tasks.md) → Web UI API

GPTase Web UI is built on FastAPI and exposes both REST and WebSocket endpoints.
The system has three execution modes: Agent (direct execution), Coordinator
(orchestrator loop with delegation and plan handoff), and Plan (structured
workflow execution).

## Start Server

```bash
# Build frontend (first time)
cd ui && ./build.sh

# Start server
gptase web --port 8000 --host 127.0.0.1
```

Default URL: `http://127.0.0.1:8000`

---

## REST API

### List Agents

```
GET /api/agents
```

Returns all available agents. The first entry is the Orchestrator (coordinator agent).

**Response:**

```json
[
  {"id": "orchestrator", "name": "Orchestrator"},
  {"id": "enzyme-kinetics-extractor", "name": "enzyme-kinetics-extractor"},
  {"id": "vision-image-analyzer", "name": "vision-image-analyzer"}
]
```

---

### List Plans

```
GET /api/plans
```

Returns all available draft plan workflows.

**Response:**

```json
[
  {"plan_id": "enzyme_extraction_pipeline", "name": "Enzyme Extraction Pipeline", "version": "1.0"},
  {"plan_id": "literature_review", "name": "Literature Review", "version": "1.0"}
]
```

---

### Get Plan Definition

```
GET /api/plans/{plan_id}
```

Returns the full definition of a specific Plan.

---

### Chat With Agent

```
POST /api/chat
```

Send a message to a worker agent, or submit a task to the orchestrator runtime.

**Request Body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | Agent ID. Use `auto` for Coordinator mode |
| `message` | string | Yes | User message |
| `image_paths` | string[] | No | Image paths for multimodal tasks |
| `auto_execute` | boolean | No | Only used with `agent_id="auto"`. If runtime hands off into plan mode, `true` executes immediately and `false` returns a draft session for approval |

### `agent_id="auto"` behavior

Coordinator mode runs the orchestrator agent in a loop, choosing one of these paths:

1. Direct answer
   `execution_mode="auto"`
2. Coordinator loop answer after worker delegation
   `execution_mode="coordinator"`
3. Runtime handoff into plan execution / draft plan
   `execution_mode` is omitted; response contains `status: "draft"` or `status: "completed"`

Direct and coordinator answers return immediately without a `session_id`.
Plan execution results are returned inline, and resumable plan checkpoints are
persisted internally to SQLite.

### Response fields worth checking

| Field | Where | Meaning |
|---|---|---|
| `execution_mode` | top level | `direct`, `coordinator`, or omitted (plan mode) |
| `trace.runtime.stop_reason` | `trace.runtime` | Terminal runtime state such as `final_answer` or `needs_plan` |
| `trace.runtime.turn_count` | `trace.runtime` | Number of interactive runtime turns |
| `trace.runtime.turns` | `trace.runtime` | Per-turn assistant/tool trace |
| `trace.runtime.plan_handoff` | `trace.runtime` | Structured handoff proposal when runtime returns `needs_plan` |
| `trace.runtime.coordinator` | `trace.runtime` | Coordinator summary, including delegated workers and coordinator turns |
| `status` | plan execution response | `draft` (review mode) or `completed` / `blocked` / `needs_input` |
| `current_plan` | plan execution response | The resolved Plan object |
| `goal_evaluation` | completed plan response | Whether the goal was achieved |

### Example: Coordinator returns a direct answer

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

### Example: Coordinator hands off into a draft plan

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

### Execute a Plan

```
POST /api/plan/run
```

Execute a plan from an explicit `plan_id`. This endpoint is for user-provided
workflows; it is separate from the coordinator handoff path used by
`POST /api/chat` with `agent_id="auto"`.

**Request Body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `plan_id` | string | Yes | Draft plan workflow ID |
| `input_data` | object | Yes | Input data dictionary |
| `document_path` | string | No | Workspace / document path |
| `auto_execute` | boolean | No | Execute immediately instead of waiting for approval |
| `auto_replan` | boolean | No | Allow automatic follow-up drafts if the goal is still unmet |

**Response:**

Returns a plan execution result with fields such as `status`, `goal`,
`current_plan`, `progress`, `task_results`, `goal_evaluation`, and `preflight`.

---

### List Sessions

```
GET /api/sessions
```

Returns recent direct sessions (chat and agent). This endpoint does not list
plan sessions; plan runtime state is stored separately as SQLite checkpoints.

---

### Get Session Status

```
GET /api/sessions/{session_id}
```

Returns the latest state for a direct (chat or agent) session.
Plan sessions are stored as checkpoints rather than direct sessions, so this
endpoint returns `null` for plan session IDs.

**Response (direct session):**

```json
{
  "session_id": "chat_20260401_120000_abc12345",
  "session_type": "chat",
  "status": "completed",
  "goal": "Analyze this paper",
  "selected_agent_id": "chat",
  "messages": [...],
  "traces": [...],
  "created_at": "2026-04-01T12:00:00",
  "updated_at": "2026-04-01T12:00:01"
}
```

---

### Approve Draft Plan

```
POST /api/sessions/{session_id}/approve
```

Optional body:

```json
{"feedback": "Revise the draft before executing"}
```

---

### Continue Session With User Input

```
POST /api/sessions/{session_id}/input
```

Body:

```json
{"feedback": "The goal is not met yet. Add one more synthesis pass."}
```

---

## WebSocket

### Plan Realtime Updates

```
WS /ws/plan/{session_id}
```

Receives status updates for plan execution. This does not stream coordinator
direct answers or coordinator loop requests because those paths return results inline.
