"""Utility functions and infrastructure for GPTase framework."""

from typing import Dict, List

from gptase.models.model import Model
from gptase.utils.config import FrameworkConfig
from gptase.utils.logging import setup_logging


def format_plan_list(plans: List[Dict[str, str]], desc_width: int = 60) -> str:
    """Format a list of Plans for display.

    Args:
        plans: List of Plan metadata dictionaries from PlanRegistry.list_plans().
        desc_width: Maximum width for description truncation.

    Returns:
        Formatted string for printing.
    """
    lines = ["Available Plans:", "-" * 50]
    for plan in plans:
        lines.append(f"  {plan['plan_id']}")
        lines.append(f"    Name: {plan['name']}")
        lines.append(f"    Version: {plan['version']}")
        if plan.get("description"):
            desc = plan["description"][:desc_width]
            if len(plan["description"]) > desc_width:
                desc += "..."
            lines.append(f"    Description: {desc}")
        lines.append("")
    return "\n".join(lines)


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
