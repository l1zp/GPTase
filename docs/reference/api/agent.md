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

# By agent name (looks up .claude/agents/{name}/{name}.md or .claude/agents/{name}.md)
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
    max_iterations=10,              # max tool turns / max Claude SDK turns
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

`max_iterations` is applied in both paths:
- Claude SDK path: passed as `max_turns`
- Non-Claude path: passed to `ToolExecutor(max_iterations=...)`

### `process_task()` — structured input

```python
result = await agent.process_task(task: Task) -> Dict[str, Any]
```

Extracts image paths from the task, builds a formatted prompt (JSON-serialized task fields), then calls `run()`.

### `is_claude_model()`

```python
agent.is_claude_model() -> bool
```

Checks `model_name.startswith("claude-")`. Used internally for routing.

---

## Task

**File:** `gptase/agents/types.py`

Pydantic model with `extra="allow"` — any extra fields are accepted and injected into the prompt as JSON.

```python
from gptase.agents.types import Task

task = Task(
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
Task.from_dict(data_dict)
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

Agent files in `.claude/agents/` must have YAML frontmatter. Two layouts are supported:

```
.claude/agents/
  {name}/{name}.md     # Directory layout (recommended)
  {name}.md            # Flat layout (legacy compatibility)
```

**Directory layout (recommended):**
```
.claude/agents/my-agent/
  my-agent.md          # Agent definition file
```

**File format:**

```markdown
---
name: my-agent
description: One-line description of what this agent does
tools: Read, Grep, Glob, Bash
skills: pdf-extractor, academic-search
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
| `skills` | No | Comma-separated skill names, content appended to system_prompt |
| `model` | No | Informational only at the moment; `Agent.from_markdown()` does not apply it |
| `color` | No | Display color in Claude Code UI |
| `max_iterations` | No | Maximum tool-call iterations / Claude SDK turns. Default: `10` |

> Current behavior: per-agent model selection comes from `FrameworkConfig.agent_models`, not from the markdown `model:` frontmatter.

---

## Skills {#skills}

Skills are reusable prompt fragments defined in `.claude/skills/{skill_name}/SKILL.md`. When an agent loads, specified skill content is appended to the system_prompt.

### Skill File Format

Each skill directory contains a `SKILL.md` file:

```markdown
---
name: pdf-extractor
description: |
  Extract content from PDF documents with MinerU.
  Trigger for requests like "read this PDF", "OCR this scanned PDF", or "extract tables from this PDF".
---

# PDF Extractor

Use MinerU to turn PDFs into Markdown and structured content.

## Routing

1. Prefer MinerU Cloud API when `MINERU_TOKEN` is available.
2. Use `flash-extract` only for small/simple PDFs when no token is available.
3. Use local CLI extraction as a fallback for OCR, tables, formulas, or large PDFs.
```

Skill files also use YAML frontmatter. The `description` field is used for trigger word matching.

### Directory Structure

```
.claude/skills/{skill_name}/
  SKILL.md              # Skill definition (required)
  agents/openai.yaml    # UI metadata (optional)
  evals/evals.json      # Behavior eval cases (optional)
  references/           # On-demand reference files (optional)
  tests/
    trigger_eval.json   # Trigger condition test cases (optional)
```

### Loading Mechanism

```python
# Internal flow in Agent.from_markdown():
# 1. Parse skills field from YAML frontmatter
# 2. Load content from .claude/skills/{skill_name}/SKILL.md
# 3. Strip skill file's frontmatter
# 4. Append skill body to agent system_prompt
```

### Example

Agent definition (`.claude/agents/research-agent/research-agent.md`):

```markdown
---
name: research-agent
description: Research assistant with PDF reading capabilities
tools: Read, Grep, Glob
skills: pdf-extractor, academic-search
---

You are a research assistant specialized in academic research.

## Key Focus

1. Literature search and analysis
2. Data extraction and organization
```

Actual system_prompt after loading:

```
You are a research assistant specialized in academic research.

## Key Focus

1. Literature search and analysis
2. Data extraction and organization

# PDF Extractor

Use MinerU to turn PDFs into Markdown and structured content...

# Academic Search

Search academic papers and publication metadata via OpenAlex, Semantic Scholar, Crossref, and Europe PMC...
```

### Built-in Skills

| Skill | Purpose |
|---|---|
| `pdf-extractor` | PDF extraction with MinerU, preferring Cloud API when `MINERU_TOKEN` is set |
| `biochem_databases` | Biochemical database queries (Rhea, KEGG, PDB, UniProt, PubChem, ChEBI, etc.) |
| `academic-search` | Academic literature search across OpenAlex, Semantic Scholar, Crossref, and Europe PMC |

### Skill Testing

Each skill can include test cases to verify trigger conditions work correctly.

**Test file location:** `.claude/skills/{skill_name}/tests/trigger_eval.json`

**Basic test case format:**

```json
[
  {"query": "Query that should trigger", "should_trigger": true},
  {"query": "Query that should NOT trigger", "should_trigger": false}
]
```

**Boundary test case (validates execution behavior):**

```json
{
  "query": "Search for articles about kemp enzyme published this year",
  "should_trigger": true,
  "category": "boundary",
  "expected_behavior": {
    "use_openalex_api": true,
    "filter_by_date": true,
    "search_keyword": "kemp enzyme",
    "NOT_use_biochem_databases": true
  },
  "reason": "Intent is literature search, not biochemical data query"
}
```

Boundary test cases verify:
- Correct skill is triggered (avoiding multi-skill keyword conflicts)
- Correct API/tool is used
- Correct parameters are applied (date filters, keywords, etc.)

**Running tests:**

```bash
# Test a specific skill
gptase agent -n skill-tester -d "Test biochem_databases skill"

# Specify test file
gptase agent -n skill-tester -d "Test biochem_databases skill with .claude/skills/biochem_databases/tests/trigger_eval.json"
```

---

## AgentDefinition & AgentState

```python
@dataclass
class AgentDefinition:
    name: str
    description: str = ""
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""
    skills: List[str] = field(default_factory=list)  # loaded skill names

    @property
    def agent_id(self) -> str: ...  # alias for name

class AgentState(BaseModel):
    agent_id: str
    status: str = "idle"
    current_task: Optional[str] = None
```

---

*Related: [Plan API →](./plan.md) | [Model API →](./model.md)*
