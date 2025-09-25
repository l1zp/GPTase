"""
FastAPI application for the multi-agent framework web interface
"""

import asyncio
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from src.core.config import FrameworkConfig
from src.agents.orchestrator import AgentOrchestrator

class WebApplication:
    """Main FastAPI application for the web interface."""
    
    def __init__(self):
        self.app = FastAPI(
            title="GPTase Multi-Agent Framework",
            description="Interactive web interface for managing AI agents",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        self.orchestrator = None
        self.websocket_manager = WebSocketManager()
        self.setup_routes()
        
    def setup_routes(self):
        """Setup all API routes."""
        
        # Static files
        self.app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
        
        # Templates
        templates = Jinja2Templates(directory="src/web/templates")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Main dashboard."""
            return templates.TemplateResponse("dashboard.html", {"request": request})
            
        @self.app.get("/api/status")
        async def get_status() -> Dict[str, Any]:
            """Get system status."""
            if not self.orchestrator:
                config = FrameworkConfig()
                self.orchestrator = AgentOrchestrator(config)
            
            return await self.orchestrator.get_system_status()
            
        @self.app.get("/api/agents")
        async def get_agents() -> List[Dict[str, Any]]:
            """Get all agents."""
            if not self.orchestrator:
                config = FrameworkConfig()
                self.orchestrator = AgentOrchestrator(config)
            
            return await self.orchestrator.list_available_agents()
            
        @self.app.post("/api/tasks")
        async def create_task(task: Dict[str, Any]) -> Dict[str, Any]:
            """Create and execute a new task."""
            if not self.orchestrator:
                config = FrameworkConfig()
                self.orchestrator = AgentOrchestrator(config)
            
            result = await self.orchestrator.execute_task(task)
            return result
            
        @self.app.get("/api/tasks")
        async def get_tasks() -> Dict[str, Any]:
            """Get task history."""
            if not self.orchestrator:
                config = FrameworkConfig()
                self.orchestrator = AgentOrchestrator(config)
            
            return await self.orchestrator.get_agent_memory("global")
            
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket for real-time updates."""
            await self.websocket_manager.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    await self.websocket_manager.broadcast(data)
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket)

class WebSocketManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        """Connect a new WebSocket."""
        await websocket.accept()
        self.active_connections.append(websocket)
        
    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
    async def broadcast(self, message: str):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    web_app = WebApplication()
    return web_app.app