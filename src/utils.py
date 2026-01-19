"""Utility functions for common operations."""

from src.core.config import FrameworkConfig
from src.models.model import Model
from src.models.types import ModelRole


def default_manager() -> Model:
    """Create and configure a default Model instance.

    Loads configuration from FrameworkConfig which automatically resolves
    configuration from template and environment variables.

    Returns:
        Configured Model instance.

    Raises:
        ConfigurationError: If no valid API key can be resolved.
    """
    config = FrameworkConfig()
    model_config = config.get_model_config()
    return Model(default_config=model_config)


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
