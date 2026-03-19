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

### Start Plan Execution

```
POST /api/plan/run
```

Start an Plan workflow execution in the background.

**Request Body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `plan_id` | string | Yes | Plan workflow ID |
| `input_data` | object | Yes | Input data dictionary |
| `document_path` | string | No | Document path |

**Request Example:**

```json
{
  "plan_id": "enzyme_extraction_pipeline",
  "input_data": {
    "text": "Full paper content..."
  },
  "document_path": "/path/to/paper_dir"
}
```

**Response:**

```json
{
  "session_id": "plan_web_a1b2c3d4",
  "status": "started"
}
```

---

### List Sessions

```
GET /api/sessions
```

Returns recent Plan execution sessions.

**Response:**

```json
[
  {
    "session_id": "plan_web_a1b2c3d4",
    "plan_id": "enzyme_extraction_pipeline",
    "status": "completed",
    "progress": 100,
    "completed_steps": 3,
    "total_steps": 3,
    "created_at": "2024-03-10T12:00:00"
  },
  {
    "session_id": "plan_web_e5f6g7h8",
    "plan_id": "literature_review",
    "status": "running",
    "progress": 50,
    "completed_steps": 1,
    "total_steps": 2,
    "created_at": "2024-03-10T12:30:00"
  }
]
```

---

### Get Session Status

```
GET /api/sessions/{session_id}
```

Returns detailed status of a specific session.

**Response:**

```json
{
  "session_id": "plan_web_a1b2c3d4",
  "plan_id": "enzyme_extraction_pipeline",
  "status": "completed",
  "progress": 100,
  "completed_steps": 3,
  "total_steps": 3,
  "created_at": "2024-03-10T12:00:00",
  "step_results": {
    "1": {"status": "success", "data": {...}},
    "2a": {"status": "success", "data": {...}},
    "2b": {"status": "success", "data": {...}}
  }
}
```

---

## WebSocket

### Plan Real-time Updates

```
WS /ws/plan/{session_id}
```

Receive real-time status updates for Plan execution.

**Message Format:**

```json
{
  "type": "update",
  "data": {
    "session_id": "plan_web_a1b2c3d4",
    "status": "running",
    "progress": 50,
    "completed_steps": 1,
    "total_steps": 2
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
