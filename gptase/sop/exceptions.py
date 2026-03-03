"""SOP-specific exceptions for the GPTase framework.

This module defines the exception hierarchy used throughout the SOP system.
All SOP-specific exceptions inherit from SOPError.
"""

from typing import Any, Dict, Optional


class SOPError(Exception):
    """Base exception for SOP-related errors.

    All SOP-specific exceptions inherit from this class, allowing
    for catching any SOP-related error with a single except clause.

    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional error context.
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class SOPNotFoundError(SOPError):
    """Exception raised when an SOP definition cannot be found.

    Raised when attempting to load an SOP that does not exist in the
    registry or on the filesystem.
    """

    def __init__(self, plan_id: str, search_path: Optional[str] = None):
        details = {"plan_id": plan_id}
        if search_path:
            details["search_path"] = search_path
        super().__init__(f"SOP definition not found: {plan_id}", details)


class SOPValidationError(SOPError):
    """Exception raised when an SOP definition fails validation.

    Raised when an SOP definition file has invalid syntax, missing
    required fields, or violates schema constraints.
    """

    def __init__(self, plan_id: str, reason: str, field: Optional[str] = None):
        details = {"plan_id": plan_id, "reason": reason}
        if field:
            details["field"] = field
        super().__init__(f"Invalid SOP definition '{plan_id}': {reason}", details)


class SOPExecutionError(SOPError):
    """Exception raised when SOP execution fails.

    Raised when an error occurs during SOP workflow execution, such as
    step failures, agent errors, or context issues.
    """

    def __init__(
        self,
        plan_id: str,
        step_id: Optional[str] = None,
        reason: str = "",
        original_error: Optional[Exception] = None,
    ):
        details = {"plan_id": plan_id}
        if step_id:
            details["step_id"] = step_id
        if reason:
            details["reason"] = reason
        if original_error:
            details["original_error"] = str(original_error)

        message = f"SOP execution failed for '{plan_id}'"
        if step_id:
            message = f"SOP execution failed at step '{step_id}' in '{plan_id}'"
        if reason:
            message = f"{message}: {reason}"

        super().__init__(message, details)


class AgentDispatchError(SOPError):
    """Exception raised when dispatching to an agent fails.

    Raised when the dispatcher cannot create or communicate with
    an agent, or when the agent returns an error response.
    """

    def __init__(
        self,
        agent_id: str,
        action: Optional[str] = None,
        reason: str = "",
        original_error: Optional[Exception] = None,
    ):
        details = {"agent_id": agent_id}
        if action:
            details["action"] = action
        if reason:
            details["reason"] = reason
        if original_error:
            details["original_error"] = str(original_error)

        message = f"Failed to dispatch to agent '{agent_id}'"
        if action:
            message = f"Failed to dispatch action '{action}' to agent '{agent_id}'"
        if reason:
            message = f"{message}: {reason}"

        super().__init__(message, details)
