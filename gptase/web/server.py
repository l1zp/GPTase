import asyncio
import csv
from io import StringIO
import json
import logging
from mimetypes import guess_type
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gptase.agents.plan_loader import PlanRegistry
from gptase.agents.types import SessionType
from gptase.core.orchestrator import _ORCHESTRATOR_AGENT_ID
from gptase.core.orchestrator import AgentOrchestrator
from gptase.models.model import Model
from gptase.utils.config import FrameworkConfig
from gptase.web.workspace import _resolve_safe_file_path
from gptase.web.workspace import _resolve_workspace_root_for_document
from gptase.web.workspace import list_workspace_runs
from gptase.web.workspace import WorkspaceArtifact  # noqa: F401 re-exported for tests
from gptase.web.workspace import WorkspaceDocumentResponse
from gptase.web.workspace import WorkspaceRunSummary  # noqa: F401 re-exported for tests
from gptase.web.workspace import \
    WorkspaceTaskSummary  # noqa: F401 re-exported for tests

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
plan_registry = PlanRegistry.get_instance()


# Pydantic Models
class ChatRequest(BaseModel):
    agent_id: str
    message: str
    session_id: Optional[str] = None
    session_type: str = "chat"
    image_paths: Optional[List[str]] = None
    auto_execute: bool = False


class PlanStartRequest(BaseModel):
    plan_id: str
    input_data: Dict[str, Any]
    document_path: Optional[str] = None
    auto_execute: bool = True
    auto_replan: bool = False


class SessionActionRequest(BaseModel):
    feedback: Optional[str] = None
    auto_replan: Optional[bool] = None


# API Routes
@app.get("/api/agents")
async def list_agents():
    """List all available agents."""
    agents = await orchestrator.list_available_agents()
    return [{
        "id": _ORCHESTRATOR_AGENT_ID,
        "name": "Orchestrator",
        "description": "Harness 运行时入口，负责创建 session、draft plan 并调度 worker",
    }] + [{
        "id": agent["agent_id"],
        "name": agent["agent_id"],
        "description": agent.get("description", ""),
    } for agent in agents]


@app.get("/api/plans")
async def list_plans():
    """List all available plans."""
    return plan_registry.list_plans()


@app.get("/api/workspace/plans")
async def list_workspace_plans():
    """List plans available for plan workspace routing."""
    plans = plan_registry.list_plans()
    return [{
        "plan_id": item.get("plan_id"),
        "name": item.get("name"),
        "description": item.get("description"),
    } for item in plans]


@app.get("/api/workspace/document", response_model=WorkspaceDocumentResponse)
async def get_workspace_document(
        plan_id: str = Query(...),
        workspace_root: str = Query(...),
        document_name: str = Query(...),
        run_id: Optional[str] = Query(None),
):
    """Resolve a document workspace for the dedicated plan explorer UI."""
    resolved_root = _resolve_workspace_root_for_document(workspace_root, document_name)
    document_dir = resolved_root / "data" / "input" / document_name
    if not document_dir.exists():
        raise HTTPException(status_code=404,
                            detail=f"Document directory not found: {document_dir}")

    pdf_path = resolved_root / "data" / "input" / "documents" / f"{document_name}.pdf"
    markdown_path = document_dir / f"{document_name}.md"
    images_dir = document_dir / "images"
    runs = list_workspace_runs(resolved_root, document_name, plan_id)

    selected_run = runs[0] if runs else None
    if run_id:
        selected_run = next((run for run in runs if run.run_id == run_id), None)
        if selected_run is None:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    available_plans = sorted({
        plan_dir.name.rsplit("_", 2)[0]
        for plan_dir in (resolved_root / "data" / "output" / document_name).iterdir()
        if plan_dir.is_dir() and "_" in plan_dir.name
    }) if (resolved_root / "data" / "output" / document_name).exists() else []

    return WorkspaceDocumentResponse(
        plan_id=plan_id,
        workspace_root=str(resolved_root),
        document_name=document_name,
        document_dir=str(document_dir),
        pdf_path=str(pdf_path) if pdf_path.exists() else None,
        markdown_path=str(markdown_path) if markdown_path.exists() else None,
        images_dir=str(images_dir) if images_dir.exists() else None,
        runs=runs,
        selected_run_id=selected_run.run_id if selected_run else None,
        selected_run_path=selected_run.run_path if selected_run else None,
        available_plans=available_plans,
    )


@app.get("/api/workspace/file")
async def get_workspace_file(path: str = Query(...)):
    """Serve workspace files with a safe allowlist rooted at configured workspace paths."""
    resolved = _resolve_safe_file_path(path)
    mime_type = guess_type(str(resolved))[0] or "application/octet-stream"
    suffix = resolved.suffix.lower()

    if suffix in {".md", ".txt", ".json", ".csv"}:
        content = resolved.read_text(encoding="utf-8")
        if suffix == ".json":
            return JSONResponse(content=json.loads(content))
        if suffix == ".csv":
            reader = csv.DictReader(StringIO(content))
            rows = list(reader)
            return JSONResponse({
                "type": "csv",
                "columns": reader.fieldnames or [],
                "rows": rows,
                "raw": content,
            })
        return PlainTextResponse(content, media_type="text/plain; charset=utf-8")

    headers = {"Cache-Control": "public, max-age=3600"}
    if suffix in {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        headers["Content-Disposition"] = "inline"
    return FileResponse(resolved, media_type=mime_type, headers=headers)


@app.get("/api/plans/{plan_id}")
async def get_plan_definition(plan_id: str):
    """Get full plan definition."""
    try:
        plan = plan_registry.get_plan(plan_id)
        return plan.model_dump()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/chat")
async def chat_with_agent(request: ChatRequest):
    """Send a message in chat/agent mode without creating a plan session."""
    try:
        if request.session_type not in {"chat", "agent"}:
            raise ValueError(f"Unsupported session_type: {request.session_type}")

        return await orchestrator.execute_direct_session(
            session_type=SessionType(request.session_type),
            message=request.message,
            agent_id=request.agent_id,
            session_id=request.session_id,
            image_paths=request.image_paths,
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plan/run")
async def start_plan(request: PlanStartRequest):
    """Start a harness session from a predefined draft plan."""
    try:
        result = await orchestrator.execute_task({
            "description":
            request.input_data.get("text", f"Execute draft plan {request.plan_id}"),
            "goal":
            request.input_data.get("text", f"Execute draft plan {request.plan_id}"),
            "plan_id":
            request.plan_id,
            "input_data":
            request.input_data,
            "auto_execute":
            request.auto_execute,
            "auto_replan":
            request.auto_replan,
            "document_path":
            request.document_path or request.input_data.get("document_path"),
        })
        return result
    except Exception as e:
        logger.error(f"Plan start error: {e}")
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


@app.post("/api/sessions/{session_id}/approve")
async def approve_session(session_id: str, request: SessionActionRequest):
    """Approve the current draft plan and optionally provide revision feedback."""
    result = await orchestrator.approve_plan(session_id, feedback=request.feedback)
    return result


@app.post("/api/sessions/{session_id}/input")
async def continue_session(session_id: str, request: SessionActionRequest):
    """Provide user feedback to revise or continue a goal session."""
    payload: Dict[str, Any] = {"session_id": session_id}
    if request.feedback:
        payload["feedback"] = request.feedback
    if request.auto_replan is not None:
        payload["auto_replan"] = request.auto_replan
    result = await orchestrator.execute_task(payload)
    return result


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


@app.websocket("/ws/plan/{session_id}")
async def plan_websocket(websocket: WebSocket, session_id: str):
    """WebSocket for real-time plan updates."""
    await websocket.accept()
    try:
        await websocket.send_json({
            "type": "status",
            "data": "connected",
            "session_id": session_id
        })

        # Keep connection open
        while True:
            status = await orchestrator.get_session_status(session_id)
            if status:
                await websocket.send_json({"type": "update", "data": status})

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


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
                message=str(payload.get("message") or ""),
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
