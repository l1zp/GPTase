"""Integration tests for Markdown-based agents and Orchestrator."""

import pytest

from gptase.agents.orchestrator import AgentOrchestrator
from gptase.core.config import FrameworkConfig


@pytest.fixture
def orchestrator():
    config = FrameworkConfig()
    return AgentOrchestrator(config)


class TestMarkdownAgentsIntegration:
    """Verify that all specialized agents are correctly loaded via Markdown."""

    def test_agent_loading(self, orchestrator):
        # List of agents that should be loaded (now using hyphenated names)
        expected_agents = [
            "document-structure-analyzer",
            "enzyme-kinetics-extractor",
            "enzyme-design-extractor",
            "enzyme-extraction-summary",
        ]

        for name in expected_agents:
            assert name in orchestrator.agents
            agent = orchestrator.agents[name]
            assert agent.agent_id == name
            assert agent.definition.name == name

    @pytest.mark.asyncio
    async def test_agent_with_tools_definition(self, orchestrator):
        """Verify that agents have their tools correctly mapped from Markdown."""
        agent = orchestrator.agents["document-structure-analyzer"]
        # Check if definition has tools (now standard tools like Read, Grep)
        assert "Read" in agent.definition.tools
        assert "Grep" in agent.definition.tools
