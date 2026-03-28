---
name: agent-creator
description: |
  Design, write, and iteratively improve GPTase agents (.claude/agents/).
  ALWAYS trigger when the user wants to: create a new agent, add an agent for
  a task, write a system prompt for an agent, improve an existing agent's
  instructions, refine agent behavior, make an agent more accurate, or build
  a new capability into the GPTase framework.
  Also trigger for: "the agent keeps doing X wrong", "add a worker agent for",
  "I need an agent that", "write a system prompt for", "the extraction is off".
  Do NOT trigger for: running existing agents (use CLI directly), creating
  Claude Code skills (use skill-creator), debugging Python framework code,
  or evaluating agent quality without intent to improve (use agent-eval).
---

# Agent Creator

Design and iteratively refine GPTase agents through a structured loop:
**draft system prompt → create eval data → run → diagnose → improve → repeat**.

The goal is not just to get a working agent on the first try — it's to build
confidence through reproducible evals that the agent behaves correctly across
varied inputs.

---

## The Design Loop

```
Intent → Draft Agent → Create Eval Data
                            ↓
                    Run Live Eval
                            ↓
                   Score < target? → Diagnose Trace → Improve Prompt
                            ↓
                   Score ≥ target? → Done
```

Run at least one full cycle even if the first draft looks good. Evals catch
failure modes that aren't obvious from reading the system prompt.

---

## Phase 1: Capture Intent

Before writing anything, understand:

1. **What task does this agent perform?** Be specific about inputs and outputs.
2. **What tools does it need?** (Read, Grep, Glob, Bash, DelegateTask, etc.)
3. **What does "correct" output look like?** Get a concrete example — even
   sketched — so you can write meaningful eval assertions.
4. **Is there an existing agent that partially covers this?** Check:
   ```
   Glob: .claude/agents/*/*.md
   ```
   If a similar agent exists, read it for patterns before designing from scratch.

Ask the user these questions if the answers aren't clear from context.

---

## Phase 2: Research Existing Patterns

Read 1-2 agents that are structurally similar to what you're building:

- **Extraction agent** → `enzyme-kinetics-extractor` (Read + Grep, JSON output)
- **Vision agent** → `vision-image-analyzer` (multimodal, structured analysis)
- **Routing agent** → `orchestrator` (DelegateTask, decision-making)
- **Analysis/summary agent** → `enzyme-extraction-summary` (multi-input, report)

Check whether an existing schema in `gptase/evals/schemas.py` covers the
output shape. If not, plan to add one (see Phase 5).

---

## Phase 3: Draft the Agent

Create `.claude/agents/{name}/{name}.md` with this structure:

```markdown
---
name: my-agent
description: One-line description shown in `gptase list`
tools: Read, Grep, Glob      # comma-separated; omit if no tools needed
model: claude-sonnet-4-6     # omit to inherit global default
---

[System prompt starts here — everything after the second --- is the prompt]
```

### Frontmatter fields

| Field | Required | Notes |
|---|---|---|
| `name` | Yes | Must match directory name and filename (no spaces) |
| `description` | Yes | One sentence; shown in `gptase list` output |
| `tools` | No | Comma-separated. Available: Read, Grep, Glob, Bash, DelegateTask |
| `model` | No | Override global default for this agent |
| `color` | No | Display color in Claude Code UI |
| `skills` | No | Comma-separated skill names to load into context |

### System prompt writing guide

A strong system prompt has four parts, in this order:

**1. Role statement** — who the agent is, in one sentence.
> "You are the Enzyme Kinetics Extraction Expert. Your mission is to extract
> every variant and kinetic parameter into structured JSON."

**2. Input format** — what the agent receives. Be explicit about field names
and types the agent will see in its context:
> "You will receive: `document_path` (path to markdown), `relevant_sections`
> (section metadata from structure analyzer), `relevant_tables` (table list)."

**3. Workflow** — numbered steps the agent should follow. Use concrete,
imperative instructions. The agent will follow them literally, so avoid vague
directives like "analyze carefully" — prefer "Use Grep to find all rows
containing `Km`, then Read only those line ranges."

**4. Output format** — a JSON example with exact field names and types. Never
describe the schema in prose; show it. Use `null` for optional fields:
```json
{
  "reactions": [
    {
      "enzyme_name": "...",
      "kinetics": {"Km": 0.0, "Km_unit": "..."}
    }
  ]
}
```

**Common pitfalls to avoid in system prompts:**
- Vague scope ("analyze the document") → prefer targeted tool calls ("Grep for `kcat`")
- Over-relying on agent inference → spell out exactly what to extract
- Missing units in output format → agents drop units if not shown in example
- No "what not to do" rules → agents fill gaps with invented values

**Verify** the agent appears: `conda run -n llm gptase list`

---

## Phase 4: Create Eval Data

Good evals are the difference between "it worked once" and "it reliably works."
Write eval data before running the agent live — it forces you to be precise
about what "correct" means.

### Directory layout

```
.claude/agents/{name}/evals/
  golden.yaml       # Schema name + key fact assertions
  input.md          # Input text the agent will receive
  images/           # Input images (multimodal agents only)
  output/           # Populated by --save-output (don't create manually)
```

### Writing golden.yaml

```yaml
schema: existing_schema_name   # Key from gptase/evals/schemas.py SCHEMA_MAP

key_facts:
  # 1. Structure checks (cheap, run first)
  - field: "reactions"
    condition: length_gte
    value: 3

  # 2. Specific value checks (the real test)
  - field: "reactions[enzyme_name=Des27].kinetics.kcat/KM"
    condition: approx_eq
    value: 130
    tolerance: 0.15

  # 3. Coverage checks (did we miss anything?)
  - field: "reactions[*].enzyme_name"
    condition: contains_all
    values: ["Des27", "Des27.7", "Des27.13"]
```

**Write assertions in order of specificity**: structure first, then specific
values, then coverage. This makes failure messages easier to interpret.

**Good assertion ratio**: aim for 1-2 structure checks, 3-5 specific value
checks, 1-2 coverage checks per agent. Fewer than 5 total assertions gives
low confidence; more than 15 is over-specified.

### Writing input.md

Use a representative real-world example — not a toy case you invented. If the
agent extracts from papers, use an actual paper excerpt. Realistic inputs
surface edge cases (formatting quirks, missing values, ambiguous notation)
that idealized inputs hide.

---

## Phase 5: Run → Diagnose → Improve

### Running evals

```bash
# First run: live (no cached output yet)
conda run -n llm gptase eval -a {agent_name} --live --save-output

# Subsequent runs: use cache first (free, instant)
conda run -n llm gptase eval -a {agent_name}

# After prompt changes: live again to refresh cache
conda run -n llm gptase eval -a {agent_name} --live --save-output
```

### Interpreting results

A passing eval shows:
```
[OK] Schema: vision_analysis
Facts: 9/10 passed (score: 0.90)
```

A failing eval shows which assertions failed and why:
```
[FAIL] vision-image-analyzer: extracted_tables[*].csv_data [contains] --
       "Des27.7" not in ['Des27,131\nDes27.2,89\n...']
```

**Target score**: ≥ 0.85 before considering the agent ready. Below 0.70 means
the system prompt needs substantial rework.

### Diagnosing failures

When assertions fail:

1. **Read `evals/output/output_*.json`** — compare actual values against
   what the assertions expected. Is the field path wrong, or is the agent
   actually extracting wrong values?

2. **Read `evals/output/trace_*.json`** — inspect the full LLM conversation.
   Look at what the agent searched for, what it read, what it reasoned.
   Diagnosis questions:
   - Did the agent search the right places? (wrong Grep queries → wrong scope)
   - Did it read the right lines? (off-by-N ranges → missed rows)
   - Did it produce the right JSON structure but the field path was wrong?

3. **Fix the right thing**:
   - Wrong field path in assertion → fix golden.yaml, not the agent
   - Agent searching wrong terms → improve workflow steps in system prompt
   - Agent inventing values → add explicit "extract only what is written" rule
   - Agent missing items → add coverage guidance ("if a table has N rows,
     extract all N rows")

### Improving the system prompt

Focus changes on the specific failure. Don't rewrite the whole prompt — one
targeted addition often fixes multiple assertions.

After each change:
1. Run `--live --save-output` to refresh the cache
2. Run the cached eval to check score
3. If score improved but others regressed, check for unintended side effects
4. Repeat until score ≥ 0.85

---

## Phase 6: When to Add a New Schema

If no schema in `SCHEMA_MAP` fits the agent's output, add one to
`gptase/evals/schemas.py`:

```python
class MyAgentOutput(BaseModel):
    """Output schema for my-agent."""
    items: Optional[List[MyItem]] = None
    summary: Optional[str] = None

SCHEMA_MAP["my_agent"] = MyAgentOutput
```

Rules for schema design:
- All fields `Optional` — schema validates shape, not completeness
- Use `List[Any]` for list items if the sub-structure varies
- Use `Dict[str, Any]` for free-form nested dicts
- Completeness is enforced by `key_facts`, not by the schema

---

## When to Stop Iterating

The agent is ready when:
- Eval score ≥ 0.85 consistently across two live runs
- All high-priority assertions pass (specific values, coverage)
- The system prompt explains *why* each rule exists (future maintainability)

If you're stuck below 0.70 after 3+ iterations, step back: the problem might
be the model (try `model: claude-opus-4-6`), the input quality (is `input.md`
representative?), or the assertion design (are assertions testing the right
things?).

---

## Quick Reference

```bash
# Verify agent registered
conda run -n llm gptase list

# Run cached eval
conda run -n llm gptase eval -a {agent_name}

# Live eval + save output
conda run -n llm gptase eval -a {agent_name} --live --save-output

# Run agent manually (outside eval)
conda run -n llm gptase agent -n {agent_name} -d "task description"
conda run -n llm gptase agent -n {agent_name} -i input.md
```

---

## Example: Creating an Agent from Scratch

```
User: "I need an agent that reads a markdown table of protein sequences and
       extracts mutation positions and amino acid changes as JSON."

1. Check: no existing agent matches → new agent needed
2. Check schemas.py: no "protein_mutation" schema → plan to add one
3. Research: enzyme-kinetics-extractor uses Read+Grep pattern → use same approach
4. Draft: write protein-mutation-extractor.md
   - Tools: Read, Grep
   - Input: document_path, table line ranges
   - Workflow: Grep for position patterns, Read rows, extract JSON
   - Output: {"mutations": [{"position": 42, "from": "A", "to": "V"}]}
5. Add schema: ProteinMutationOutput with mutations: Optional[List[...]]
6. Write golden.yaml: use real example table, assert specific positions
7. Run: gptase eval -a protein-mutation-extractor --live --save-output
8. Iterate on failures until score ≥ 0.85
```
