"""
Specialized agent implementations

This package now uses markdown-based agent definitions.
All agents are defined in config/agents/*.md files and loaded dynamically
via MarkdownAgentFactory.

The LLMEnzymeExtractorAgent is retained here for reference and as a backup
for the enzyme_extractor.md agent, which provides equivalent functionality.
"""

from .llm_enzyme_extractor import LLMEnzymeExtractorAgent

__all__ = [
    "LLMEnzymeExtractorAgent",
]
