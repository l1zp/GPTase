# Config API

> [Home](../README.md) → [API](.) → Config

**File:** `gptase/utils/config.py`

---

## FrameworkConfig

Single source of truth for all framework settings. Loaded once from a JSON template file.

```python
from gptase.utils.config import FrameworkConfig

config = FrameworkConfig()                           # loads from template
config = FrameworkConfig(llm_model="gpt-4o")        # override specific fields
config = FrameworkConfig(**json.load(open("f.json"))) # load from dict
```

### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `llm_provider` | `str` | `"openai"` | Provider identifier |
| `llm_model` | `str` | `"gpt-4"` | Default model name |
| `llm_api_key` | `Optional[str]` | env `OPENAI_API_KEY` | API key |
| `llm_base_url` | `Optional[str]` | `None` | Custom endpoint URL |
| `llm_temperature` | `float` | `0.1` | Sampling temperature |
| `llm_max_tokens` | `int` | `2000` | Max output tokens |
| `llm_timeout` | `Optional[int]` | `None` → `600` | Request timeout (seconds) |
| `llm_thinking` | `Optional[ThinkingConfig]` | `None` | Reasoning mode |
| `llm_provider_config` | `Dict` | `{}` | Provider-specific extras |
| `agent_models` | `Dict[str, Dict]` | `{}` | Per-agent model overrides |
| `memory` | `MemoryConfig` | — | Memory subsystem config |
| `log_level` | `str` | `"INFO"` | Logging level |

### Methods

```python
config.to_model_config() -> ModelConfig
# Converts to a ModelConfig using the default llm_* fields.

config.get_config_for_agent(agent_name: str) -> Optional[ModelConfig]
# Looks up agent_models[agent_name], merges with defaults, returns ModelConfig.
# Normalizes hyphens and underscores: "my-agent" and "my_agent" both match.

config.to_dict() -> Dict[str, Any]
```

---

## Config File Format

### llm_config.template.json (full example)

> API keys should be managed via `.env` file, not stored in JSON.

```json
{
  "provider": "openai",
  "model_name": "gpt-4",
  "base_url": null,
  "temperature": 0.1,
  "max_tokens": 2000,
  "timeout": 600,
  "thinking": {
    "type": "disabled"
  },
  "provider_config": {},
  "agent_models": {
    "vision-image-analyzer": {
      "model_name": "gpt-4o",
      "max_tokens": 4000,
      "temperature": 0.2
    },
    "enzyme-kinetics-extractor": {
      "model_name": "gpt-4-turbo",
      "temperature": 0.0,
      "timeout": 300
    }
  }
}
```

### JSON key → FrameworkConfig field mapping

When loading from JSON, these key names are remapped:

| JSON key | FrameworkConfig field |
|---|---|
| `provider` | `llm_provider` |
| `model_name` | `llm_model` |
| `api_key` | `llm_api_key` |
| `base_url` | `llm_base_url` |
| `temperature` | `llm_temperature` |
| `max_tokens` | `llm_max_tokens` |
| `timeout` | `llm_timeout` |
| `thinking` | `llm_thinking` |
| `provider_config` | `llm_provider_config` |

Fields not in this mapping (e.g., `agent_models`, `memory`, `log_level`) are passed through unchanged.

---

## Environment Variables

### .env File Configuration (Recommended)

All API keys are managed through `.env` file. The framework loads it automatically on startup:

```bash
# Create from template
cp .env.example .env

# Edit with your keys
vim .env
```

`.env` file format:

```bash
# LLM Provider Keys
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GEMINI_API_KEY=your-gemini-key

# Custom Provider
CUSTOM_API_KEY=your-custom-key
CUSTOM_BASE_URL=https://your-api-endpoint.com

# MCP Server Keys
BRAVE_API_KEY=your-brave-key
TAVILY_API_KEY=your-tavily-key
```

**Priority:** `api_key` in config file > `OPENAI_API_KEY` environment variable

> Best practice: Don't set `api_key` in JSON config files, manage all keys through `.env`.

### Supported Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI/compatible API key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `CUSTOM_API_KEY` | Custom provider API key |
| `CUSTOM_BASE_URL` | Custom provider endpoint URL |
| `BRAVE_API_KEY` | MCP Brave Search service key |
| `TAVILY_API_KEY` | MCP Tavily Search service key |
| `GPTASE_LLM_CONFIG` | Path to custom config file |

### GPTASE_LLM_CONFIG

Supports both absolute and relative paths (relative = from project root):

```bash
# Absolute
export GPTASE_LLM_CONFIG=/home/user/my_config.json

# Relative to project root
export GPTASE_LLM_CONFIG=config/llm_config.openai.json

# Per-command override
GPTASE_LLM_CONFIG=config/llm_config.gemini.json gptase sop -p my_pipeline -i paper.md
```

**Load priority:**
1. `GPTASE_LLM_CONFIG` environment variable
2. `config/llm_config.template.json` (default)
3. Hardcoded defaults (if template file is missing)

---

## MemoryConfig

```python
class MemoryConfig(BaseModel):
    type: str = "local"          # storage type
    max_history: int = 1000      # max history entries
```

---

## load_template_config()

Low-level function used by `FrameworkConfig.__init__()`:

```python
from gptase.utils.config import load_template_config

raw_dict = load_template_config()   # returns parsed JSON dict
# Raises ConfigurationError if file missing or invalid JSON
```

---

*Related: [Model API →](./model.md) | [Memory API →](./memory.md)*
