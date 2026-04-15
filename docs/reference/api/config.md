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
| `llm_model` | `str` | `"gpt-4"` | Default model name |
| `llm_api_key` | `Optional[str]` | env `OPENAI_API_KEY` | API key |
| `llm_base_url` | `Optional[str]` | `"https://aiping.cn/api/v1"` | API endpoint URL |
| `llm_temperature` | `float` | `0.1` | Sampling temperature |
| `llm_max_tokens` | `int` | `131072` | Max output tokens |
| `llm_timeout` | `Optional[int]` | `None` → `600` | Request timeout (seconds) |
| `llm_stream` | `bool` | `True` | Enable streaming |
| `llm_enable_thinking` | `bool` | `False` | Enable reasoning/thinking mode |
| `llm_provider` | `Optional[Dict[str, Any]]` | `None` | Provider-specific routing/options passed via `extra_body.provider` |
| `agent_models` | `Dict[str, Dict]` | `{}` | Per-agent model overrides |
| `mcp_servers` | `Dict[str, Dict[str, Any]]` | `{}` | MCP server definitions used to register runtime tools |
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
  "model_name": "GLM-5",
  "base_url": "https://aiping.cn/api/v1",
  "temperature": 1,
  "max_tokens": 131072,
  "timeout": 300,
  "stream": true,
  "enable_thinking": false,
  "provider": {
    "sort": "input_length"
  },
  "mcp_servers": {
    "_comment": {
      "note": "Documentation/example entries starting with _ are ignored by FrameworkConfig."
    },
    "brave-search": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "YOUR_BRAVE_API_KEY"
      }
    }
  },
  "agent_models": {
    "vision-image-analyzer": {
      "model_name": "Qwen3-VL-30B-A3B-Thinking",
      "max_tokens": 131072,
      "enable_thinking": true
    },
    "enzyme-kinetics-extractor": {
      "model_name": "GLM-5",
      "temperature": 0.1
    },
    "deep-research-eval-agent": {
      "provider": {
        "sort": "input_length"
      }
    }
  }
}
```

### JSON key → FrameworkConfig field mapping

When loading from JSON, these key names are remapped:

| JSON key | FrameworkConfig field |
|---|---|
| `model_name` | `llm_model` |
| `api_key` | `llm_api_key` |
| `base_url` | `llm_base_url` |
| `temperature` | `llm_temperature` |
| `max_tokens` | `llm_max_tokens` |
| `timeout` | `llm_timeout` |
| `stream` | `llm_stream` |
| `enable_thinking` | `llm_enable_thinking` |
| `provider` | `llm_provider` when the JSON value is an object |

Fields not in this mapping (e.g., `agent_models`, `memory`, `log_level`) are passed through unchanged.

> Legacy scalar `provider` values are still ignored for backward compatibility. Object-valued `provider` is now reserved for provider routing/options.

### `mcp_servers`

Each entry defines one MCP server connection. Supported keys:

| Key | Type | Required | Notes |
|---|---|---|---|
| `transport` | `str` | No | `"stdio"` (default) or `"sse"` |
| `command` | `str` | stdio only | Command to launch the MCP server |
| `args` | `List[str]` | No | CLI arguments for stdio servers |
| `env` | `Dict[str, str]` | No | Environment variables for the server process |
| `cwd` | `str` | No | Working directory for stdio servers |
| `url` | `str` | sse only | SSE endpoint URL |

Entries whose names start with `_` are ignored. This lets the config template include inline comments/examples like `_comment`.

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
# API Key (used for aiping.cn and other OpenAI-compatible endpoints)
OPENAI_API_KEY=your-api-key

# MCP Server Keys
BRAVE_API_KEY=your-brave-key
TAVILY_API_KEY=your-tavily-key
```

**Priority:** `api_key` in config file > `OPENAI_API_KEY` environment variable

> Best practice: Don't set `api_key` in JSON config files, manage all keys through `.env`.

### Supported Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | API key for OpenAI-compatible endpoint |
| `BRAVE_API_KEY` | MCP Brave Search service key |
| `TAVILY_API_KEY` | MCP Tavily Search service key |
| `GPTASE_LLM_CONFIG` | Path to custom config file |

### GPTASE_LLM_CONFIG

Supports both absolute and relative paths (relative = from project root):

```bash
# Absolute
export GPTASE_LLM_CONFIG=/home/user/my_config.json

# Relative to project root
export GPTASE_LLM_CONFIG=config/llm_config.glm5.json

# Per-command override
GPTASE_LLM_CONFIG=config/llm_config.glm5.json gptase plan -p my_pipeline -i paper.md
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
    db_path: str = "data/conversations.db"
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
