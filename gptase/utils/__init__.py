"""Utility functions and infrastructure for GPTase framework."""

from typing import Any, Dict, List

from gptase.models.model import Model
from gptase.models.types import ModelConfig
from gptase.utils.config import FrameworkConfig
from gptase.utils.logging import setup_logging


def format_sop_list(sops: List[Dict[str, str]], desc_width: int = 60) -> str:
    """Format a list of SOPs for display.

    Args:
        sops: List of SOP metadata dictionaries from SOPRegistry.list_sops().
        desc_width: Maximum width for description truncation.

    Returns:
        Formatted string for printing.
    """
    lines = ["Available SOPs:", "-" * 50]
    for sop in sops:
        lines.append(f"  {sop['plan_id']}")
        lines.append(f"    Name: {sop['name']}")
        lines.append(f"    Version: {sop['version']}")
        if sop.get("description"):
            desc = sop["description"][:desc_width]
            if len(sop["description"]) > desc_width:
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
    model_config = ModelConfig(
        provider=config.llm_provider,
        model_name=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        temperature=config.llm_temperature,
        max_tokens=config.llm_max_tokens,
        timeout=config.llm_timeout or 600,
        thinking=config.llm_thinking,
        provider_config=config.llm_provider_config,
    )
    return Model(default_config=model_config, enable_tracking=enable_tracking)
