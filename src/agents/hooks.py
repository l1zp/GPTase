"""SDK hooks for GPTase agents.

This module provides hook implementations for Claude Agent SDK integration,
including logging, concurrency control, and middleware-to-hooks conversion utilities.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Hook Data Classes
# ============================================================================


@dataclass
class HookContext:
    """Context passed to hook functions.

    Attributes:
        agent_id: ID of the executing agent.
        session_id: Session ID for tracking.
        timestamp: When the hook was triggered.
        metadata: Additional context data.
    """

    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}


# ============================================================================
# Pre-Tool-Use Hooks
# ============================================================================


async def log_tool_usage(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: HookContext,
) -> Dict[str, Any]:
    """Log all tool usage before execution.

    Args:
        input_data: Tool input data containing tool_name and tool_input.
        tool_use_id: Unique identifier for this tool use.
        context: Hook execution context.

    Returns:
        Empty dict to allow execution to proceed.
    """
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})

    logger.info(
        "[TOOL] %s (id=%s) - Input: %s",
        tool_name,
        tool_use_id,
        _truncate_for_log(str(tool_input), 200),
    )

    return {}


async def validate_tool_parameters(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: HookContext,
) -> Dict[str, Any]:
    """Validate tool parameters against required schema.

    Args:
        input_data: Tool input data.
        tool_use_id: Tool use identifier.
        context: Hook context with tool_registry.

    Returns:
        Empty dict if valid, or denial dict if invalid.
    """
    tool_name = input_data.get("tool_name")
    tool_input = input_data.get("tool_input", {})

    # Check if tool_registry is available in context
    tool_registry = context.metadata.get("tool_registry") if context else None
    if not tool_registry:
        return {}  # Skip validation if no registry

    tool = tool_registry.get_tool(tool_name)
    if not tool:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Tool '{tool_name}' not found in registry",
            }
        }

    # Validate parameters
    if not tool.validate_parameters(tool_input):
        schema = tool.get_schema()
        required = schema.get("required", [])
        missing = [r for r in required if r not in tool_input]

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Missing required parameters: {missing}",
            }
        }

    return {}


# ============================================================================
# Concurrency Control Hooks
# ============================================================================


class ConcurrencyControl:
    """Manages concurrent tool executions with limits.

    This class provides hooks to limit the number of concurrent
    executions, particularly useful for the Task tool (subagent delegation).

    Attributes:
        max_concurrent: Maximum allowed concurrent executions.
        _pending: Set of currently executing tool use IDs.
        _lock: Async lock for thread-safe operations.
    """

    def __init__(self, max_concurrent: int = 3):
        """Initialize concurrency control.

        Args:
            max_concurrent: Maximum concurrent executions allowed.
        """
        self.max_concurrent = max_concurrent
        self._pending: set = set()
        self._lock = asyncio.Lock()

    async def limit_task_calls(
        self,
        input_data: Dict[str, Any],
        tool_use_id: str,
        context: HookContext,
    ) -> Dict[str, Any]:
        """Limit concurrent Task tool calls.

        Args:
            input_data: Tool input data.
            tool_use_id: Unique identifier for this call.
            context: Hook context.

        Returns:
            Empty dict to proceed, or denial dict if limit reached.
        """
        tool_name = input_data.get("tool_name", "")

        # Only limit Task tool (subagent delegation)
        if tool_name != "Task":
            return {}

        async with self._lock:
            if len(self._pending) >= self.max_concurrent:
                return {
                    "hookSpecificOutput": {
                        "hookEventName":
                        "PreToolUse",
                        "permissionDecision":
                        "deny",
                        "permissionDecisionReason":
                        (f"Maximum {self.max_concurrent} concurrent Task calls reached. "
                         "Please wait for existing tasks to complete."),
                    }
                }

            self._pending.add(tool_use_id)

        return {}

    async def release_task_slot(
        self,
        tool_name: str,
        tool_use_id: str,
        result: Any,
        context: HookContext,
    ) -> Dict[str, Any]:
        """Release a Task slot after execution completes.

        Args:
            tool_name: Name of the completed tool.
            tool_use_id: Unique identifier for this call.
            result: Tool execution result.
            context: Hook context.

        Returns:
            Empty dict (post-hooks don't affect execution).
        """
        if tool_name != "Task":
            return {}

        async with self._lock:
            self._pending.discard(tool_use_id)

        logger.debug("Released Task slot for %s", tool_use_id)
        return {}


# ============================================================================
# Post-Tool-Use Hooks
# ============================================================================


async def log_tool_result(
    tool_name: str,
    tool_use_id: str,
    result: Any,
    context: HookContext,
) -> Dict[str, Any]:
    """Log tool execution results.

    Args:
        tool_name: Name of the executed tool.
        tool_use_id: Unique identifier for this execution.
        result: Tool result data.
        context: Hook context.

    Returns:
        Empty dict (post-hooks don't affect execution).
    """
    result_str = str(result)
    logger.info(
        "[TOOL RESULT] %s (id=%s) - %s",
        tool_name,
        tool_use_id,
        _truncate_for_log(result_str, 200),
    )

    return {}


async def track_tool_metrics(
    tool_name: str,
    tool_use_id: str,
    result: Any,
    context: HookContext,
) -> Dict[str, Any]:
    """Track tool execution metrics for performance analysis.

    Args:
        tool_name: Name of the executed tool.
        tool_use_id: Unique identifier.
        result: Tool result with execution_time.
        context: Hook context with metrics tracker.

    Returns:
        Empty dict.
    """
    metrics_tracker = context.metadata.get("metrics_tracker") if context else None
    if not metrics_tracker:
        return {}

    # Extract execution time if available
    execution_time = 0.0
    if hasattr(result, "execution_time"):
        execution_time = result.execution_time
    elif isinstance(result, dict):
        execution_time = result.get("execution_time", 0.0)

    # Record metric
    try:
        metrics_tracker.record(tool_name, execution_time)
    except Exception as e:
        logger.warning(f"Failed to record metric: {e}")

    return {}


# ============================================================================
# User Prompt Submit Hooks
# ============================================================================


async def sanitize_user_input(
    prompt: str,
    context: HookContext,
) -> Dict[str, Any]:
    """Sanitize user input before processing.

    Args:
        prompt: User's input prompt.
        context: Hook context.

    Returns:
        Dict with sanitized prompt or denial.
    """
    # Check for potential injection patterns
    dangerous_patterns = [
        "ignore previous instructions",
        "disregard all",
        "system override",
    ]

    prompt_lower = prompt.lower()
    for pattern in dangerous_patterns:
        if pattern in prompt_lower:
            logger.warning("Potential injection detected: %s", pattern)
            # Note: In production, you might want to deny or sanitize
            # For now, just log the warning

    return {}


async def log_user_prompt(
    prompt: str,
    context: HookContext,
) -> Dict[str, Any]:
    """Log user prompts for debugging.

    Args:
        prompt: User's input prompt.
        context: Hook context.

    Returns:
        Empty dict.
    """
    logger.info(
        "[USER PROMPT] %s - %s",
        context.agent_id or "unknown",
        _truncate_for_log(prompt, 100),
    )
    return {}


# ============================================================================
# Hook Builder Utilities
# ============================================================================


def build_hooks(
    middleware_chain: Optional[List[Callable]] = None,
    tool_registry: Optional[Any] = None,
    max_concurrent_tasks: int = 3,
    enable_logging: bool = True,
    enable_validation: bool = True,
    enable_concurrency: bool = True,
) -> Dict[str, List]:
    """Build SDK hooks configuration from options.

    This function creates a complete hooks configuration for SDK agents,
    optionally converting GPTase middleware to SDK hooks.

    Args:
        middleware_chain: Optional list of middleware functions to convert.
        tool_registry: Optional tool registry for validation.
        max_concurrent_tasks: Maximum concurrent Task calls.
        enable_logging: Whether to enable logging hooks.
        enable_validation: Whether to enable parameter validation.
        enable_concurrency: Whether to enable concurrency control.

    Returns:
        Dictionary mapping hook event names to hook configurations.
    """
    hooks = {
        "PreToolUse": [],
        "PostToolUse": [],
        "UserPromptSubmit": [],
    }

    # Build context for hooks
    context = HookContext(metadata={
        "tool_registry": tool_registry,
    })

    # Add PreToolUse hooks
    pre_tool_hooks = []

    if enable_logging:
        pre_tool_hooks.append(log_tool_usage)

    if enable_validation and tool_registry:
        pre_tool_hooks.append(validate_tool_parameters)

    if enable_concurrency:
        concurrency = ConcurrencyControl(max_concurrent_tasks)
        pre_tool_hooks.append(concurrency.limit_task_calls)

        # Also add post-hook to release slots
        hooks["PostToolUse"].append(
            _create_hook_matcher_for_post(concurrency.release_task_slot))

    if pre_tool_hooks:
        hooks["PreToolUse"].append(_create_hook_matcher(pre_tool_hooks))

    # Add PostToolUse hooks
    post_tool_hooks = []

    if enable_logging:
        post_tool_hooks.append(log_tool_result)

    if post_tool_hooks:
        hooks["PostToolUse"].append(_create_hook_matcher_for_post(post_tool_hooks))

    # Add UserPromptSubmit hooks
    user_hooks = []

    if enable_logging:
        user_hooks.append(log_user_prompt)

    user_hooks.append(sanitize_user_input)

    if user_hooks:
        hooks["UserPromptSubmit"].append(_create_hook_matcher_for_user(user_hooks))

    # Convert middleware chain if provided
    if middleware_chain:
        converted = _convert_middleware_to_hooks(middleware_chain)
        for event, hook_list in converted.items():
            hooks.setdefault(event, []).extend(hook_list)

    return hooks


def _create_hook_matcher(hooks: List[Callable]) -> Dict[str, Any]:
    """Create a hook matcher dict for SDK.

    Args:
        hooks: List of hook functions.

    Returns:
        Hook matcher configuration.
    """
    try:
        from claude_agent_sdk import HookMatcher

        return HookMatcher(hooks=hooks)
    except ImportError:
        # Return a dict that can be converted later
        return {"hooks": hooks}


def _create_hook_matcher_for_post(hooks: List[Callable]) -> Dict[str, Any]:
    """Create a hook matcher for post-tool hooks.

    Args:
        hooks: List of post-tool hook functions.

    Returns:
        Hook matcher configuration.
    """
    return _create_hook_matcher(hooks)


def _create_hook_matcher_for_user(hooks: List[Callable]) -> Dict[str, Any]:
    """Create a hook matcher for user prompt hooks.

    Args:
        hooks: List of user prompt hook functions.

    Returns:
        Hook matcher configuration.
    """
    return _create_hook_matcher(hooks)


def _convert_middleware_to_hooks(middleware_chain: List[Callable], ) -> Dict[str, List]:
    """Convert GPTase middleware functions to SDK hooks.

    Middleware in GPTase typically follows a different signature,
    so we wrap them to match SDK hook signatures.

    Args:
        middleware_chain: List of middleware functions.

    Returns:
        Dictionary of SDK hooks.
    """
    hooks = {
        "PreToolUse": [],
        "PostToolUse": [],
    }

    for middleware in middleware_chain:
        # Try to detect middleware type and convert
        wrapper = _wrap_middleware_as_hook(middleware)
        if wrapper:
            event = wrapper.get("event", "PreToolUse")
            hook_func = wrapper.get("hook")
            if hook_func:
                hooks[event].append(_create_hook_matcher([hook_func]))

    return hooks


def _wrap_middleware_as_hook(middleware: Callable) -> Optional[Dict[str, Any]]:
    """Wrap a middleware function as an SDK hook.

    Args:
        middleware: Middleware function to wrap.

    Returns:
        Dict with event name and hook function, or None if not convertible.
    """
    import inspect

    sig = inspect.signature(middleware)

    # Check if it's a pre-processing middleware
    params = list(sig.parameters.keys())

    async def pre_wrapper(input_data, tool_use_id, context):
        # Adapt middleware call to hook signature
        try:
            if asyncio.iscoroutinefunction(middleware):
                await middleware(input_data)
            else:
                middleware(input_data)
        except Exception as e:
            logger.warning(f"Middleware error: {e}")

        return {}

    async def post_wrapper(tool_name, tool_use_id, result, context):
        try:
            if asyncio.iscoroutinefunction(middleware):
                await middleware(result)
            else:
                middleware(result)
        except Exception as e:
            logger.warning(f"Middleware error: {e}")

        return {}

    # Heuristic: if middleware has "result" or "output" in params, it's post-tool
    if any(p in params for p in ["result", "output", "response"]):
        return {"event": "PostToolUse", "hook": post_wrapper}
    else:
        return {"event": "PreToolUse", "hook": pre_wrapper}


def _truncate_for_log(text: str, max_length: int) -> str:
    """Truncate text for logging.

    Args:
        text: Text to truncate.
        max_length: Maximum length.

    Returns:
        Truncated text with ellipsis if needed.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


# ============================================================================
# Pre-built Hook Configurations
# ============================================================================


def get_default_hooks(tool_registry: Optional[Any] = None) -> Dict[str, List]:
    """Get default hooks configuration for GPTase agents.

    Args:
        tool_registry: Optional tool registry for validation.

    Returns:
        Default hooks dictionary.
    """
    return build_hooks(
        tool_registry=tool_registry,
        enable_logging=True,
        enable_validation=True,
        enable_concurrency=True,
    )


def get_minimal_hooks() -> Dict[str, List]:
    """Get minimal hooks configuration (logging only).

    Returns:
        Minimal hooks dictionary.
    """
    return build_hooks(
        enable_logging=True,
        enable_validation=False,
        enable_concurrency=False,
    )


def get_permissive_hooks() -> Dict[str, List]:
    """Get permissive hooks configuration (no restrictions).

    Returns:
        Permissive hooks dictionary with logging only.
    """
    return build_hooks(
        enable_logging=True,
        enable_validation=False,
        enable_concurrency=False,
    )
