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

## 🚀 Quick Start

This project exposes modules under `src/`.

### Installation
```bash
# Clone the repository
git clone https://github.com/gptase/gptase.git
cd gptase

# Install base dependencies
pip install -r requirements.txt

# Or install environment-specific sets
# pip install -r requirements/base.txt
# pip install -r requirements/dev.txt
# pip install -r requirements/prod.txt

# Optional: install as editable package to ensure imports work everywhere
pip install -e .
```

### Basic Usage (Model Manager)
```python
import asyncio
from src.models.manager import ModelManager
from src.models.types import ModelConfig, ModelProvider, ModelRole

async def main():
    manager = ModelManager(
        default_config=ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o-mini",
            api_key="YOUR_OPENAI_API_KEY",
            temperature=0.7,
            max_tokens=1000,
        )
    )
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello and tell me a fun fact."},
    ]
    response = await manager.generate(messages, role=ModelRole.GENERAL)
    print(response.content)

asyncio.run(main())
```

If you run examples directly, ensure imports work by either:
- `PYTHONPATH="$(pwd)" python3 examples/chat_demo.py`, or
- `pip install -e .` once (recommended).

### Web Interface
```bash
# Start development server
./scripts/start_dev.sh

# Or production server
./scripts/start_prod.sh
```

Visit **http://localhost:8000** for the interactive dashboard!

## 🎯 **Advanced Usage**

### Configuration

Provide LLM settings via `config/llm_config.template.json`:

```json
{
  "model_name": "Kimi-K2",
  "api_key": "${API_KEY}",
  "temperature": 0.7,
  "max_tokens": 1000,
  "base_url": "https://llmapi.paratera.com"
}
```

API key resolution follows this order:
- If `api_key` is set to a real value in the template, use it.
- If missing or a placeholder like `${...}`, use environment variables:
  - `OPENAI_API_KEY` (preferred)
  - `GPTASE_OPENAI_API_KEY` (fallback)

To configure via environment:
```bash
export OPENAI_API_KEY="your-real-api-key"
```

### Orchestrator Example
```python
import asyncio
from src.core.config import FrameworkConfig, ModelConfigExtended
from src.agents.orchestrator import AgentOrchestrator

async def main():
    config = FrameworkConfig(
        llm=ModelConfigExtended(
            provider="custom",
            model_name="Kimi-K2",
            planner_config=None,
            executor_config=None,
        )
    )
    orchestrator = AgentOrchestrator(config)
    result = await orchestrator.execute_task({
        "id": "demo_001",
        "description": "Create a Python script to calculate fibonacci numbers"
    })
    print(result)
    await orchestrator.shutdown()

asyncio.run(main())
```
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

## 🧪 Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_agents/ -v
pytest tests/test_models/ -v
pytest tests/test_executors/ -v
```

## 📊 API Endpoints

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

## 🔧 Development

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

## 📈 Performance

- **Async-first** architecture for high concurrency
- **Memory-efficient** execution with cleanup
- **Scalable** design for production workloads
- **Real-time** updates via WebSocket

## 🌍 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

CC BY-NC 4.0 License - see [LICENSE](../LICENSE) file for details.
