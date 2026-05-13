"""Core type definitions for the GPTase framework."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class DispatchRequest(BaseModel):
    """Typed input for AgentOrchestrator.dispatch().

    Single entry point for the two execution modes:
      - Agent mode: explicit ``agent_id`` invokes one worker directly.
      - Coordinator mode (default): LLM-driven orchestrator loop with
        DelegateTask delegation.

    Supports ``extra="allow"`` so callers can still pass arbitrary keys
    that are transparently forwarded.
    """

    model_config = ConfigDict(extra="allow")

    # ── Identity ──────────────────────────────────────────────────────
    id: Optional[str] = None
    session_id: Optional[str] = None

    # ── Query (used by all modes) ────────────────────────────────────
    query: str = ""

    # ── Agent mode ────────────────────────────────────────────────────
    agent_id: Optional[str] = None

    # ── Execution control ─────────────────────────────────────────────
    auto_execute: bool = True

    # ── Data & paths ──────────────────────────────────────────────────
    input_data: Optional[Dict[str, Any]] = None
    document_path: Optional[str] = None
    workspace_dir: Optional[str] = None
    image_paths: Optional[List[str]] = None
