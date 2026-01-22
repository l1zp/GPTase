"""Utility functions for common operations."""

from typing import Any, Dict, List

from src.core.config import FrameworkConfig
from src.models.model import Model
from src.models.types import ModelRole


def create_error_response(
    step_name: str,
    description: str,
    errors: List[str],
) -> Dict[str, Any]:
    """Create a standardized error response for pipeline failures.

    This is a generic utility for creating consistent error responses across
    different agents and pipeline steps. It follows the standard pipeline
    response schema with reactions, steps, validations, and errors.

    Args:
        step_name: Name of the pipeline step that failed.
        description: Human-readable description of the error.
        errors: List of detailed error messages.

    Returns:
        Dictionary matching the extraction result schema with error status.
        Structure:
        {
            "reactions": [],
            "pipeline": {
                "steps": [{"name": step_name, "description": description, "status": "failed"}],
                "validations": [],
                "errors": errors
            }
        }

    Example:
        >>> errors = ["Missing required field: enzyme_name", "Invalid kinetics data"]
        >>> response = create_error_response("extract", "Validation failed", errors)
        >>> response["pipeline"]["status"]
        'failed'
    """
    return {
        "reactions": [],
        "pipeline": {
            "steps": [{
                "name": step_name,
                "description": description,
                "status": "failed",
            }],
            "validations": [],
            "errors": errors,
        },
    }


def default_manager(enable_tracking: bool = True) -> Model:
    """Create and configure a default Model instance.

    Loads configuration from FrameworkConfig which automatically resolves
    configuration from template and environment variables.

    Args:
        enable_tracking: Enable conversation tracking (default: True).

    Returns:
        Configured Model instance.

    Raises:
        ConfigurationError: If no valid API key can be resolved.
    """
    config = FrameworkConfig()
    model_config = config.get_model_config()
    return Model(default_config=model_config, enable_tracking=enable_tracking)


def get_model_for_role(role: ModelRole) -> Model:
    """Get a Model instance configured for a specific role.

    Provides a convenient way to get role-specific model instances
    with appropriate configuration overrides.

    Args:
        role: The model role (PLANNER, EXECUTOR, GENERAL, etc.)

    Returns:
        Configured Model instance for the specified role.
    """
    config = FrameworkConfig()
    model_config = config.get_model_config(role)
    return Model(default_config=model_config)
