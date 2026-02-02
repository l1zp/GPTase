#!/bin/bash
# MCP Server startup script

echo "[INFO] Starting GPTase MCP Server..."
echo "[INFO] MCP Tools available via Claude Desktop"
echo "[INFO] Connect using: python -m src.mcp.server"
echo ""

# Set Python path and start MCP server
export PYTHONPATH="."
python -m src.mcp.server "$@"
