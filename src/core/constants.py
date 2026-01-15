"""Shared constants for the GPTase framework.

This module centralizes common constants used across multiple modules
to eliminate duplication and ensure consistency.
"""

# Agent status constants
STATUS_IDLE = "idle"
STATUS_WORKING = "working"
STATUS_WAITING = "waiting"
STATUS_ERROR = "error"
STATUS_SUCCESS = "success"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_STARTED = "started"
STATUS_FAILED = "failed"

# Tool status constants
TOOL_STATUS_SUCCESS = "success"
TOOL_STATUS_ERROR = "error"
TOOL_STATUS_TIMEOUT = "timeout"
TOOL_STATUS_CANCELLED = "cancelled"

# Message type constants
DEFAULT_MESSAGE_TYPE = "general"

# Default timeouts
DEFAULT_MESSAGE_TIMEOUT = 5.0
DEFAULT_TOOL_TIMEOUT = 30

# Default importance and confidence
DEFAULT_IMPORTANCE = 0.5
DEFAULT_SEMANTIC_CONFIDENCE = 0.8
