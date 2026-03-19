# Core Concepts

> [Home](./README.md) → Core Concepts

Five minutes to a working mental model of GPTase.

---

## The Mental Model

```
Your input (text, document path, images)
          |
          v
      [ Agent ]
      Single AI worker. Defined in .claude/agents/*.md.
      Runs one task, returns {"status", "data", "error"}.
          |
          v
  [ Plan Orchestrator ]
  Reads a workflow from config/plans/*.yaml.
  Passes data between steps using {{template}} variables.
          |
    ┌─────┴──────┐
    v            v
[ Step 2a ]  [ Step 2b ]   ← parallel group
    └─────┬──────┘
          v
      [ Step 3 ]           ← sequential step
          |
          v
      Final result
```

---

## Five Core Concepts

### 1. Agent

**What:** A single AI worker. Lives in `.claude/agents/your-agent.md` as a markdown file with YAML frontmatter.

**How it runs:** Routes automatically based on model name:

```
model_name.startswith("claude-")
    Yes → claude_agent_sdk.query()         built-in tools, managed loop
    No  → Model.generate() + ToolExecutor  OpenAI-compatible tool calling
```

**Input → Output:**
```python
result = await agent.run("your task description")
# {"status": "success", "data": {"content": "..."}}
```

**Key file:** `gptase/agents/base.py` — `Agent` class
**Deep dive:** [api/agent.md](./api/agent.md)

---

### 2. Plan (Standard Operating Procedure)

**What:** A YAML workflow that chains agents together. Lives in `config/plans/*.yaml`.

**How it works:**
- Steps run sequentially or in parallel groups
- Data flows between steps using `{{step1}}`, `{{step2a.field}}` template variables
- Failed steps can be retried, skipped, or abort the workflow
- Every run gets a session ID; interrupted runs can be resumed

**Key file:** `gptase/plan/orchestrator_agent.py` — `PlanOrchestratorAgent`
**Deep dive:** [api/plan.md](./api/plan.md)

---

### 3. Model

**What:** The LLM abstraction layer. Wraps any OpenAI-compatible provider.

**What it handles:**
- Per-agent model configuration (different agents can use different models)
- Provider instance caching (reuses HTTP connections)
- Optional conversation tracking to SQLite
- Streaming responses

**Key file:** `gptase/models/model.py` — `Model` class
**Deep dive:** [api/model.md](./api/model.md)

---

### 4. FrameworkConfig

**What:** Single source of truth for all settings. Loaded once and used everywhere.

**Load priority:**
1. `GPTASE_LLM_CONFIG` environment variable
2. `config/llm_config.template.json` (default)

**Key file:** `gptase/utils/config.py` — `FrameworkConfig`
**Deep dive:** [api/config.md](./api/config.md)

---

### 5. Skill

**What:** Reusable prompt fragments defined in `.claude/skills/{name}/SKILL.md`.

**How it works:**
- Agent declares `skills: skill1, skill2` in YAML frontmatter
- Skill content is automatically appended to system_prompt on load
- Used to encapsulate common workflows, domain knowledge, or guides

**Example:**
```markdown
---
name: my-agent
skills: academic-pdf-reader, code_analysis
---
```

**Key file:** `gptase/agents/base.py` — `Agent._load_skill_content()`
**Deep dive:** [api/agent.md#skills](./api/agent.md#skills)

---

## Directory Map

```
.claude/agents/          Agent definitions (*.md)   ← add agents here
.claude/skills/          Skill definitions (*/SKILL.md) ← add skills here
config/plans/             Plan workflows (*.yaml)     ← add workflows here
config/llm_config.*.json LLM configuration          ← set API keys here

gptase/agents/           Agent execution logic
gptase/plan/              Plan system
gptase/models/           LLM providers
gptase/memory/           SQLite persistence
gptase/tools/            Tool system (for LLM loop)
gptase/utils/            Config, constants, exceptions
gptase/main.py           CLI entry point
```

---

## What Happens When You Run a Task

```bash
gptase agent -n enzyme-kinetics-extractor -d "Extract kinetics from paper"
```

1. `FrameworkConfig` loads from `config/llm_config.template.json`
2. `AgentOrchestrator` scans `.claude/agents/` to discover agents
3. An `Agent` is created from the matching `.md` file
4. `Agent.run()` routes to Claude SDK or LLM loop
5. Result is printed to stdout

```bash
gptase plan -p enzyme_extraction_pipeline -i paper.md
```

1. `PlanRegistry` loads `config/plans/enzyme_extraction_pipeline.yaml`
2. `PlanOrchestratorAgent` creates an `ExecutionContext` with a session ID
3. Each workflow step dispatches to an `Agent` via `TaskDispatcher`
4. Template variables (`{{step1}}`) are resolved from completed step results
5. Checkpoints are saved to SQLite after each step
6. Output is organized into `analysis/`, `extraction/`, `vision/`, `summary/` dirs

---

*Next: [Common Tasks →](./common-tasks.md)*
