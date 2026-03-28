# Core Concepts

> [Home](./README.md) → Core Concepts

Five minutes to a working mental model of GPTase.

---

## The Mental Model

```
Your input (text, document path, images)
          |
          v
 [ Orchestrator Runtime ]
 Goal-oriented harness entry point.
 Owns the session, drafts or loads a plan,
 dispatches workers, and evaluates completion.
          |
    ┌─────┴──────┐
    v            v
[ Worker 2a ] [ Worker 2b ] ← parallel dispatch
    └─────┬──────┘
          v
      [ Worker 3 ]          ← sequential dispatch
          |
          v
      Final result
```

---

## Five Core Concepts

### 1. Agent

**What:** A single AI worker. Lives in `.claude/agents/your-agent/your-agent.md` as a markdown file with YAML frontmatter.

**Boundary:** Agents are workers only. They are not the orchestrator. The orchestrator is a separate runtime layer in `gptase/core/`.

**How it runs:** Routes automatically based on model name:

```
model_name.startswith("claude-")
    Yes → claude_agent_sdk.query()         built-in tools, MCP servers, managed loop
    No  → Model.generate() + ToolExecutor  OpenAI-compatible tool calling + MCP tools
```

**Input → Output:**
```python
result = await agent.run("your task description")
# {"status": "success", "data": {"content": "..."}}
```

**Key file:** `gptase/agents/base.py` — `Agent` class
**Deep dive:** [api/agent.md](./api/agent.md)

---

### 2. Orchestrator Harness

**What:** `AgentOrchestrator` is the primary runtime entry point for multi-step work.
It is not a markdown-defined agent. It accepts a task submission, owns the goal session,
creates or loads a draft plan, dispatches workers, and decides whether the goal is complete,
awaiting approval, awaiting user input, or needs another draft.

**How it works:**
- Every orchestrated run gets a session ID
- The runtime can start from a predefined draft plan in `config/plans/*.yaml` or from a generated draft
- Worker tasks run sequentially or in parallel groups
- Data flows between steps using `{{step1}}`, `{{step2a.field}}` template variables
- Goal evaluation decides whether to stop, request approval, wait for user input, or generate another draft

**Key file:** `gptase/core/orchestrator.py` — `AgentOrchestrator`
**Deep dive:** [api/plan.md](./api/plan.md)

---

### 3. PlanManager + TaskDispatcher

**What:** The internal execution engine behind the harness runtime.

**Boundary:** These are not user-facing orchestrator entry points. `PlanManager` creates and executes a single draft plan. `TaskDispatcher` runs individual worker tasks.

**How it works:**
- `PlanManager.create_plan()` drafts a plan from a natural-language goal
- `PlanManager.execute_plan()` runs the plan DAG
- `TaskDispatcher` sends each ready task to the assigned worker agent
- The orchestrator runtime wraps these pieces with session, approval, and re-plan logic

**Key files:** `gptase/agents/planner.py`, `gptase/agents/plan_dispatcher.py`
**Deep dive:** [api/plan.md](./api/plan.md)

---

### 4. Model

**What:** The LLM abstraction layer. Wraps any OpenAI-compatible provider.

**What it handles:**
- Per-agent model configuration (different agents can use different models)
- Provider instance caching (reuses HTTP connections)
- Optional conversation tracking to SQLite
- Streaming responses

**Key file:** `gptase/models/model.py` — `Model` class
**Deep dive:** [api/model.md](./api/model.md)

---

### 5. FrameworkConfig

**What:** Single source of truth for all settings. Loaded once and used everywhere.

**What it also carries now:**
- per-agent model overrides via `agent_models`
- provider routing/options via `provider`
- MCP tool server definitions via `mcp_servers`

**Load priority:**
1. `GPTASE_LLM_CONFIG` environment variable
2. `config/llm_config.template.json` (default)

**Key file:** `gptase/utils/config.py` — `FrameworkConfig`
**Deep dive:** [api/config.md](./api/config.md)

---

### 6. Skill

**What:** Reusable prompt fragments defined in `.claude/skills/{name}/SKILL.md`.

**How it works:**
- Agent declares `skills: skill1, skill2` in YAML frontmatter
- Skill content is automatically appended to system_prompt on load
- Used to encapsulate common workflows, domain knowledge, or guides

**Example:**
```markdown
---
name: my-agent
skills: pdf-extractor, code_analysis
---
```

**Key file:** `gptase/agents/base.py` — `Agent._load_skill_content()`
**Deep dive:** [api/agent.md#skills](./api/agent.md#skills)

---

## Directory Map

```
.claude/agents/          Agent definitions (directory layout)
  {name}/{name}.md       Agent definition file     ← add agents here
.claude/skills/          Skill definitions (*/SKILL.md) ← add skills here
config/plans/             Plan workflows (*.yaml)     ← add workflows here
config/llm_config.*.json LLM configuration          ← set API keys here

gptase/agents/           Agent execution logic
gptase/core/             Orchestrator harness runtime
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
2. An `Agent` is created from the matching `.md` file
3. `Agent.run()` routes to Claude SDK or LLM loop
4. Result is printed to stdout

```bash
gptase plan -p enzyme_extraction_pipeline -i paper.md
```

1. `PlanRegistry` loads `config/plans/enzyme_extraction_pipeline.yaml`
2. `AgentOrchestrator` creates a goal session and attaches the draft plan
3. `PlanManager` executes the draft plan inside the harness runtime
4. Each workflow step dispatches to a worker `Agent` via `TaskDispatcher`
5. Template variables (`{{step1}}`) are resolved from completed step results
6. Goal evaluation decides whether the session is complete or needs another draft
7. Session state is saved to SQLite between turns

---

*Next: [Common Tasks →](./common-tasks.md)*
