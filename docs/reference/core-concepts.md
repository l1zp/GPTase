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

**What:** The default execution mode (`gptase chat`). The orchestrator agent
runs in a loop where it can answer directly or delegate to worker agents via
DelegateTask.

**How it works:**
- The orchestrator agent runs a turn loop with tool calls and trace collection
- If runtime returns `final_answer` -> result returned immediately (terminal even with delegations)
- If delegations occurred but no final_answer -> followup prompt built, loop continues (capped at `_MAX_COORDINATOR_TURNS`)
- No coordinator activity at all -> error

**Two exit paths:**
- Direct answer: returned after one turn
- Coordinator loop: returned after multi-turn delegation + LLM synthesis

**Key file:** `gptase/core/orchestrator.py` — `AgentOrchestrator._execute_coordinator`
**Deep dive:** [internals/execution-flow.md](./internals/execution-flow.md)

---

### 3. Plan Templates

**What:** Plan templates are YAML files under `config/plans/*.yaml` that
describe "in this order, with these workers, do this work." They are **not**
execution schedules — they seed the Coordinator session's prompt.

**How it works:**
- The user runs `gptase chat -p <plan_id> -i <doc>` to start a session
- `expand_plan_to_prompt` renders the YAML into a structured to-do prompt
- The Coordinator schedules DelegateTask calls in the order described
- `replicas` / `parallel_with` issue concurrent calls in one assistant message
- Workers marked `deterministic: true` bypass the LLM and call their tool directly

**Key file:** `gptase/agents/plan_prompt.py` — `expand_plan_to_prompt`
**Deep dive:** [../../CLAUDE.md#adding-a-new-plan](../../CLAUDE.md)

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
gptase chat -p enzyme_extraction_pipeline -i paper.md
```

1. The CLI loads `config/plans/enzyme_extraction_pipeline.yaml`
2. `expand_plan_to_prompt` renders the YAML as a structured to-do prompt
3. `AgentOrchestrator.dispatch` enters Coordinator mode
4. The Coordinator emits `DelegateTask` calls in the order described
5. Each worker output is written to `<workspace>/worker_results/NNN_*.json`
6. Downstream steps reference upstream artifacts via `output_path` strings
7. The Coordinator returns the final synthesis as the result

---

*Next: [Common Tasks →](./common-tasks.md)*
