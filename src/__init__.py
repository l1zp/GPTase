"""
GPTase - Multi-Agent Framework

A comprehensive framework for building and managing AI agent systems
with support for multiple LLM providers, code execution, and memory management.
"""

__version__ = "1.0.0"
__author__ = "GPTase Team"
__email__ = "team@gptase.com"

from .core.config import FrameworkConfig
from .agents.orchestrator import AgentOrchestrator

__all__ = [
    "FrameworkConfig",
    "AgentOrchestrator"
]