"""Shared constants for the GPTase framework.

This module centralizes common constants used across multiple modules
to eliminate duplication and ensure consistency.
"""

# Agent status constants for orchestration/runtime state.
STATUS_IDLE = "idle"
STATUS_WORKING = "working"
STATUS_WAITING = "waiting"
STATUS_ERROR = "error"
STATUS_SUCCESS = "success"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_STARTED = "started"
STATUS_FAILED = "failed"

# Default importance (kept for potential future use)
DEFAULT_IMPORTANCE = 0.5
