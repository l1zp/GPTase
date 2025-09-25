#!/bin/bash
# MCP Server startup script

echo "🚀 Starting GPTase MCP Server..."
echo "🔗 MCP Tools available via Claude Desktop"
echo "📊 Connect using: python -m src.mcp.server"

# Set Python path
export PYTHONPATH="."

# Start MCP server
python -m src.mcp.server "$@"