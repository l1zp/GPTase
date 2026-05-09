"""Utility functions and infrastructure for GPTase framework."""

from gptase.models.model import Model
from gptase.utils.config import FrameworkConfig


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
    return Model(default_config=config.to_model_config(),
                 enable_tracking=enable_tracking)
