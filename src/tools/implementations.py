"""
Tool implementations for various tasks
"""

import os
import subprocess
import tempfile
import json
import asyncio
from typing import Any, Dict, List
from src.tools.base import BaseTool, ToolResult

class CodeWriterTool(BaseTool):
    """Tool for writing code to files."""
    
    def __init__(self):
        super().__init__(
            name="code_writer",
            description="Write code content to a specified file path",
            timeout=10
        )
        
    async def execute(self, file_path: str, content: str, overwrite: bool = False) -> ToolResult:
        """Write code to a file."""
        try:
            # Ensure absolute path
            if not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)
                
            # Ensure directory exists
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            # Check if file exists and overwrite is False
            if os.path.exists(file_path) and not overwrite:
                return ToolResult.error(f"File {file_path} already exists and overwrite=False")
                
            with open(file_path, 'w') as f:
                f.write(content)
                
            return ToolResult.success({
                "file_path": file_path,
                "size": len(content),
                "created": True
            })
            
        except Exception as e:
            return ToolResult.error(str(e))
            
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path where to write the file"
                },
                "content": {
                    "type": "string", 
                    "description": "Code content to write"
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite existing file",
                    "default": False
                }
            },
            "required": ["file_path", "content"]
        }

class CodeExecutorTool(BaseTool):
    """Tool for executing Python code."""
    
    def __init__(self):
        super().__init__(
            name="code_executor",
            description="Execute Python code and return results",
            timeout=30
        )
        
    async def execute(self, code: str, working_dir: str = None) -> ToolResult:
        """Execute Python code safely."""
        try:
            # Create temporary file for code execution
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
                
            # Execute the code
            cmd = ["python3", temp_file]
            
            if working_dir:
                os.chdir(working_dir)
                
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Clean up temp file
            os.unlink(temp_file)
            
            if process.returncode == 0:
                return ToolResult.success({
                    "output": stdout.decode('utf-8'),
                    "return_code": process.returncode
                })
            else:
                return ToolResult.error(
                    f"Code execution failed: {stderr.decode('utf-8')}",
                    metadata={"return_code": process.returncode}
                )
                
        except Exception as e:
            return ToolResult.error(str(e))
            
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for code execution",
                    "default": None
                }
            },
            "required": ["code"]
        }

class FileManagerTool(BaseTool):
    """Tool for file system operations."""
    
    def __init__(self):
        super().__init__(
            name="file_manager",
            description="Manage files and directories",
            timeout=10
        )
        
    async def execute(self, action: str, path: str, **kwargs) -> ToolResult:
        """Perform file system operations."""
        try:
            if action == "read":
                with open(path, 'r') as f:
                    content = f.read()
                return ToolResult.success({"content": content, "size": len(content)})
                
            elif action == "list":
                items = os.listdir(path)
                return ToolResult.success({"items": items, "count": len(items)})
                
            elif action == "create_dir":
                os.makedirs(path, exist_ok=True)
                return ToolResult.success({"created": path})
                
            elif action == "delete":
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    import shutil
                    shutil.rmtree(path)
                return ToolResult.success({"deleted": path})
                
            elif action == "exists":
                exists = os.path.exists(path)
                return ToolResult.success({"exists": exists, "is_file": os.path.isfile(path), "is_dir": os.path.isdir(path)})
                
            else:
                return ToolResult.error(f"Unknown action: {action}")
                
        except Exception as e:
            return ToolResult.error(str(e))
            
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "list", "create_dir", "delete", "exists"],
                    "description": "File operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                }
            },
            "required": ["action", "path"]
        }

class WebSearchTool(BaseTool):
    """Tool for web searching (mock implementation)."""
    
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web for information",
            timeout=15
        )
        
    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        """Mock web search - in real implementation, integrate with search APIs."""
        # This is a mock implementation
        mock_results = [
            {
                "title": f"Result {i+1} for '{query}'",
                "url": f"https://example.com/search/{query.replace(' ', '-')}-{i+1}",
                "snippet": f"This is a mock search result snippet for {query}..."
            }
            for i in range(max_results)
        ]
        
        return ToolResult.success({
            "query": query,
            "results": mock_results,
            "total_found": len(mock_results)
        })
        
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["query"]
        }

class CalculatorTool(BaseTool):
    """Tool for mathematical calculations."""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform mathematical calculations",
            timeout=5
        )
        
    async def execute(self, expression: str) -> ToolResult:
        """Evaluate mathematical expression safely."""
        try:
            # Basic safety check
            allowed_chars = set('0123456789+-*/.() ')
            if not all(c in allowed_chars for c in expression):
                return ToolResult.error("Invalid characters in expression")
                
            # Evaluate safely
            result = eval(expression, {"__builtins__": {}}, {})
            
            return ToolResult.success({
                "expression": expression,
                "result": result,
                "type": type(result).__name__
            })
            
        except Exception as e:
            return ToolResult.error(str(e))
            
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., '2+2', '3*4/2')"
                }
            },
            "required": ["expression"]
        }