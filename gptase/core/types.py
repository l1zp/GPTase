"""Core type definitions for the GPTase framework."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic import ConfigDict


class DispatchRequest(BaseModel):
    """Typed input for AgentOrchestrator.dispatch().

    Replaces the untyped Dict[str, Any] that was previously used as the
    single entry point for all orchestrator modes (agent, coordinator, plan).

    Supports ``extra="allow"`` so callers can still pass arbitrary keys
    that are transparently forwarded (e.g. to agent-level task dicts).
    """

    model_config = ConfigDict(extra="allow")

    # ── Identity ──────────────────────────────────────────────────────
    id: Optional[str] = None
    session_id: Optional[str] = None

    # ── Description (used by all modes) ───────────────────────────────
    description: str = ""
    message: Optional[str] = None  # alias for description in session resume

    # ── Agent mode ────────────────────────────────────────────────────
    agent_id: Optional[str] = None

    # ── Plan mode ─────────────────────────────────────────────────────
    plan: Optional[Dict[str, Any]] = None  # inline plan dict
    plan_id: Optional[str] = None
    plan_path: Optional[str] = None
    planning_context: Optional[str] = None

    # ── Execution control ─────────────────────────────────────────────
    auto_execute: bool = True
    auto_replan: bool = False
    max_auto_replans: int = 3

    # ── Data & paths ──────────────────────────────────────────────────
    input_data: Optional[Dict[str, Any]] = None
    document_path: Optional[str] = None
    workspace_dir: Optional[str] = None
    image_paths: Optional[List[str]] = None

    # ── Session resume fields ─────────────────────────────────────────
    approve_plan: bool = False
    feedback: Optional[str] = None
    user_input: Optional[str] = None

    def effective_description(self) -> str:
        """Return the best available description string."""
        return str(self.message or self.description or "").strip()
