"""Tool execution handlers."""

import asyncio
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from gptase.tools.base import BaseTool

logger = logging.getLogger(__name__)

READ_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "file_path": {
            "type":
            "string",
            "description":
            "The absolute path to the file to read. You can call this tool multiple times in a single response to read multiple files in parallel.",
        },
        "offset": {
            "type": "integer",
            "description": "Line number to start reading from (1-indexed, optional)",
        },
        "limit": {
            "type": "integer",
            "description": "Number of lines to read (optional)",
        },
    },
    "required": ["file_path"],
}

GREP_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {
            "type":
            "string",
            "description":
            "The regex pattern to search for. You can call this tool multiple times in a single response to search different patterns or paths in parallel.",
        },
        "path": {
            "type": "string",
            "description": "Directory or file path to search in",
        },
        "glob": {
            "type": "string",
            "description": "File pattern to match (e.g., '*.py')",
        },
    },
    "required": ["pattern", "path"],
}

GLOB_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {
            "type":
            "string",
            "description":
            "Glob pattern to match files (e.g., '**/*.py'). You can call this tool multiple times in a single response to search with different patterns in parallel.",
        },
        "path": {
            "type": "string",
            "description": "Base directory for the search (optional)",
        },
    },
    "required": ["pattern"],
}

BASH_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The bash command to execute",
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout in seconds (default: 30)",
        },
    },
    "required": ["command"],
}


class ReadTool(BaseTool):
    """Read tool for file reading."""

    name = "Read"
    description = "Read contents from a file on the local filesystem."

    def get_schema(self) -> Dict[str, Any]:
        return READ_TOOL_SCHEMA

    async def execute(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> str:
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            return f"[ERROR] File not found: {file_path}"

        if not path.is_file():
            return f"[ERROR] Not a file: {file_path}"

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            start = (offset or 1) - 1  # Convert 1-indexed to 0-indexed
            end = start + (limit or len(lines))
            selected = lines[start:end]

            # Format with line numbers
            result = []
            for i, line in enumerate(selected, start=(offset or 1)):
                result.append(f"{i:6}\t{line.rstrip()}")

            return "\n".join(result)
        except Exception as e:
            return f"[ERROR] Failed to read file: {e}"


class GrepTool(BaseTool):
    """Grep tool for pattern searching."""

    name = "Grep"
    description = "Search for patterns in files using regex."

    def get_schema(self) -> Dict[str, Any]:
        return GREP_TOOL_SCHEMA

    async def execute(
        self,
        pattern: str,
        path: str,
        glob: Optional[str] = None,
    ) -> str:
        search_path = Path(path).expanduser().resolve()

        if not search_path.exists():
            return f"[ERROR] Path not found: {path}"

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"[ERROR] Invalid regex pattern: {e}"

        results = []
        files_to_search = []

        if search_path.is_file():
            files_to_search = [search_path]
        else:
            pattern_glob = glob or "**/*"
            files_to_search = list(search_path.glob(pattern_glob))

        for file_path in files_to_search:
            if not file_path.is_file():
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{file_path}:{line_num}: {line.rstrip()}")
            except Exception:
                continue

        if not results:
            return "[INFO] No matches found"

        return "\n".join(results[:100])  # Limit output


class GlobTool(BaseTool):
    """Glob tool for file pattern matching."""

    name = "Glob"
    description = "Find files matching a glob pattern."

    def get_schema(self) -> Dict[str, Any]:
        return GLOB_TOOL_SCHEMA

    async def execute(
        self,
        pattern: str,
        path: Optional[str] = None,
    ) -> str:
        base_path = Path(path).expanduser().resolve() if path else Path.cwd()

        if not base_path.exists():
            return f"[ERROR] Path not found: {path}"

        matches = list(base_path.glob(pattern))

        if not matches:
            return "[INFO] No files matched the pattern"

        # Format output
        results = []
        for m in matches[:200]:  # Limit output
            try:
                rel_path = m.relative_to(base_path)
                results.append(str(rel_path))
            except ValueError:
                results.append(str(m))

        return "\n".join(results)


class BashTool(BaseTool):
    """Bash tool for command execution."""

    name = "Bash"
    description = "Execute bash commands. Use for read-only operations only."

    # Dangerous commands that should be blocked
    BLOCKED_PATTERNS = [
        r"\brm\s+-rf",
        r"\brm\s+[^-]",  # rm without flags
        r"\bmkfs\b",
        r"\bdd\b",
        r"\bshutdown\b",
        r"\breboot\b",
        r">\s*/dev/",  # Writing to devices
        r"curl.*\|\s*bash",  # Piping curl to bash
        r"wget.*\|\s*bash",  # Piping wget to bash
    ]

    def get_schema(self) -> Dict[str, Any]:
        return BASH_TOOL_SCHEMA

    async def execute(self, command: str, timeout: int = 30) -> str:
        # Safety check
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return "[ERROR] Command blocked for safety: contains potentially dangerous operation"

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            result_parts = []
            if stdout:
                result_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                result_parts.append(
                    f"[STDERR] {stderr.decode('utf-8', errors='replace')}")

            if proc.returncode != 0:
                result_parts.append(f"[ERROR] Exit code: {proc.returncode}")

            return "\n".join(result_parts) if result_parts else "[OK] Command completed"

        except asyncio.TimeoutError:
            return f"[ERROR] Command timed out after {timeout} seconds"
        except Exception as e:
            return f"[ERROR] Failed to execute command: {e}"


DELEGATE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "agent_id": {
            "type":
            "string",
            "description":
            "ID of the agent to delegate the task to (e.g., 'code-analyzer', 'literature-synthesis')",
        },
        "task_description": {
            "type":
            "string",
            "description":
            "Complete description of the task for the delegated agent to execute",
        },
        "image_paths": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Optional list of image paths relevant to the task",
        },
    },
    "required": ["agent_id", "task_description"],
}


class DelegateTaskTool(BaseTool):
    """Delegate work to another Agent instance in the Orchestrator."""

    name = "DelegateTask"
    description = "Delegate a specialized task to another agent. Use this when the task requires specialized skills like code analysis, paper structure analysis, etc."

    def __init__(self, orchestrator=None):
        """Initialize the DelegateTaskTool.

        Args:
            orchestrator: The AgentOrchestrator instance to delegate tasks through.
                          Can be set later if not available at initialization.
        """
        self.orchestrator = orchestrator

    def get_schema(self) -> Dict[str, Any]:
        return DELEGATE_TASK_SCHEMA

    async def execute(
        self,
        agent_id: str,
        task_description: str,
        image_paths: Optional[List[str]] = None,
    ) -> str:
        if not self.orchestrator:
            return "[ERROR] Orchestrator not found for delegation."

        if agent_id not in self.orchestrator.agents:
            # Maybe fallback to first available or return error
            available = list(self.orchestrator.agents.keys())
            return f"[ERROR] Agent '{agent_id}' not found. Available agents: {available}"

        try:
            from gptase.agents import AgentTask
            task_obj = AgentTask(description=task_description,
                                 agent_id=agent_id,
                                 image_paths=image_paths or [])

            result = await self.orchestrator.agents[agent_id].process_task(task_obj)

            if result.get("status") == "error" or result.get("status") == "failed":
                return f"[ERROR] Delegation failed: {result.get('error', 'Unknown error')}"

            # Extract content from result
            data = result.get("data", {})
            content = data.get("content", str(data)) if isinstance(data,
                                                                   dict) else str(data)

            if not content:
                return "[INFO] Agent completed task but returned no content."

            return f"Result from {agent_id}:\n{content}"

        except Exception as e:
            return f"[ERROR] Failed to delegate task to {agent_id}: {e}"


def register_default_tools(registry: "ToolRegistry") -> None:
    """Register the default set of tools.

    Args:
        registry: The ToolRegistry instance to register tools with.
    """
    registry.register(ReadTool())
    registry.register(GrepTool())
    registry.register(GlobTool())
    registry.register(BashTool())

    # DelegateTaskTool should be imported from orchestrator to avoid circular imports if needed,
    # or we define it here and use it in orchestrator.
    # We will define DelegateTaskTool here.
    registry.register(DelegateTaskTool())
    logger.info("Registered default tools: Read, Grep, Glob, Bash, DelegateTask")
