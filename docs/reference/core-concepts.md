# Core Concepts

> [Home](./README.md) → Core Concepts

Five minutes to a working mental model of GPTase.

---

## The Mental Model

```
Your input (text, document path, images)
          |
          v
 [ dispatch routing ]  Three paths: Agent / Coordinator / Plan
     |           |           |
     v           v           v
 [Agent]    [Coordinator]  [Plan]
 Single     Orchestrator    Structured workflow
 agent      loop + delegate DAG dependency tracking
 direct       |
 execute      v
          [Plan Handoff]   coordinator can hand off to Plan
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

### 2. Coordinator Mode

**What:** The default execution mode (`gptase chat`). The orchestrator agent runs in
a loop where it can answer directly, delegate to worker agents via DelegateTask,
or hand off to plan execution.

**How it works:**
- The orchestrator agent runs a turn loop with tool calls and trace collection
- If runtime returns `final_answer` with no delegation -> result returned immediately
- If workers were delegated -> results are merged, followup prompt built, loop continues (up to 3 turns)
- If runtime returns `needs_plan` -> orchestrator hands off to plan execution

**Three exit paths:**
- Direct answer: returned after one turn
- Coordinator loop: returned after multi-turn delegation + synthesis
- Plan handoff: creates a draft plan for review or immediate execution

**Key file:** `gptase/core/orchestrator.py` — `AgentOrchestrator.run_coordinator`
**Deep dive:** [api/plan.md](./api/plan.md)

---

### 3. Plan Execution

**What:** Plan execution is the structured execution layer used after an
explicit plan request or a runtime handoff. Plans execute inline (no session
persistence) and results are returned directly.

**How it works:**
- Plans can come from `plan_id`, `plan_path`, inline plan data, or LLM-generated
- Plans run sequentially or in parallel groups
- Data flows between steps using `{{step1}}`, `{{step2a.field}}` template variables
- Goal evaluation checks whether the objective was met, with optional auto-replan

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
gptase/core/             Coordinator + Plan execution runtime
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
2. `AgentOrchestrator._execute_plan()` resolves or creates the plan
3. Each workflow step dispatches to an `Agent` via `TaskDispatcher`
4. Template variables (`{{step1}}`) are resolved from completed step results
5. Goal evaluation checks whether the objective was met
6. If `auto_replan=True` and the goal is unmet, a follow-up plan is generated
7. Results are returned inline (no session persistence)

---

*Next: [Common Tasks →](./common-tasks.md)*
