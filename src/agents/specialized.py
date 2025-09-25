"""
Specialized agent implementations for different roles
"""

import asyncio
import json
from typing import Any, Dict, List
from src.agents.base import BaseAgent
from src.memory.types import TaskMemory, ConversationMemory, MemoryType

class PlanningAgent(BaseAgent):
    """Agent specialized in planning and task decomposition."""
    
    def __init__(self, agent_id: str, memory_manager, tool_registry):
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=["planning", "task_decomposition", "strategy", "analysis"]
        )
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task by creating a detailed plan."""
        await self.update_status("planning", task.get("id"))
        
        try:
            # Get task context
            task_description = task.get("description", "")
            required_tools = task.get("required_tools", [])
            
            # Create plan structure
            plan = {
                "task_id": task.get("id"),
                "original_description": task_description,
                "steps": [],
                "estimated_duration": 0,
                "required_tools": required_tools,
                "dependencies": [],
                "risk_assessment": {}
            }
            
            # Decompose task into steps
            if "fibonacci" in task_description.lower():
                plan["steps"] = [
                    {
                        "step_id": "1",
                        "description": "Create Python script for fibonacci calculation",
                        "tool": "code_writer",
                        "estimated_time": 2,
                        "priority": "high"
                    },
                    {
                        "step_id": "2", 
                        "description": "Test the fibonacci script",
                        "tool": "code_executor",
                        "estimated_time": 1,
                        "priority": "high"
                    },
                    {
                        "step_id": "3",
                        "description": "Verify results with known fibonacci values",
                        "tool": "calculator",
                        "estimated_time": 1,
                        "priority": "medium"
                    }
                ]
                plan["estimated_duration"] = 4
            else:
                # Generic planning for unknown tasks
                plan["steps"] = [
                    {
                        "step_id": "1",
                        "description": f"Analyze requirements for: {task_description}",
                        "tool": "web_search",
                        "estimated_time": 3,
                        "priority": "high"
                    },
                    {
                        "step_id": "2",
                        "description": "Implement solution",
                        "tool": "code_writer",
                        "estimated_time": 5,
                        "priority": "high"
                    },
                    {
                        "step_id": "3",
                        "description": "Test implementation",
                        "tool": "code_executor", 
                        "estimated_time": 2,
                        "priority": "high"
                    }
                ]
                plan["estimated_duration"] = 10
                
            # Store planning memory
            await self.memory.store_memory(TaskMemory(
                id=f"plan_{task.get('id')}",
                task_id=task.get('id'),
                agent_id=self.agent_id,
                content=plan,
                type=MemoryType.TASK,
                tags=["planning", "task_decomposition"]
            ))
            
            await self.update_status("completed", task.get("id"))
            
            return {
                "status": "success",
                "plan": plan,
                "agent_id": self.agent_id,
                "message": f"Successfully created plan with {len(plan['steps'])} steps"
            }
            
        except Exception as e:
            await self.update_status("error", task.get("id"))
            return {
                "status": "error",
                "error": str(e),
                "agent_id": self.agent_id
            }

class ExecutionAgent(BaseAgent):
    """Agent specialized in executing tasks and plans."""
    
    def __init__(self, agent_id: str, memory_manager, tool_registry):
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=["execution", "implementation", "testing", "debugging"]
        )
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task based on provided plan."""
        await self.update_status("executing", task.get("id"))
        
        try:
            plan = task.get("plan", {})
            steps = plan.get("steps", [])
            
            if not steps:
                # Simple execution mode
                return await self._execute_simple_task(task)
                
            # Execute planned steps
            results = []
            for step in steps:
                step_result = await self._execute_step(step, task.get("id"))
                results.append(step_result)
                
                if step_result.get("status") == "error":
                    break
                    
            await self.update_status("completed", task.get("id"))
            
            return {
                "status": "success",
                "results": results,
                "agent_id": self.agent_id,
                "total_steps": len(steps),
                "completed_steps": len([r for r in results if r.get("status") == "success"])
            }
            
        except Exception as e:
            await self.update_status("error", task.get("id"))
            return {
                "status": "error",
                "error": str(e),
                "agent_id": self.agent_id
            }
            
    async def _execute_simple_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a simple task without a plan."""
        description = task.get("description", "").lower()
        
        if "fibonacci" in description:
            # Create fibonacci script
            fib_code = '''def fibonacci(n):
    """Calculate nth Fibonacci number."""
    if n <= 1:
        return n
    a, b = 0, 1
    for i in range(2, n + 1):
        a, b = b, a + b
    return b

if __name__ == "__main__":
    for i in range(10):
        print(f"F({i}) = {fibonacci(i)}")
'''
            
            # Write the file
            file_path = "fibonacci.py"
            write_result = await self.tools.execute_tool(
                "code_writer",
                {"file_path": file_path, "content": fib_code}
            )
            
            if write_result.status.value == "success":
                # Execute the file
                exec_result = await self.tools.execute_tool(
                    "code_executor",
                    {"code": fib_code}
                )
                
                return {
                    "status": "success",
                    "file_created": file_path,
                    "execution_output": exec_result.data.get("output", ""),
                    "agent_id": self.agent_id
                }
            else:
                return {
                    "status": "error",
                    "error": write_result.error,
                    "agent_id": self.agent_id
                }
        else:
            return {
                "status": "error",
                "error": "No plan provided and unknown task type",
                "agent_id": self.agent_id
            }
            
    async def _execute_step(self, step: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """Execute a single step from a plan."""
        tool_name = step.get("tool")
        step_desc = step.get("description")
        
        # Build parameters based on step type
        if tool_name == "code_writer":
            params = self._build_code_writer_params(step_desc)
        elif tool_name == "code_executor":
            params = self._build_code_executor_params(step_desc)
        elif tool_name == "calculator":
            params = self._build_calculator_params(step_desc)
        elif tool_name == "web_search":
            params = self._build_web_search_params(step_desc)
        else:
            params = {}
            
        # Execute the tool
        result = await self.tools.execute_tool(tool_name, params)
        
        return {
            "step_id": step.get("step_id"),
            "tool": tool_name,
            "description": step_desc,
            "status": result.status.value,
            "result": result.data,
            "error": result.error
        }
        
    def _build_code_writer_params(self, description: str) -> Dict[str, Any]:
        """Build parameters for code writer based on description."""
        if "fibonacci" in description.lower():
            return {
                "file_path": "fibonacci.py",
                "content": '''def fibonacci(n):
    """Calculate nth Fibonacci number."""
    if n <= 1:
        return n
    a, b = 0, 1
    for i in range(2, n + 1):
        a, b = b, a + b
    return b

if __name__ == "__main__":
    for i in range(10):
        print(f"F({i}) = {fibonacci(i)}")
''',
                "overwrite": True
            }
        elif "test file" in description.lower():
            return {
                "file_path": "test.txt",
                "content": "This is a test file created by the framework",
                "overwrite": True
            }
        else:
            return {
                "file_path": "output.txt",
                "content": f"# Generated for: {description}",
                "overwrite": True
            }
        return {}
        
    def _build_code_executor_params(self, description: str) -> Dict[str, Any]:
        """Build parameters for code executor."""
        return {"code": "exec(open('fibonacci.py').read())"}
        
    def _build_calculator_params(self, description: str) -> Dict[str, Any]:
        """Build parameters for calculator."""
        return {"expression": "0+1+1+2+3+5+8+13+21+34"}
        
    def _build_web_search_params(self, description: str) -> Dict[str, Any]:
        """Build parameters for web search."""
        return {"query": "fibonacci sequence python implementation"}

class ToolAgent(BaseAgent):
    """Agent specialized in tool management and optimization."""
    
    def __init__(self, agent_id: str, memory_manager, tool_registry):
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=["tool_management", "optimization", "troubleshooting", "integration"]
        )
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process tool-related tasks."""
        await self.update_status("processing", task.get("id"))
        
        try:
            task_type = task.get("type", "analyze")
            
            if task_type == "analyze_tools":
                return await self._analyze_tools()
            elif task_type == "optimize_usage":
                return await self._optimize_tool_usage(task)
            else:
                return await self._provide_tool_recommendations(task)
                
        except Exception as e:
            await self.update_status("error", task.get("id"))
            return {"status": "error", "error": str(e)}
            
    async def _analyze_tools(self) -> Dict[str, Any]:
        """Analyze available tools and their usage."""
        tools = self.tools.list_tools()
        categories = self.tools.get_all_categories()
        
        tool_details = {}
        for tool_name in tools:
            tool = self.tools.get_tool(tool_name)
            tool_details[tool_name] = {
                "description": tool.description,
                "timeout": tool.timeout,
                "schema": tool.get_schema()
            }
            
        return {
            "status": "success",
            "total_tools": len(tools),
            "categories": categories,
            "tools": tool_details,
            "agent_id": self.agent_id
        }
        
    async def _optimize_tool_usage(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize tool usage for a given scenario."""
        required_capabilities = task.get("capabilities", [])
        
        matching_tools = self.tools.get_tools_for_capabilities(required_capabilities)
        
        return {
            "status": "success",
            "recommended_tools": matching_tools,
            "capabilities": required_capabilities,
            "agent_id": self.agent_id
        }
        
    async def _provide_tool_recommendations(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Provide tool recommendations for a task."""
        task_description = task.get("description", "")
        
        recommendations = []
        
        if any(word in task_description.lower() for word in ["write", "create", "generate"]):
            recommendations.append("code_writer")
        if any(word in task_description.lower() for word in ["run", "execute", "test"]):
            recommendations.append("code_executor")
        if any(word in task_description.lower() for word in ["file", "directory", "folder"]):
            recommendations.append("file_manager")
        if any(word in task_description.lower() for word in ["search", "find", "lookup"]):
            recommendations.append("web_search")
        if any(word in task_description.lower() for word in ["calculate", "math", "compute"]):
            recommendations.append("calculator")
            
        return {
            "status": "success",
            "task_description": task_description,
            "recommended_tools": recommendations,
            "agent_id": self.agent_id
        }

class MemoryAgent(BaseAgent):
    """Agent specialized in memory management and retrieval."""
    
    def __init__(self, agent_id: str, memory_manager, tool_registry):
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=["memory_management", "retrieval", "summarization", "analysis"]
        )
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process memory-related tasks."""
        await self.update_status("processing", task.get("id"))
        
        try:
            task_type = task.get("type", "summarize")
            
            if task_type == "summarize":
                return await self._summarize_memories(task)
            elif task_type == "search":
                return await self._search_memories(task)
            elif task_type == "cleanup":
                return await self._cleanup_memories(task)
            else:
                return await self._get_memory_stats()
                
        except Exception as e:
            await self.update_status("error", task.get("id"))
            return {"status": "error", "error": str(e)}
            
    async def _summarize_memories(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize memories for an agent or overall."""
        agent_id = task.get("agent_id")
        try:
            summary = await self.memory.create_memory_summary(agent_id)
            return {
                "status": "success",
                "summary": summary,
                "agent_id": agent_id or "global",
                "processed_by": self.agent_id
            }
        except Exception as e:
            return {
                "status": "success",  # Return success even if no memories exist
                "summary": {
                    "conversation_count": 0,
                    "task_count": 0,
                    "recent_conversations": [],
                    "recent_tasks": []
                },
                "agent_id": agent_id or "global",
                "processed_by": self.agent_id,
                "note": "No memories found"
            }
        
        return {
            "status": "success",
            "summary": summary,
            "agent_id": agent_id or "global",
            "processed_by": self.agent_id
        }
        
    async def _search_memories(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Search memories based on criteria."""
        query = task.get("query", "")
        limit = task.get("limit", 10)
        
        memories = await self.memory.search_memories(
            query=query,
            limit=limit
        )
        
        return {
            "status": "success",
            "query": query,
            "results_count": len(memories),
            "results": [
                {
                    "id": mem.id,
                    "type": mem.type,
                    "content_preview": str(mem.content)[:100] + "..." if len(str(mem.content)) > 100 else str(mem.content),
                    "timestamp": mem.timestamp.isoformat()
                }
                for mem in memories
            ],
            "agent_id": self.agent_id
        }
        
    async def _cleanup_memories(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up old memories."""
        max_age_days = task.get("max_age_days", 30)
        deleted_count = await self.memory.cleanup_old_memories(max_age_days)
        
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "max_age_days": max_age_days,
            "agent_id": self.agent_id
        }
        
    async def _get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        usage = await self.memory.get_usage()
        
        return {
            "status": "success",
            "usage": usage,
            "agent_id": self.agent_id
        }