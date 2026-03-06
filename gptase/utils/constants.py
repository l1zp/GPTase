"""Shared constants for the GPTase framework.

This module centralizes common constants used across multiple modules
to eliminate duplication and ensure consistency.
"""


class AgentStatus:
    """Agent status constants.

    Provides a centralized namespace for all agent-related status values
    to ensure consistency across the framework.
    """

    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    SUCCESS = "success"
    PROCESSING = "processing"
    COMPLETED = "completed"
    STARTED = "started"
    FAILED = "failed"


class Timeouts:
    """Centralized timeout values (in seconds).

    All timeout constants should be defined here to ensure consistency
    and make it easy to adjust timeouts globally.
    """

    MESSAGE = 5.0
    TOOL = 30
    CODE_WRITER = 10
    CODE_EXECUTOR = 30
    FILE_MANAGER = 10
    WEB_SEARCH = 15
    CALCULATOR = 5
    DOCUMENT_LOADER = 15
    DOCUMENT_ANALYSIS = 30
    EXTRACTION = 30
    VISION_ANALYSIS = 60
    MINERU = 300


# Backward compatibility: export module-level constants
# These are maintained for backward compatibility but new code
# should use the class namespaces (e.g., AgentStatus.IDLE)
STATUS_IDLE = AgentStatus.IDLE
STATUS_WORKING = AgentStatus.WORKING
STATUS_WAITING = AgentStatus.WAITING
STATUS_ERROR = AgentStatus.ERROR
STATUS_SUCCESS = AgentStatus.SUCCESS
STATUS_PROCESSING = AgentStatus.PROCESSING
STATUS_COMPLETED = AgentStatus.COMPLETED
STATUS_STARTED = AgentStatus.STARTED
STATUS_FAILED = AgentStatus.FAILED

# Message type constants
DEFAULT_MESSAGE_TYPE = "general"

# Default timeouts (for backward compatibility)
DEFAULT_MESSAGE_TIMEOUT = Timeouts.MESSAGE
DEFAULT_TOOL_TIMEOUT = Timeouts.TOOL

# Default importance and confidence
DEFAULT_IMPORTANCE = 0.5
DEFAULT_SEMANTIC_CONFIDENCE = 0.8
