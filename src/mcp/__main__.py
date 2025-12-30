"""
MCP Server entry point for GPTase framework
"""

import asyncio
import json
import sys

from src.core.logging import setup_logging
from src.mcp.server import GPTaseMCPServer


async def main():
    """Main entry point for MCP server."""
    setup_logging("INFO")

    server = GPTaseMCPServer()

    try:
        print("🚀 Starting GPTase MCP Server...")
        print("📊 MCP Tools available:")
        tools = await server.list_tools()
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")

        # Run the server
        print("✅ GPTase MCP Server is ready!")
        print("🔧 Connect using Claude Desktop or any MCP client")

        # Keep the server running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down MCP server...")
        await server.shutdown()
    except Exception as e:
        print(f"❌ MCP server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
