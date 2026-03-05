"""
GPTase - Multi-Agent Framework

A comprehensive framework for building and managing AI agent systems
with support for multiple LLM providers, code execution, and memory management.
"""

__version__ = "1.0.0"
__author__ = "GPTase Team"
__email__ = "team@gptase.com"

from .core.config import FrameworkConfig

__all__ = ["FrameworkConfig", "AgentOrchestrator"]


def __getattr__(name: str):
    """Lazy import for heavy modules to speed up package load time."""
    if name == "AgentOrchestrator":
        from .agents.orchestrator import AgentOrchestrator
        return AgentOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
