"""Integration tests for Markdown-based agents and Orchestrator."""

import pytest

from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig


@pytest.fixture
def orchestrator():
    config = FrameworkConfig()
    return AgentOrchestrator(config)


class TestMarkdownAgentsIntegration:
    """Verify that all specialized agents are correctly loaded via Markdown."""

    def test_agent_loading(self, orchestrator):
        # List of agents that should now be loaded via MarkdownAgentFactory
        expected_agents = [
            "document_structure_analyzer", "enzyme_kinetics_extractor",
            "enzyme_design_extractor", "enzyme_extraction_summary", "planner"
        ]

        for agent_id in expected_agents:
            assert agent_id in orchestrator.agents
            agent = orchestrator.agents[agent_id]
            # Verify they are instances of MarkdownAgent (implicitly via factory loading)
            assert agent.agent_id == agent_id
            assert len(agent.capabilities) > 0

    @pytest.mark.asyncio
    async def test_agent_with_tools_definition(self, orchestrator):
        """Verify that agents have their tools correctly mapped from Markdown."""
        agent = orchestrator.agents["document_structure_analyzer"]
        # Check if definition loaded @tools
        assert "document_structure_tool" in agent.definition.tools
