"""Integration tests for Markdown-based agents and Orchestrator."""

import pytest

from gptase.agents.base import Agent
from gptase.core.orchestrator import AgentOrchestrator
from gptase.utils.config import FrameworkConfig


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
            assert agent.system_prompt  # loaded from markdown body

    @pytest.mark.asyncio
    async def test_agent_with_tools_definition(self, orchestrator):
        """Verify that agents are loaded with a non-empty system prompt."""
        agent = orchestrator.agents["document-structure-analyzer"]
        assert isinstance(agent, Agent)
        assert len(agent.system_prompt) > 0

    def test_discover_agents_directly(self):
        """Test Agent.discover_agents() without orchestrator."""
        agents = Agent.discover_agents()
        assert len(agents) > 0
        for name, agent in agents.items():
            assert agent.agent_id == name
            assert agent.system_prompt
