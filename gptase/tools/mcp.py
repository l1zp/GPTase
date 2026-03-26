"""MCP client integration for GPTase.

Connects to MCP servers at runtime and registers their tools into the
ToolRegistry as McpProxyTool instances, making them available to the
LLM tool loop just like any native tool.

Tool naming convention: ``{server_name}__{mcp_tool_name}``
This matches the Claude Code convention (e.g. ``web-search-prime__web_search_prime``).

Usage (via llm_config.json):

    "mcp_servers": {
        "web-search-prime": {
            "transport": "sse",
            "url": "http://localhost:3000/sse"
        },
        "my-local-server": {
            "transport": "stdio",
            "command": "node",
            "args": ["/path/to/server.js"]
        }
    }
"""

import contextlib
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic import Field

from gptase.tools.base import BaseTool

logger = logging.getLogger(__name__)


class McpServerConfig(BaseModel):
    """Configuration for a single MCP server connection.

    Supports both stdio (subprocess) and SSE (HTTP) transports.
    """

    transport: str = "stdio"
    # stdio transport
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None
    # sse transport
    url: Optional[str] = None


class McpProxyTool(BaseTool):
    """Forwards execute() calls to a tool on a connected MCP server.

    Registered in the ToolRegistry under ``{server_name}__{mcp_tool_name}``.
    """

    def __init__(
        self,
        server_name: str,
        mcp_tool_name: str,
        description: str,
        input_schema: Any,
        session: Any,
    ) -> None:
        self.name = f"{server_name}__{mcp_tool_name}"
        self.description = description or f"MCP tool '{mcp_tool_name}' from server '{server_name}'"
        self._mcp_tool_name = mcp_tool_name
        self._input_schema = input_schema
        self._session = session

    def get_schema(self) -> Dict[str, Any]:
        """Return the MCP tool's input schema in OpenAI JSON Schema format."""
        if self._input_schema is None:
            return {"type": "object", "properties": {}}
        if hasattr(self._input_schema, "model_dump"):
            return self._input_schema.model_dump(exclude_none=True)
        return dict(self._input_schema)

    async def execute(self, **kwargs) -> str:
        """Invoke the MCP tool and return its text output."""
        result = await self._session.call_tool(
            self._mcp_tool_name,
            kwargs or None,
        )
        parts = [
            item.text
            for item in result.content
            if hasattr(item, "text") and item.text
        ]
        if result.isError:
            return f"[ERROR] MCP tool '{self._mcp_tool_name}': {' '.join(parts)}"
        return "\n".join(parts) if parts else "[INFO] MCP tool returned no content"


class McpManager:
    """Connects to MCP servers and registers their tools into a ToolRegistry.

    Uses AsyncExitStack to keep all server connections alive for the
    duration of the manager's lifetime. Call ``connect()`` once and
    ``disconnect()`` when done.
    """

    def __init__(self) -> None:
        self._exit_stack: Optional[contextlib.AsyncExitStack] = None
        self._connected: bool = False

    async def connect(
        self,
        registry: Any,
        server_configs: Dict[str, "McpServerConfig"],
    ) -> None:
        """Connect to all configured MCP servers and register their tools.

        Idempotent — calling this a second time is a no-op.

        Args:
            registry: ToolRegistry instance to register tools into.
            server_configs: Mapping of server name -> McpServerConfig.
        """
        if self._connected:
            return

        try:
            from mcp import ClientSession
            from mcp import StdioServerParameters
            from mcp.client.sse import sse_client
            from mcp.client.stdio import stdio_client
        except ImportError:
            logger.warning(
                "mcp package not installed; MCP tools will not be available. "
                "Install with: pip install mcp"
            )
            return

        self._exit_stack = contextlib.AsyncExitStack()
        await self._exit_stack.__aenter__()

        for server_name, config in server_configs.items():
            try:
                if config.transport == "stdio":
                    if not config.command:
                        logger.warning(
                            "MCP server '%s': transport=stdio but no command; skipping.",
                            server_name,
                        )
                        continue
                    params = StdioServerParameters(
                        command=config.command,
                        args=config.args,
                        env=config.env,
                        cwd=config.cwd,
                    )
                    read, write = await self._exit_stack.enter_async_context(
                        stdio_client(params)
                    )
                elif config.transport == "sse":
                    if not config.url:
                        logger.warning(
                            "MCP server '%s': transport=sse but no url; skipping.",
                            server_name,
                        )
                        continue
                    read, write = await self._exit_stack.enter_async_context(
                        sse_client(config.url)
                    )
                else:
                    logger.warning(
                        "MCP server '%s': unknown transport '%s'; skipping.",
                        server_name,
                        config.transport,
                    )
                    continue

                session = await self._exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()

                tools_result = await session.list_tools()
                registered = 0
                for tool in tools_result.tools:
                    proxy = McpProxyTool(
                        server_name=server_name,
                        mcp_tool_name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.inputSchema,
                        session=session,
                    )
                    registry.register(proxy)
                    registered += 1

                logger.info(
                    "Connected to MCP server '%s' (%s), registered %d tools.",
                    server_name,
                    config.transport,
                    registered,
                )

            except Exception as exc:
                logger.warning(
                    "Failed to connect to MCP server '%s': %s",
                    server_name,
                    exc,
                )
                continue

        self._connected = True

    async def disconnect(self) -> None:
        """Close all MCP server connections."""
        if self._exit_stack is not None:
            await self._exit_stack.__aexit__(None, None, None)
            self._exit_stack = None
            self._connected = False
            logger.debug("Disconnected all MCP servers.")
