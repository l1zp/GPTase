# 🚀 GPTase - Multi-Agent Framework

A comprehensive, elegant framework for building and managing AI agent systems with support for multiple LLM providers, code execution, memory management, and a beautiful web interface.

## ✨ Features

### 🤖 **Multi-Agent System**
- **Planner Agent** - Task decomposition and planning
- **Executor Agent** - Task implementation and execution
- **Tool Manager** - Resource and tool management
- **Memory Manager** - Persistent memory and learning

### 🧠 **LLM Integration**
- **OpenAI GPT** - GPT-3.5, GPT-4, GPT-4 Turbo
- **Anthropic Claude** - Claude 3 series
- **Local Models** - Custom model support
- **Flexible Configuration** - Role-based model selection

### 🔧 **Code Execution**
- **Python Executor** - Safe Python code execution
- **Shell Executor** - System command execution
- **Docker Executor** - Containerized execution
- **Sandbox Executor** - Secure sandboxed execution

### 🎨 **Web Interface**
- **Real-time Dashboard** - Live monitoring and control
- **Task Management** - Create and track tasks
- **Agent Monitoring** - Real-time status updates
- **Interactive Logs** - Live execution logs

## 🏗️ **Elegant Structure**

```
gptase/
├── src/                    # Source code
│   ├── core/              # Core framework
│   ├── agents/            # Agent implementations
│   ├── models/            # LLM management
│   ├── executors/         # Code execution engines
│   ├── memory/            # Memory management
│   ├── tools/             # Tool registry
│   └── web/               # Web interface
├── tests/                 # Test suite
├── examples/              # Usage examples
├── scripts/               # Utility scripts
└── requirements/          # Dependencies
```

## 🚀 **Quick Start**

### **Installation**
```bash
# Clone the repository
git clone https://github.com/gptase/gptase.git
cd gptase

# Install dependencies
pip install -r requirements/base.txt

# For web interface
pip install -r requirements/prod.txt
```

### **Basic Usage**
```python
import asyncio
from src.core.config import FrameworkConfig
from src.agents.orchestrator import AgentOrchestrator

async def main():
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)
    
    task = {
        "id": "demo_001",
        "description": "Create a Python script to calculate fibonacci numbers",
        "priority": "high"
    }
    
    result = await orchestrator.execute_task(task)
    print(f"Task completed: {result['status']}")
    await orchestrator.shutdown()

asyncio.run(main())
```

### **Web Interface**
```bash
# Start development server
./scripts/start_dev.sh

# Or production server
./scripts/start_prod.sh
```

Visit **http://localhost:8000** for the interactive dashboard!

## 🎯 **Advanced Usage**

### **Custom Configuration**
```python
from src.core.config import FrameworkConfig

config = FrameworkConfig(
    llm={
        "planner_config": {"provider": "openai", "model": "gpt-4"},
        "executor_config": {"provider": "anthropic", "model": "claude-3-opus"}
    },
    timeout=60,
    max_retries=3
)
```

### **Custom Agents**
```python
from src.agents.base import BaseAgent

class CustomAgent(BaseAgent):
    async def execute_task(self, task):
        # Your custom logic here
        return {"status": "success", "result": "custom result"}
```

## 🧪 **Testing**

```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_agents/ -v
pytest tests/test_models/ -v
pytest tests/test_executors/ -v
```

## 📊 **API Endpoints**

### **System Status**
```bash
curl http://localhost:8000/api/status
```

### **Agent Management**
```bash
curl http://localhost:8000/api/agents
```

### **Task Creation**
```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"id": "test", "description": "Your task", "priority": "high"}'
```

## 🔧 **Development**

### **Setup Development Environment**
```bash
# Install development dependencies
pip install -r requirements/dev.txt

# Run development server
./scripts/start_dev.sh
```

### **Code Style**
```bash
# Format code
black src/
isort src/

# Type checking
mypy src/
```

## 📈 **Performance**

- **Async-first** architecture for high concurrency
- **Memory-efficient** execution with cleanup
- **Scalable** design for production workloads
- **Real-time** updates via WebSocket

## 🌍 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 **License**

MIT License - see [LICENSE](LICENSE) file for details.