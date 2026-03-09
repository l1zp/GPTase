# Common Tasks

> [Home](./README.md) → Common Tasks

Code recipes for everyday development. Each task links to the relevant API page for full details.

---

## Running Agents

### Run a single agent from code

```python
import asyncio
from gptase.agents.base import Agent
from gptase.models.model import Model

async def main():
    model = Model()
    agent = Agent.from_markdown("enzyme-kinetics-extractor", model_manager=model)

    result = await agent.run("Extract all Km and kcat values from this text: ...")
    print(result["status"])           # "success" or "error"
    print(result["data"]["content"])  # agent output

asyncio.run(main())
```

→ Full API: [api/agent.md](./api/agent.md)

### Run a vision (multimodal) task

```python
result = await agent.run(
    content="Extract numerical data from these figures",
    image_paths=["figure1.png", "figure2.png"],
)
```

Images are base64-encoded and sent alongside the text. Supported formats: `.png`, `.jpg`, `.gif`, `.webp`.

→ Image loading details: [api/agent.md#image-loading](./api/agent.md#image-loading)

### Pass structured data as a task

```python
from gptase.agents.types import AgentTask

task = AgentTask(
    description="Extract enzyme kinetics",
    image_paths=["table.png"],
    document_text="Full paper text...",   # any extra field goes into the prompt
    source="Nature 2024",                 # any extra field goes into the prompt
)
result = await agent.process_task(task)
```

→ AgentTask details: [api/agent.md#agenttask](./api/agent.md#agenttask)

---

## Running SOP Workflows

### Execute an SOP from code

```python
import asyncio
from gptase.sop import SOPOrchestratorAgent

async def main():
    orchestrator = SOPOrchestratorAgent()
    try:
        result = await orchestrator.execute_sop(
            plan_id="enzyme_extraction_pipeline",
            input_data={"text": open("paper.md").read()},
            document_path="/path/to/paper_dir",
            workspace_dir="/path/to/workspace",
            auto_checkpoint=True,
        )
        print(result["step_results"]["1"])   # step 1 output
        print(result["step_results"]["2a"])  # step 2a output
    finally:
        await orchestrator.close()  # always close — prevents SQLite errors

asyncio.run(main())
```

→ Full API: [api/sop.md](./api/sop.md)

### Resume a failed session

```bash
gptase sop --list-sessions
gptase sop --resume sop_20240301_120000_abc12345
```

```python
orchestrator = SOPOrchestratorAgent()
result = await orchestrator.resume_sop(session_id="sop_20240301_120000_abc12345")
await orchestrator.close()
```

→ Checkpoint internals: [internals/execution-flow.md](./internals/execution-flow.md)

---

## Configuration

### Use a different model for a specific agent

In `config/llm_config.template.json`:

```json
{
  "model_name": "gpt-4",
  "api_key": "sk-...",
  "agent_models": {
    "vision-image-analyzer": {
      "model_name": "gpt-4o",
      "max_tokens": 4000
    },
    "enzyme-kinetics-extractor": {
      "model_name": "gpt-4-turbo",
      "temperature": 0.0
    }
  }
}
```

No code changes needed. `Model.get_config_for_agent()` resolves this automatically.

→ Full config reference: [api/config.md](./api/config.md)

### Point to a custom config file

```bash
export GPTASE_LLM_CONFIG=/path/to/my_config.json
gptase sop -p enzyme_extraction_pipeline -i paper.md
```

### Enable thinking / reasoning mode

In config:
```json
{ "thinking": { "type": "enabled" } }
```

Or per-agent:
```json
{
  "agent_models": {
    "my-agent": { "thinking": { "type": "enabled" } }
  }
}
```

---

## Adding New Components

### Add a new agent (no code required)

Create `.claude/agents/my-agent.md`:

```markdown
---
name: my-agent
description: Describe what this agent does and when to use it
tools: Read, Grep, Glob
skills: academic-pdf-reader, code_analysis
model: claude-sonnet-4-6
---

You are a specialized agent for...

## Workflow

1. Read the input...
2. Extract...

## Output Format

Return JSON:
```json
{"field": "value"}
```
```

Verify:
```bash
gptase list   # my-agent should appear
```

→ Full format spec: [api/agent.md#markdown-format](./api/agent.md#markdown-format)

### Add a new skill

Create `.claude/skills/my-skill/SKILL.md`:

```markdown
---
name: my-skill
description: |
  What this skill does and trigger phrases.
  Triggers on: "keyword1", "keyword2".
---

# My Skill

Detailed instructions for this skill...

## Workflow
1. Step one...
2. Step two...

## Output
Expected output format...
```

Use in an agent:
```markdown
---
name: my-agent
skills: my-skill
---
...
```

→ Skills API: [api/agent.md#skills](./api/agent.md#skills)

### Add a new SOP workflow (no code required)

Create `config/sops/my_pipeline.yaml`:

```yaml
plan_id: my_pipeline
name: "My Pipeline"
version: "1.0"

workflow:
  - step_id: "1"
    agent: document-structure-analyzer
    inputs:
      text: "{{input_text}}"

  - parallel:
      - step_id: "2a"
        agent: my-extractor-a
        inputs:
          text: "{{input_text}}"
          structure: "{{step1}}"
      - step_id: "2b"
        agent: my-extractor-b
        inputs:
          images: "{{step1.images}}"

  - step_id: "3"
    agent: my-summarizer
    inputs:
      results_a: "{{step2a}}"
      results_b: "{{step2b}}"
```

Verify:
```bash
gptase sop --list   # my_pipeline should appear
```

→ Full YAML schema: [api/sop.md#yaml-schema](./api/sop.md#yaml-schema)

---

## LLM & Streaming

### Enable streaming responses

```python
from gptase.models.model import Model

model = Model()
async for chunk in model.generate_stream(messages):
    print(chunk.content, end="", flush=True)
    if chunk.reasoning_content:
        print(f"[thinking] {chunk.reasoning_content}")
```

→ Full streaming API: [api/model.md#streaming](./api/model.md#streaming)

### Enable conversation tracking

```python
model = Model(enable_tracking=True, tracking_db_path="data/conversations.db")
await model.initialize_tracking()
response = await model.generate(messages, agent_name="my-agent")
await model.shutdown()
```

→ Memory system: [api/memory.md](./api/memory.md)

### Generate with retry

```python
response = await model.generate_with_retry(messages, max_retries=3)
```

Uses exponential backoff: waits `2^attempt` seconds between retries.

---

## Debugging

### Enable debug logging

```bash
gptase sop -p my_pipeline -i paper.md --debug
```

### Check session status

```bash
gptase sop --session-status sop_20240301_120000_abc12345
```

### Disable checkpoints (for testing)

```bash
gptase sop -p my_pipeline -i paper.md --no-checkpoint
```

### Health check

```python
model = Model()
status = await model.health_check()
print(status)
```

---

*Next level of detail: [api/ →](./api/agent.md)*
