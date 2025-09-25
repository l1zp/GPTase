"""
Memory manager agent for memory and learning management
"""

from typing import Dict, Any, List
from ..base import BaseAgent

class MemoryManagerAgent(BaseAgent):
    """Agent responsible for memory management and learning."""
    
    def __init__(self, agent_id: str, memory_manager, tool_registry):
        super().__init__(agent_id, memory_manager, tool_registry, ["memory_management", "learning", "summarization", "analysis"])
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Manage memory and learning."""
        task_description = task.get("description", "")
        
        # Get memory summary
        memory_summary = await self.memory_manager.get_memory_summary()
        
        # Create memory management report
        report = {
            "total_memories": memory_summary.get("total_memories", 0),
            "memory_types": memory_summary.get("memory_types", {}),
            "recent_entries": memory_summary.get("recent_entries", []),
            "cleanup_recommendations": [
                "Archive old conversation memories",
                "Optimize task memory storage",
                "Clean up temporary memories"
            ]
        }
        
        return {
            "status": "success",
            "report": report,
            "summary": f"Managed {report['total_memories']} memories for task: {task_description}"
        }