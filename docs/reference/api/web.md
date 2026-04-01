# Web UI API

> [Home](../README.md) → [Common Tasks](../common-tasks.md) → Web UI API

GPTase Web UI is built on FastAPI and exposes both REST and WebSocket endpoints.
The most important runtime distinction is that `agent_id="auto"` can now end in
three different ways: a direct answer, a coordinated answer after worker
delegation, or a harness session created from a runtime handoff.

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

Returns all available agents. The first entry is the Auto orchestrator.

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
| `agent_id` | string | Yes | Agent ID. Use `auto` for the Auto orchestrator |
| `message` | string | Yes | User message |
| `image_paths` | string[] | No | Image paths for multimodal tasks |
| `auto_execute` | boolean | No | Only used with `agent_id="auto"`. If runtime hands off into plan mode, `true` executes immediately and `false` returns a draft session for approval |

### `agent_id="auto"` behavior

The Auto orchestrator runs an interactive runtime first, then chooses one of these paths:

1. Direct answer
   `execution_mode="auto"`
2. Coordinator loop answer after worker delegation
   `execution_mode="coordinator"`
3. Runtime handoff into harness session / draft plan
   `execution_mode="harness"`

Only the third path creates a harness session. Direct and coordinator answers return
immediately without a `session_id`.

### Response fields worth checking

| Field | Where | Meaning |
|---|---|---|
| `execution_mode` | top level | `direct`, `auto`, `coordinator`, or `harness` |
| `trace.runtime.stop_reason` | `trace.runtime` | Terminal runtime state such as `final_answer` or `needs_plan` |
| `trace.runtime.turn_count` | `trace.runtime` | Number of interactive runtime turns |
| `trace.runtime.turns` | `trace.runtime` | Per-turn assistant/tool trace |
| `trace.runtime.plan_handoff` | `trace.runtime` | Structured handoff proposal when runtime returns `needs_plan` |
| `trace.runtime.coordinator` | `trace.runtime` | Coordinator summary, including delegated workers and coordinator turns |
| `handoff` | top level harness response | Persisted handoff proposal on a harness session |
| `coordinator` | top level harness response | Persisted coordinator summary on a harness session |

### Example: Auto returns a direct answer

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

### Example: Auto hands off into a draft harness session

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

### Start Harness Session From A Draft Plan

```
POST /api/plan/run
```

Start a harness session from an explicit draft plan. This endpoint is for
user-provided `plan_id` workflows; it is separate from the runtime handoff path
used by `POST /api/chat` with `agent_id="auto"`.

**Request Body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `plan_id` | string | Yes | Draft plan workflow ID |
| `input_data` | object | Yes | Input data dictionary |
| `document_path` | string | No | Workspace / document path |
| `auto_execute` | boolean | No | Execute immediately instead of waiting for approval |
| `auto_replan` | boolean | No | Allow automatic follow-up drafts if the goal is still unmet |

**Response:**

Returns a harness session payload with fields such as `session_id`, `status`,
`current_plan`, `draft_source`, `preflight`, `task_results`, `task_traces`,
`handoff`, `coordinator`, and `execution_mode`.

---

### List Sessions

```
GET /api/sessions
```

Returns recent harness sessions.

---

### Get Session Status

```
GET /api/sessions/{session_id}
```

Returns the latest persisted state for a harness session.

**Response:**

```json
{
  "session_id": "goal_20260401_120000_abc12345",
  "status": "completed",
  "goal": "Analyze this paper",
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

### Harness Realtime Updates

```
WS /ws/plan/{session_id}
```

Receives status updates for harness sessions after the session already exists.
This does not stream direct `auto` or coordinator-only requests because those
paths do not create a session.
