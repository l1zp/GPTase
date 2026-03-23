# Web UI API

> [Home](../README.md) → [Common Tasks](../common-tasks.md) → Web UI API

GPTase Web UI is built on FastAPI, providing REST API and WebSocket interfaces.

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

Returns all available agents. The first one is the Auto orchestrator.

**Response:**

```json
[
  {"id": "auto", "name": "Auto (Orchestrator)"},
  {"id": "enzyme-kinetics-extractor", "name": "enzyme-kinetics-extractor"},
  {"id": "vision-image-analyzer", "name": "vision-image-analyzer"}
]
```

---

### List Plans

```
GET /api/plans
```

Returns all available Plan workflows.

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

**Response:**

```json
{
  "plan_id": "enzyme_extraction_pipeline",
  "name": "Enzyme Extraction Pipeline",
  "version": "1.0",
  "workflow": [
    {"step_id": "1", "agent": "document-structure-analyzer", "action": "analyze"},
    {"parallel": [
      {"step_id": "2a", "agent": "vision-image-analyzer"},
      {"step_id": "2b", "agent": "enzyme-kinetics-extractor"}
    ]},
    {"step_id": "3", "agent": "literature-synthesis"}
  ]
}
```

---

### Chat with Agent

```
POST /api/chat
```

Send a message to a specific agent.

**Request Body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | Agent ID, use `auto` for automatic orchestration |
| `message` | string | Yes | User message |
| `image_paths` | string[] | No | List of image paths (multimodal tasks) |

**Request Example:**

```json
{
  "agent_id": "enzyme-kinetics-extractor",
  "message": "Extract Km and kcat values from this text...",
  "image_paths": ["/path/to/figure.png"]
}
```

**Response:**

```json
{
  "status": "success",
  "data": {
    "content": "Extracted kinetic parameters:\n- Km: 0.5 mM\n- kcat: 120 s^-1"
  },
  "agent_id": "enzyme-kinetics-extractor"
}
```

**Error Response:**

```json
{
  "status": "error",
  "error": "Agent not found: unknown-agent"
}
```

---

### Start Harness Session From A Draft Plan

```
POST /api/plan/run
```

Start a harness session using a predefined draft plan.

**Request Body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `plan_id` | string | Yes | Plan workflow ID |
| `input_data` | object | Yes | Input data dictionary |
| `document_path` | string | No | Workspace/document path |
| `auto_execute` | boolean | No | Execute immediately instead of waiting for approval |
| `auto_replan` | boolean | No | Allow automatic follow-up drafts if the goal is not yet met |

**Request Example:**

```json
{
  "plan_id": "enzyme_extraction_pipeline",
  "input_data": {
    "text": "Full paper content..."
  },
  "document_path": "/path/to/paper_dir",
  "auto_execute": true
}
```

**Response:**

```json
{
  "session_id": "goal_20240301_120000_abc12345",
  "status": "completed",
  "current_plan": {...}
}
```

---

### List Sessions

```
GET /api/sessions
```

Returns recent harness sessions.

**Response:**

```json
[
  {
    "session_id": "goal_20240301_120000_abc12345",
    "goal": "Analyze this paper",
    "status": "awaiting_approval",
    "current_plan_id": "enzyme_extraction_pipeline"
  }
]
```

---

### Get Session Status

```
GET /api/sessions/{session_id}
```

Returns detailed status of a specific harness session.

**Response:**

```json
{
  "session_id": "goal_20240301_120000_abc12345",
  "status": "completed",
  "goal": "Analyze this paper",
  "progress": {"total": 3, "completed": 3, "failed": 0},
  "goal_evaluation": {"goal_achieved": true, "next_action": "complete"},
  "task_results": {"1": {...}, "2a": {...}, "2b": {...}}
}
```

### Approve Draft Plan

```
POST /api/sessions/{session_id}/approve
```

Optional body:

```json
{"feedback": "Revise the draft before executing"}
```

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

### Harness Real-time Updates

```
WS /ws/plan/{session_id}
```

Receive real-time status updates for harness sessions.

**Message Format:**

```json
{
  "type": "update",
  "data": {
    "session_id": "goal_20240301_120000_abc12345",
    "status": "executing",
    "progress": {"total": 2, "completed": 1, "failed": 0},
    "current_plan": {"plan_id": "enzyme_extraction_pipeline"}
  }
}
```

**Message Types:**

| type | Description |
|---|---|
| `status` | Connection status confirmation |
| `update` | Execution progress update |

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend Framework | FastAPI |
| ASGI Server | Uvicorn |
| Frontend Framework | React + TypeScript |
| Build Tool | Vite |
| UI Components | Lucide Icons, React Markdown |

---

## Frontend Development

```bash
cd ui

# Install dependencies
npm install

# Development mode
npm run dev

# Build for production
npm run build
```

Build output is in `ui/dist/`, served as static files by FastAPI.

---

*Next level of detail: [internals/ →](../internals/execution-flow.md)*
