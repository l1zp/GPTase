# 🔗 MCP (Model Context Protocol) Guide

GPTase now fully supports MCP (Model Context Protocol) for seamless integration with Claude Desktop and other MCP clients.

## 🚀 Quick Setup

### 1. Install MCP Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Claude Desktop

Add to your Claude Desktop configuration:

#### **macOS** (`~/Library/Application Support/Claude/claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "gptase": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "env": {
        "PYTHONPATH": "$(pwd)",
        "OPENAI_API_KEY": "your-openai-key",
        "ANTHROPIC_API_KEY": "your-anthropic-key"
      }
    }
  }
}
```

#### **Windows** (`%APPDATA%/Claude/claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "gptase": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "env": {
        "PYTHONPATH": "%CD%",
        "OPENAI_API_KEY": "your-openai-key",
        "ANTHROPIC_API_KEY": "your-anthropic-key"
      }
    }
  }
}
```

### 3. Start MCP Server
```bash
# Method 1: Direct MCP server
python -m src.mcp.server

# Method 2: Using scripts
./scripts/start_mcp.sh
```

## 🛠️ MCP Tools Available

### **1. execute_task**
Execute complex tasks using the multi-agent system.

**Usage in Claude Desktop:**
```
Use the gptase:execute_task tool to create a Python script that calculates fibonacci numbers
```

### **2. execute_code**
Safely execute Python code.

**Usage in Claude Desktop:**
```
Use the gptase:execute_code tool to run: print('Hello, World!')
```

### **3. get_system_status**
Get current system status.

**Usage in Claude Desktop:**
```
Use the gptase:get_system_status tool to check system status
```

### **4. list_agents**
List all available agents.

**Usage in Claude Desktop:**
```
Use the gptase:list_agents tool to see available agents
```

### **5. search_memory**
Search through agent memories.

**Usage in Claude Desktop:**
```
Use the gptase:search_memory tool to search for: fibonacci
```

## 📊 MCP Features

### **✅ Full Integration**
- **Multi-agent orchestration** via MCP
- **Code execution** safely sandboxed
- **Memory management** persistent across sessions
- **Tool registry** comprehensive tool access
- **Real-time status** monitoring

### **🔧 Configuration Options**
```json
{
  "mcpServers": {
    "gptase": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "env": {
        "PYTHONPATH": ".",
        "OPENAI_API_KEY": "your-key",
        "ANTHROPIC_API_KEY": "your-key",
        "GPTASE_LLM_PROVIDER": "openai",
        "GPTASE_LLM_MODEL": "gpt-4"
      }
    }
  }
}
```

## 🎯 Usage Examples

### **Basic Task Execution**
```bash
# Via Claude Desktop
"Use gptase:execute_task to create a web scraper"
"Use gptase:execute_task to analyze this dataset"
"Use gptase:execute_task to build a REST API"
```

### **Code Execution**
```bash
# Via Claude Desktop
"Use gptase:execute_code to calculate 2+2"
"Use gptase:execute_code to read a CSV file"
"Use gptase:execute_code to plot data"
```

### **System Monitoring**
```bash
# Via Claude Desktop
"Use gptase:get_system_status to check system health"
"Use gptase:list_agents to see available capabilities"
```

## 🔍 Troubleshooting

### **Common Issues**
1. **Import errors**: Ensure PYTHONPATH is set correctly
2. **API key issues**: Set environment variables properly
3. **Connection issues**: Check Claude Desktop configuration

### **Debug Mode**
```bash
# Enable debug logging
python -m src.mcp.server --debug
```

### **Test MCP Connection**
```bash
# Test MCP tools
python -c "
from src.mcp.server import GPTaseMCPServer
import asyncio

async def test():
    server = GPTaseMCPServer()
    tools = await server.list_tools()
    print('Available tools:', tools)

asyncio.run(test())
"
```

## 🚀 Advanced Usage

### **Custom MCP Clients**
```python
from src.mcp.server import GPTaseMCPServer
import asyncio

async def main():
    server = GPTaseMCPServer()
    
    # List tools
    tools = await server.list_tools()
    print("Available tools:", tools)
    
    # Execute task
    result = await server.call_tool("execute_task", {
        "description": "Create a data analysis script",
        "priority": "high"
    })
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(main())
```

## 📈 Benefits

- **🔌 Zero-config integration** with Claude Desktop
- **🤖 Multi-agent power** accessible via natural language
- **🔒 Secure execution** with sandboxed environments
- **📊 Real-time monitoring** and status updates
- **🛠️ Extensible** easy to add new tools and capabilities
