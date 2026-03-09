# Agent API

> [Home](../README.md) → [API](.) → Agent

**File:** `gptase/agents/base.py`

---

## Construction

### From a markdown definition (recommended)

```python
from gptase.agents.base import Agent
from gptase.models.model import Model

model = Model()

# By agent name (looks up .claude/agents/{name}.md)
agent = Agent.from_markdown("enzyme-kinetics-extractor", model_manager=model)

# By direct file path
agent = Agent.from_markdown("/path/to/agent.md", model_manager=model)

# Custom search directory
agent = Agent.from_markdown("my-agent", config_dir=Path("/custom/agents/"))
```

Name lookup supports both hyphens and underscores: `my-agent` and `my_agent` both resolve.

### Direct construction

```python
agent = Agent(
    system_prompt="You are a helpful assistant.",
    tools=["Read", "Grep", "Bash"],
    model_config=model_config,      # ModelConfig instance
    model_name="claude-sonnet-4-6", # for routing only (if no model_config)
    agent_id="my-agent",
    workspace_dir="/path/to/workspace",
)
```

---

## Execution

### `run()` — main entry point

```python
result = await agent.run(
    content: Union[str, List[Dict]],    # text string or pre-built content list
    image_paths: Optional[List[str]] = None,
) -> Dict[str, Any]
```

**Returns:**
```python
{"status": "success", "data": {"content": "..."}}   # on success
{"status": "error",   "error": "..."}               # on error
{"status": "error",   "error": "...", "agent_id": "..."}  # on process_task error
```

**Routing logic:** if `model_name.startswith("claude-")` → Claude SDK; otherwise → LLM loop.

### `process_task()` — structured input

```python
result = await agent.process_task(task: AgentTask) -> Dict[str, Any]
```

Extracts image paths from the task, builds a formatted prompt (JSON-serialized task fields), then calls `run()`.

### `is_claude_model()`

```python
agent.is_claude_model() -> bool
```

Checks `model_name.startswith("claude-")`. Used internally for routing.

---

## AgentTask

**File:** `gptase/agents/types.py`

Pydantic model with `extra="allow"` — any extra fields are accepted and injected into the prompt as JSON.

```python
from gptase.agents.types import AgentTask

task = AgentTask(
    description="Extract enzyme kinetics",          # optional, default: "Process the following data"
    workspace_dir="/path/to/workspace",             # optional
    image_path="single.png",                        # optional, single image
    image_paths=["img1.png", "img2.png"],           # optional, list
    images=["img3.png"],                            # optional, alternative field
    # any extra fields:
    document_text="...",
    source="Nature 2024",
)

task.to_dict()           # excludes None values
task.get_extra_fields()  # only the non-declared extra fields
AgentTask.from_dict(data_dict)
```

Image deduplication: all three image fields (`image_path`, `image_paths`, `images`) are merged and deduplicated while preserving order.

---

## Image Loading

`Agent._load_image_as_content(image_path)` is called for each image:

1. Opens the file in binary mode
2. Base64-encodes the content
3. Detects MIME type from file extension

| Extension | MIME type |
|---|---|
| `.jpg`, `.jpeg` | `image/jpeg` |
| `.png` | `image/png` |
| `.gif` | `image/gif` |
| `.webp` | `image/webp` |
| other | `image/jpeg` (fallback) |

Returns:
```python
{
    "type": "image_url",
    "image_url": {"url": "data:image/png;base64,<encoded>"}
}
```

Images are prepended to the message content list, followed by the text. If a file is not found or fails to load, a warning is logged and it is skipped (non-fatal).

---

## Markdown Format

Agent files in `.claude/agents/` must have YAML frontmatter:

```markdown
---
name: my-agent
description: One-line description of what this agent does
tools: Read, Grep, Glob, Bash
model: claude-sonnet-4-6
color: blue
---

System prompt body goes here. Everything after the closing --- is the system_prompt.

## Workflow
...

## Output Format
...
```

| Frontmatter field | Required | Description |
|---|---|---|
| `name` | Yes | Agent ID — must match filename stem |
| `description` | Yes | Shown in `gptase list` output |
| `tools` | No | Comma-separated tool names |
| `model` | No | Model override for this agent |
| `color` | No | Display color in Claude Code UI |

---

## AgentDefinition & AgentState

```python
@dataclass
class AgentDefinition:
    name: str
    description: str = ""
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""

    @property
    def agent_id(self) -> str: ...  # alias for name

class AgentState(BaseModel):
    agent_id: str
    status: str = "idle"
    current_task: Optional[str] = None
```

---

*Related: [SOP API →](./sop.md) | [Model API →](./model.md)*
