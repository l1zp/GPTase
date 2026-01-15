"""FastAPI application for the multi-agent framework web interface."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig

logger = logging.getLogger(__name__)

# Application metadata
APP_TITLE = "GPTase Multi-Agent Framework"
APP_DESCRIPTION = "Interactive web interface for managing AI agents"
APP_VERSION = "1.0.0"

# Paths
STATIC_FILES_PATH = "src/web/static"
TEMPLATES_PATH = "src/web/templates"

# API routes
ROUTE_DASHBOARD = "/"
ROUTE_STATUS = "/api/status"
ROUTE_AGENTS = "/api/agents"
ROUTE_TASKS = "/api/tasks"
ROUTE_ENZYME_EXTRACT = "/api/enzyme/extract"
ROUTE_WEBSOCKET = "/ws"

# Agent names
AGENT_ENZYME = "enzyme"


class TaskRequest(BaseModel):
    """Request model for task creation."""

    id: Optional[str] = None
    description: str
    priority: Optional[str] = None


class EnzymeExtractRequest(BaseModel):
    """Request model for enzyme extraction."""

    document: Dict[str, Any]


class WebApplication:
    """Main FastAPI application for the web interface.

    Provides REST API endpoints and WebSocket support for
    real-time communication with the multi-agent framework.

    Attributes:
        app: The FastAPI application instance.
        orchestrator: Lazy-initialized agent orchestrator.
        websocket_manager: Manages WebSocket connections.
    """

    def __init__(self) -> None:
        self.app = FastAPI(
            title=APP_TITLE,
            description=APP_DESCRIPTION,
            version=APP_VERSION,
            docs_url="/docs",
            redoc_url="/redoc",
        )
        self.orchestrator: Optional[AgentOrchestrator] = None
        self.websocket_manager = WebSocketManager()
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Setup all API routes."""
        self._setup_static_files()
        self._setup_dashboard()
        self._setup_api_routes()
        self._setup_websocket()

    def _setup_static_files(self) -> None:
        """Mount static file directories."""
        self.app.mount(
            "/static", StaticFiles(directory=STATIC_FILES_PATH), name="static"
        )

    def _setup_dashboard(self) -> None:
        """Setup dashboard route."""
        templates = Jinja2Templates(directory=TEMPLATES_PATH)

        @self.app.get(ROUTE_DASHBOARD, response_class=HTMLResponse)
        async def dashboard(request: Request) -> HTMLResponse:
            """Main dashboard page."""
            return templates.TemplateResponse("dashboard.html", {"request": request})

    def _setup_api_routes(self) -> None:
        """Setup API endpoints."""

        @self.app.get(ROUTE_STATUS)
        async def get_status() -> Dict[str, Any]:
            """Get system status."""
            orchestrator = self._get_orchestrator()
            return await orchestrator.get_system_status()

        @self.app.get(ROUTE_AGENTS)
        async def get_agents() -> List[Dict[str, Any]]:
            """Get all agents."""
            orchestrator = self._get_orchestrator()
            return await orchestrator.list_available_agents()

        @self.app.post(ROUTE_TASKS)
        async def create_task(task: TaskRequest) -> Dict[str, Any]:
            """Create and execute a new task."""
            orchestrator = self._get_orchestrator()
            result = await orchestrator.execute_task(task.model_dump())
            return result

        @self.app.get(ROUTE_TASKS)
        async def get_tasks() -> Dict[str, Any]:
            """Get task history."""
            orchestrator = self._get_orchestrator()
            return await orchestrator.get_agent_memory("global")

        @self.app.post(ROUTE_ENZYME_EXTRACT)
        async def enzyme_extract(req: EnzymeExtractRequest) -> Dict[str, Any]:
            """Extract enzyme information from a document."""
            orchestrator = self._get_orchestrator()
            enzyme_agent = orchestrator.agents.get(AGENT_ENZYME)
            if not enzyme_agent:
                return {"status": "error", "error": "Enzyme agent not found"}
            result = await enzyme_agent.process_task(req.model_dump())
            return result

    def _setup_websocket(self) -> None:
        """Setup WebSocket endpoint for real-time updates."""

        @self.app.websocket(ROUTE_WEBSOCKET)
        async def websocket_endpoint(websocket: WebSocket) -> None:
            """WebSocket for real-time updates."""
            await self.websocket_manager.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    await self.websocket_manager.broadcast(data)
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket)

    def _get_orchestrator(self) -> AgentOrchestrator:
        """Get or create the orchestrator instance.

        Returns:
            AgentOrchestrator instance.
        """
        if self.orchestrator is None:
            config = FrameworkConfig()
            self.orchestrator = AgentOrchestrator(config)
        return self.orchestrator


class WebSocketManager:
    """Manage WebSocket connections for real-time updates.

    Maintains a list of active connections and provides
    broadcast functionality.

    Attributes:
        active_connections: List of active WebSocket connections.
    """

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: WebSocket connection to accept.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug("WebSocket connected. Total connections: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: WebSocket connection to remove.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.debug(
                "WebSocket disconnected. Total connections: %d", len(self.active_connections)
            )

    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all connected clients.

        Args:
            message: Message to broadcast.
        """
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    web_app = WebApplication()
    return web_app.app
