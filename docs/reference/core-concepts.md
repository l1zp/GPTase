# Core Concepts

> [Home](./README.md) → Core Concepts

Five minutes to a working mental model of GPTase.

---

## The Mental Model

```
Your input (text, document path, images)
          |
          v
 [ Interactive Runtime ]
 Direct LLM/tool loop for one agent
 Can answer directly or request structured follow-up
          |
          v
 [ Auto Orchestrator ]
 May answer directly, run a coordinator loop, or create a harness session
     |                    |
     v                    v
 [Coordinator Loop]   [Harness Session + Plan]
 DelegateTask worker  Draft plan, approval, execution, replan
 turns + synthesis
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

### 2. Interactive Runtime + Auto Orchestrator

**What:** Every non-Claude agent now runs through an interactive runtime. The Auto
orchestrator uses that runtime first, then decides whether to stop, coordinate
worker tasks, or hand off into plan mode.

**How it works:**
- A single agent runs a turn loop with tool calls and trace collection
- `agent_id="auto"` starts in direct runtime mode first
- If delegation happens, the orchestrator can continue in a coordinator loop
- If runtime returns `needs_plan`, the orchestrator creates a harness session

**Direct answer vs. session creation:**
- Direct runtime answer: no session
- Coordinator loop answer: no session
- Plan handoff: creates a goal session with a draft plan

**Key file:** `gptase/core/orchestrator.py` — `AgentOrchestrator`
**Deep dive:** [api/plan.md](./api/plan.md)

---

### 3. Harness Session + Plan

**What:** The harness session is the structured execution layer used after an
explicit plan request or a runtime handoff.

**How it works:**
- Draft plans can come from `plan_id`, `plan_path`, inline plan data, normal plan
  generation, or `runtime_handoff`
- Draft plans run sequentially or in parallel groups
- Data flows between steps using `{{step1}}`, `{{step2a.field}}` template variables
- A session can wait for approval, execute, evaluate the goal, and auto-replan

**Key file:** `gptase/core/orchestrator.py` — `AgentOrchestrator`
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
gptase/core/             Auto orchestrator + harness runtime
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
2. `Agent.run()` routes to Claude SDK or the interactive runtime
3. The runtime may answer directly, delegate workers, or request plan handoff
4. If plan handoff happens, `AgentOrchestrator` creates a goal session and attaches the draft plan
5. Each workflow step dispatches to an `Agent` via `TaskDispatcher`
6. Goal evaluation decides whether the session is complete or needs another draft
7. Session state is saved to SQLite between turns

---

*Next: [Common Tasks →](./common-tasks.md)*
