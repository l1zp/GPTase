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

## Running Plan Workflows

### Execute an Plan from code

```python
import asyncio
from gptase.plan import PlanOrchestratorAgent

async def main():
    orchestrator = PlanOrchestratorAgent()
    try:
        result = await orchestrator.execute_plan(
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

→ Full API: [api/plan.md](./api/plan.md)

### Resume a failed session

```bash
gptase plan --list-sessions
gptase plan --resume plan_20240301_120000_abc12345
```

```python
orchestrator = PlanOrchestratorAgent()
result = await orchestrator.resume_plan(session_id="plan_20240301_120000_abc12345")
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
gptase plan -p enzyme_extraction_pipeline -i paper.md
```

### Enable thinking / reasoning mode

In config:
```json
{ "enable_thinking": true }
```

Or per-agent:
```json
{
  "agent_models": {
    "my-agent": { "enable_thinking": true }
  }
}
```

---

## Adding New Components

### Add a new agent (no code required)

Create `.claude/agents/my-agent/my-agent.md`:

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

### Add a new Plan workflow (no code required)

Create `config/plans/my_pipeline.yaml`:

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
gptase plan --list   # my_pipeline should appear
```

→ Full YAML schema: [api/plan.md#yaml-schema](./api/plan.md#yaml-schema)

---

## Testing Skill Trigger Conditions

### Create Test Case File

Create `tests/trigger_eval.json` under the skill directory:

```
.claude/skills/my-skill/
  SKILL.md
  tests/
    trigger_eval.json
```

Test case format:

```json
[
  {"query": "User input that should trigger", "should_trigger": true},
  {"query": "User input that should NOT trigger", "should_trigger": false}
]
```

Example (biochem_databases skill):

```json
[
  {"query": "Find the reaction for EC 2.7.1.1 in the Rhea database", "should_trigger": true},
  {"query": "Search for recent papers about CRISPR", "should_trigger": false}
]
```

### Run Skill Tests

Use the `skill-tester` agent to test trigger conditions:

```bash
# Simplified command - auto-finds default test file
gptase agent -n skill-tester -d "Test biochem_databases skill"

# Specify test file path
gptase agent -n skill-tester -d "Test biochem_databases skill with .claude/skills/biochem_databases/tests/trigger_eval.json"
```

### Test Report Output

After testing completes, a Markdown report is generated containing:

| Section | Description |
|---|---|
| **Summary** | Total tests, pass/fail counts, accuracy percentage |
| **Extracted Conditions** | Trigger conditions extracted from the skill |
| **Test Results** | Detailed results and reasoning for each test case |
| **Failed Cases** | Analysis of failures with improvement suggestions |
| **Recommendations** | Suggestions for optimizing trigger conditions |

### Sample Test Report

```markdown
# Skill Test Report: biochem_databases

## Summary
| Metric | Value |
|--------|-------|
| Total Test Cases | 20 |
| Passed | 20 |
| Failed | 0 |
| Accuracy | 100% |

## Test Results
| # | Query | Expected | Predicted | Result | Reason |
|---|-------|----------|-----------|--------|--------|
| 1 | "Find EC 2.7.1.1..." | true | true | PASS | Contains "EC" keyword |
| 2 | "Search papers..." | false | false | PASS | Matches "Do NOT trigger for literature" |
```

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

## Web UI

### Start Web UI

```bash
# First time: build frontend
cd ui && ./build.sh

# Start server (default http://127.0.0.1:8000)
gptase web

# Custom port and host
gptase web --port 8080 --host 0.0.0.0
```

Browser opens automatically on startup.

### Features

| Module | Description |
|---|---|
| **Chat** | Chat with agents, Markdown rendering, select different agents or use Auto mode for automatic orchestration |
| **Plan Planning** | Visualize Plan workflows, show execution steps and parallel branches, one-click execution |
| **Sessions** | View execution history with progress bars |

### Chat with agent via API

```python
import requests

response = requests.post("http://127.0.0.1:8000/api/chat", json={
    "agent_id": "enzyme-kinetics-extractor",
    "message": "Extract Km values from this text...",
    "image_paths": ["/path/to/figure.png"],  # optional
})
result = response.json()
print(result["data"]["content"])
```

### Start Plan via API

```python
import requests

# Start Plan
response = requests.post("http://127.0.0.1:8000/api/plan/run", json={
    "plan_id": "enzyme_extraction_pipeline",
    "input_data": {"text": open("paper.md").read()},
    "document_path": "/path/to/paper_dir",  # optional
})
session_id = response.json()["session_id"]

# Check status
status = requests.get(f"http://127.0.0.1:8000/api/sessions/{session_id}").json()
print(status["progress"], status["status"])
```

→ Full API docs: [api/web.md](./api/web.md)

---

## Debugging

### Enable debug logging

```bash
gptase plan -p my_pipeline -i paper.md --debug
```

### Check session status

```bash
gptase plan --session-status plan_20240301_120000_abc12345
```

### Disable checkpoints (for testing)

```bash
gptase plan -p my_pipeline -i paper.md --no-checkpoint
```

### Health check

```python
model = Model()
status = await model.health_check()
print(status)
```

---

*Next level of detail: [api/ →](./api/agent.md)*
