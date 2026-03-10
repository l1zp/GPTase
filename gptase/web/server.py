import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gptase.agents.base import Agent
from gptase.core.orchestrator import AgentOrchestrator
from gptase.models.model import Model
from gptase.sop.orchestrator_agent import SOPOrchestratorAgent
from gptase.utils.config import FrameworkConfig

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
model_manager = Model()
sop_orchestrator = SOPOrchestratorAgent(model_manager=model_manager)
agent_orchestrator = AgentOrchestrator(config=config)


# Pydantic Models
class ChatRequest(BaseModel):
    agent_id: str
    message: str
    image_paths: Optional[List[str]] = None


class SOPStartRequest(BaseModel):
    plan_id: str
    input_data: Dict[str, Any]
    document_path: Optional[str] = None


# API Routes
@app.get("/api/agents")
async def list_agents():
    """List all available agents, adding Auto-Orchestrator as the first option."""
    from gptase.agents.base import _DEFAULT_CONFIG_DIR
    agents = [{"id": "auto", "name": "✨ Auto (Orchestrator)"}]
    if _DEFAULT_CONFIG_DIR.exists():
        for f in _DEFAULT_CONFIG_DIR.glob("*.md"):
            try:
                # Try to get agent info without full loading if possible
                # For now, just return names
                agents.append({"id": f.stem, "name": f.stem})
            except Exception:
                pass
    return agents


@app.get("/api/sops")
async def list_sops():
    """List all available SOPs."""
    return sop_orchestrator.list_available_sops()


@app.get("/api/sops/{plan_id}")
async def get_sop_definition(plan_id: str):
    """Get full SOP definition."""
    try:
        sop = sop_orchestrator.get_sop(plan_id)
        # Convert SOPDefinition to dict for JSON serialization
        # (This might need manual mapping if model_dump is not available)
        return json.loads(json.dumps(sop, default=lambda o: o.__dict__))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/chat")
async def chat_with_agent(request: ChatRequest):
    """Send a message to a specific agent or let the orchestrator handle it."""
    try:
        if request.agent_id == "auto":
            # Use AgentOrchestrator for automated handling
            task = {"description": request.message, "image_paths": request.image_paths}
            result = await agent_orchestrator.execute_task(task)

            # Adapt AgentOrchestrator response to Chat UI format
            if result.get("status") == "failed":
                return {"status": "error", "error": result.get("error")}

            # Extract content from result
            data = result.get("data", {})
            content = ""
            if isinstance(data, dict):
                content = data.get("content", str(data))
            else:
                content = str(data)

            return {
                "status": "success",
                "data": {
                    "content": content
                },
                "agent_id": result.get("agent_id")
            }
        else:
            # Direct agent call
            agent = Agent.from_markdown(request.agent_id, model_manager=model_manager)
            result = await agent.run(request.message, image_paths=request.image_paths)
            return result
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sop/run")
async def start_sop(request: SOPStartRequest, background_tasks: BackgroundTasks):
    """Start an SOP execution in the background."""
    try:
        session_id = f"sop_web_{os.urandom(4).hex()}"

        # Run execution in background
        background_tasks.add_task(sop_orchestrator.execute_sop,
                                  plan_id=request.plan_id,
                                  input_data=request.input_data,
                                  document_path=request.document_path,
                                  session_id=session_id)

        return {"session_id": session_id, "status": "started"}
    except Exception as e:
        logger.error(f"SOP start error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def list_sessions():
    """List recent SOP sessions."""
    return await sop_orchestrator.list_sessions(limit=20)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session status."""
    status = await sop_orchestrator.get_session_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found")
    return status


@app.websocket("/ws/sop/{session_id}")
async def sop_websocket(websocket: WebSocket, session_id: str):
    """WebSocket for real-time SOP updates."""
    await websocket.accept()
    try:
        # In a real implementation, we'd subscribe to events for this session
        # For prototype, we just send a "connected" message
        await websocket.send_json({
            "type": "status",
            "data": "connected",
            "session_id": session_id
        })

        # Keep connection open
        while True:
            # Check for status updates in DB periodically
            status = await sop_orchestrator.get_session_status(session_id)
            if status:
                await websocket.send_json({"type": "update", "data": status})

            import asyncio
            await asyncio.sleep(2)

            # Receive (ignore for now)
            # data = await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# Mount static files for the UI
ui_dist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            "ui", "dist")

if os.path.exists(ui_dist_path):
    # Only mount assets if the directory exists
    assets_path = os.path.join(ui_dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Skip API and WS paths
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
