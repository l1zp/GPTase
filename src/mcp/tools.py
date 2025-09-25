"""
MCP Tools implementation for GPTase framework
"""

import asyncio
from typing import Any, Dict, List
from src.agents.orchestrator import AgentOrchestrator

class MCPTools:
    """MCP Tools implementation."""
    
    def __init__(self, orchestrator: AgentOrchestrator):
        self.orchestrator = orchestrator
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available MCP tools."""
        return [
            {
                "name": "execute_task",
                "description": "Execute a task using GPTase multi-agent system",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Task description"
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "default": "medium"
                        }
                    },
                    "required": ["description"]
                }
            },
            {
                "name": "get_system_status",
                "description": "Get current system status",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "list_agents",
                "description": "List all available agents",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "execute_code",
                "description": "Safe Python code execution",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute"
                        },
                        "timeout": {
                            "type": "integer",
                            "default": 30,
                            "description": "Execution timeout in seconds"
                        }
                    },
                    "required": ["code"]
                }
            }
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool."""
        try:
            if name == "execute_task":
                return await self._execute_task_tool(arguments)
            elif name == "get_system_status":
                return await self._get_system_status_tool(arguments)
            elif name == "list_agents":
                return await self._list_agents_tool(arguments)
            elif name == "execute_code":
                return await self._execute_code_tool(arguments)
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def _execute_task_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task tool implementation."""
        task = {
            "id": f"mcp_task_{hash(arguments.get('description', ''))}",
            "description": arguments["description"],
            "priority": arguments.get("priority", "medium")
        }
        
        result = await self.orchestrator.execute_task(task)
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Task executed successfully:\n{json.dumps(result, indent=2)}"
                }
            ]
        }
    
    async def _get_system_status_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get system status tool implementation."""
        status = await self.orchestrator.get_system_status()
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"System status:\n{json.dumps(status, indent=2)}"
                }
            ]
        }
    
    async def _list_agents_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List agents tool implementation."""
        agents = await self.orchestrator.list_available_agents()
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Available agents:\n{json.dumps(agents, indent=2)}"
                }
            ]
        }
    
    async def _execute_code_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code tool implementation."""
        from src.executors.code import CodeExecutor
        
        executor = CodeExecutor(timeout=arguments.get("timeout", 30))
        result = await executor.execute(arguments["code"])
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Code execution result:\n{json.dumps(result, indent=2)}"
                }
            ]
        }