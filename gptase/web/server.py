import json
import logging
import os
from pathlib import Path
from typing import Any, List, Optional

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic import model_validator

from gptase.agents.types import SessionType
from gptase.core.orchestrator import _ORCHESTRATOR_AGENT_ID
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig

_AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "agents"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GPTase Web UI API", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared resources
config = FrameworkConfig()
orchestrator = AgentOrchestrator(config)


# Pydantic Models
class ChatRequest(BaseModel):
    agent_id: str
    query: str
    session_id: Optional[str] = None
    session_type: str = "chat"
    image_paths: Optional[List[str]] = None
    auto_execute: bool = False

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_message_field(cls, data: Any) -> Any:
        """Accept `message` as alias for `query` for backward compatibility."""
        if isinstance(data, dict) and "message" in data and "query" not in data:
            data = dict(data)
            data["query"] = data.pop("message")
        return data


# API Routes
@app.get("/api/agents")
async def list_agents():
    """List all available agents."""
    agents = await orchestrator.list_available_agents()
    return [{
        "id": _ORCHESTRATOR_AGENT_ID,
        "name": "Orchestrator",
        "description": "Coordinator 入口，负责创建 session 并调度 worker",
    }] + [{
        "id": agent["agent_id"],
        "name": agent["agent_id"],
        "description": agent.get("description", ""),
    } for agent in agents]


@app.post("/api/chat")
async def chat_with_agent(request: ChatRequest):
    """Send a message in chat/agent mode without creating a plan session."""
    try:
        if request.session_type not in {"chat", "agent"}:
            raise ValueError(f"Unsupported session_type: {request.session_type}")

        return await orchestrator.execute_direct_session(
            session_type=SessionType(request.session_type),
            query=request.query,
            agent_id=request.agent_id,
            session_id=request.session_id,
            image_paths=request.image_paths,
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def list_sessions():
    """List recent harness sessions."""
    return await orchestrator.list_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session status."""
    status = await orchestrator.get_session_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found")
    return status


@app.get("/api/memory/{agent_id}")
async def get_agent_memory(agent_id: str):
    """Get the compressed working memory for a named agent."""
    try:
        return await orchestrator.get_agent_working_memory(agent_id)
    except Exception as e:
        logger.error(f"Agent memory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/evals")
async def list_eval_agents():
    """List all agents that have eval trace files."""
    result = []
    if not _AGENTS_DIR.exists():
        return result
    for agent_dir in sorted(_AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        output_dir = agent_dir / "evals" / "output"
        traces = sorted(output_dir.glob("trace_*.json")) if output_dir.exists() else []
        if not traces:
            continue
        try:
            with open(traces[-1], encoding="utf-8") as f:
                summary = json.load(f).get("summary", {})
        except Exception:
            summary = {}
        result.append({
            "agent_name": agent_dir.name,
            "trace_count": len(traces),
            "latest_timestamp": summary.get("timestamp", ""),
            "latest_model": summary.get("model", ""),
            "latest_status": summary.get("final_status", ""),
        })
    return result


@app.get("/api/evals/{agent_name}/traces")
async def list_agent_traces(agent_name: str):
    """List trace summaries (no steps) for an agent, newest first."""
    output_dir = _AGENTS_DIR / agent_name / "evals" / "output"
    if not output_dir.exists():
        return []
    traces = []
    for trace_file in sorted(output_dir.glob("trace_*.json"), reverse=True):
        try:
            with open(trace_file, encoding="utf-8") as f:
                data = json.load(f)
            summary = data.get("summary", {})
            summary["filename"] = trace_file.name
            summary["step_count"] = len(data.get("steps", []))
            traces.append(summary)
        except Exception:
            continue
    return traces


@app.get("/api/evals/{agent_name}/traces/{filename}")
async def get_trace(agent_name: str, filename: str):
    """Get a full trace file including all steps."""
    if not filename.startswith("trace_") or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid trace filename")
    trace_file = _AGENTS_DIR / agent_name / "evals" / "output" / filename
    if not trace_file.exists():
        raise HTTPException(status_code=404, detail="Trace not found")
    with open(trace_file, encoding="utf-8") as f:
        data = json.load(f)
    data["summary"]["filename"] = filename
    return data


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """WebSocket for streaming direct chat responses."""
    await websocket.accept()
    try:
        payload = await websocket.receive_json()
        session_type = SessionType(payload.get("session_type", "chat"))
        if session_type != SessionType.CHAT:
            raise ValueError("Streaming websocket currently supports chat mode only")

        async for event in orchestrator.stream_direct_session(
                session_type=session_type,
                query=str(payload.get("query") or ""),
                agent_id=payload.get("agent_id"),
                session_id=payload.get("session_id")):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        await websocket.send_json({"type": "error", "data": {"error": str(e)}})


# Mount static files for the UI
ui_dist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            "ui", "dist")

if os.path.exists(ui_dist_path):
    assets_path = os.path.join(ui_dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)

        index_file = os.path.join(ui_dist_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"error": "UI build not found. Run 'cd ui && npm run build'"}
else:

    @app.get("/")
    async def root_info():
        return {"info": "GPTase API is running. UI not built."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
