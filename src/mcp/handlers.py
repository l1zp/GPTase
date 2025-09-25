"""
MCP handlers for GPTase framework
"""

from typing import Any, Dict, List
from src.agents.orchestrator import AgentOrchestrator

class TaskHandler:
    """Handler for MCP task operations."""
    
    def __init__(self, orchestrator: AgentOrchestrator):
        self.orchestrator = orchestrator
    
    async def handle_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a task request."""
        return await self.orchestrator.execute_task(task)

class AgentHandler:
    """Handler for MCP agent operations."""
    
    def __init__(self, orchestrator: AgentOrchestrator):
        self.orchestrator = orchestrator
    
    async def get_agents(self) -> List[Dict[str, Any]]:
        """Get list of agents."""
        return await self.orchestrator.list_available_agents()
    
    async def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Get agent status."""
        return await self.orchestrator.get_agent_memory(agent_id)

class MemoryHandler:
    """Handler for MCP memory operations."""
    
    def __init__(self, orchestrator: AgentOrchestrator):
        self.orchestrator = orchestrator
    
    async def get_memory_summary(self) -> Dict[str, Any]:
        """Get memory summary."""
        return await self.orchestrator.get_agent_memory("global")