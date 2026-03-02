"""
GPTase - Multi-Agent Framework

A comprehensive framework for building and managing AI agent systems
with support for multiple LLM providers, code execution, and memory management.
"""

__version__ = "1.0.0"
__author__ = "GPTase Team"
__email__ = "team@gptase.com"

from .agents.orchestrator import AgentOrchestrator
from .core.config import FrameworkConfig

__all__ = ["FrameworkConfig", "AgentOrchestrator"]
