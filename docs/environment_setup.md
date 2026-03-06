# Environment Setup Guide

This guide covers the complete environment setup for GPTase development and usage.

## Prerequisites

- Python 3.10+ (3.10, 3.11, or 3.12 recommended)
- Conda (Miniconda or Anaconda) or pip
- Git

## Quick Setup

### Option 1: Using Conda (Recommended)

```bash
# Clone the repository
git clone https://github.com/l1zp/GPTase.git
cd GPTase

# Create conda environment
conda create -n llm python=3.11 -y

# Activate environment
conda activate llm

# Install in development mode
pip install -e .

# Install optional dependencies for LLM providers
pip install -e ".[models]"

# Install development dependencies (optional)
pip install -e ".[dev]"
```

### Option 2: Using pip with venv

```bash
# Clone the repository
git clone https://github.com/l1zp/GPTase.git
cd GPTase

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Install in development mode
pip install -e ".[models,dev]"
```

## Dependency Overview

### Core Dependencies (auto-installed)

| Package | Purpose |
|---------|---------|
| `pydantic` | Data validation and settings management |
| `python-dotenv` | Environment variable loading |
| `aiofiles` | Async file operations |
| `httpx` | HTTP client for API calls |
| `pyyaml` | YAML configuration parsing |
| `claude-agent-sdk` | Claude SDK integration |
| `aiosqlite` | Async SQLite operations |
| `rich` | Terminal formatting and progress bars |
| `requests` | HTTP requests |
| `beautifulsoup4` | HTML parsing |

### Optional Dependencies

```bash
# LLM provider support
pip install -e ".[models]"
# Includes: openai, anthropic

# Development tools
pip install -e ".[dev]"
# Includes: pytest, pytest-asyncio, pytest-cov, yapf, isort, mypy, pre-commit

# Install all
pip install -e ".[models,dev]"
```

## LLM Configuration

### Configuration Files

GPTase uses JSON configuration files in `config/` directory:

| File | Purpose |
|------|---------|
| `llm_config.template.json` | Template with MiniMax configuration |
| `llm_config.glm5.json` | GLM-5 model configuration |
| `llm_config.deepseek.json` | DeepSeek model configuration |
| `llm_config.minimax.json` | MiniMax model configuration |
| `llm_config.qwen.example.json` | Qwen model example |
| `llm_config.qwen_vl.example.json` | Qwen-VL vision model example |

### Creating Your Configuration

1. Copy a template file:

```bash
cp config/llm_config.template.json config/llm_config.json
```

2. Edit the configuration:

```json
{
  "model_name": "your-model-name",
  "api_key": "your-api-key",
  "base_url": "https://your-api-endpoint",
  "temperature": 0.7,
  "max_tokens": 4096,
  "timeout": 300,
  "provider": "openai",
  "thinking": {
    "type": "disabled"
  },
  "provider_config": {
    "stream": true
  },
  "agent_models": {
    "document_structure_analyzer": {
      "model_name": "your-model-name",
      "api_key": "your-api-key",
      "base_url": "https://your-api-endpoint",
      "temperature": 0.1,
      "max_tokens": 8000
    }
  }
}
```

### Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `model_name` | Yes | Model identifier (e.g., `gpt-4o`, `claude-3-opus`) |
| `api_key` | Yes | Your API key |
| `base_url` | No | Custom API endpoint (for OpenAI-compatible APIs) |
| `temperature` | No | Sampling temperature (0.0-2.0) |
| `max_tokens` | No | Maximum response tokens |
| `timeout` | No | Request timeout in seconds |
| `provider` | No | Provider type (`openai`, `anthropic`) |
| `thinking` | No | Thinking mode configuration |
| `agent_models` | No | Per-agent model overrides |

### Using Environment Variables

Alternatively, set API key via environment variable:

```bash
# Add to ~/.zshrc or ~/.bashrc
export API_KEY="your-api-key-here"

# Or set for current session
export API_KEY="your-api-key-here"
```

Priority order for configuration:
1. `config/llm_config.json` (highest priority)
2. Environment variable `API_KEY`
3. Default configuration

### Thinking Mode

For models that support reasoning (e.g., Qwen3, GPT-4o):

```json
{
  "thinking": {
    "type": "enabled"
  },
  "enable_thinking": true,
  "provider_config": {
    "stream": true,
    "extra_body": {
      "enable_thinking": true
    }
  }
}
```

## Vision Agent Setup

For multimodal image analysis, use a vision-capable model:

```json
{
  "agent_models": {
    "vision_image_analyzer": {
      "model_name": "Qwen3-VL-30B-A3B-Thinking",
      "api_key": "your-api-key",
      "base_url": "https://your-api-endpoint",
      "enable_thinking": true
    }
  }
}
```

## Verification

Verify your setup:

```bash
# Check installation
gptase --help

# List available agents
gptase list

# List available SOPs
gptase sop --list

# Run a simple test
pytest tests/ -v --tb=short
```

## Troubleshooting

### Import Errors

```bash
# Ensure environment is activated
conda activate llm

# Reinstall in development mode
pip install -e ".[models,dev]" --force-reinstall
```

### API Connection Issues

1. Check `base_url` is correct
2. Verify API key is valid
3. Check network connectivity
4. Increase `timeout` value if needed

### Model Not Found

1. Verify `model_name` matches provider's model ID
2. Check if model is available in your region/plan

## IDE Setup

### VS Code

Recommended extensions:
- Python
- Pylance
- Ruff

Settings (`.vscode/settings.json`):
```json
{
  "python.linting.enabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

### PyCharm

1. Set Python interpreter to conda environment: `~/anaconda3/envs/llm/bin/python`
2. Enable yapf formatter
3. Configure isort for import optimization

---

**Last Updated**: 2026-03-05
