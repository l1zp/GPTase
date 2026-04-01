---
name: agent-eval
description: |
  Evaluate GPTase agent output quality, create eval datasets, and diagnose
  failures. ALWAYS trigger when the user wants to: evaluate an agent, run eval,
  check agent quality, test agent output, create golden data, add eval to an
  agent, write golden.yaml, diagnose eval failure, fix failing assertions,
  add a new eval schema. Also trigger for: "how good is agent X", "does agent
  X work correctly", "benchmark agent", "eval agent".
  Do NOT trigger for: running pytest tests (use pytest-writer), general code
  debugging, or agent development questions unrelated to evaluation.
---

# Agent Eval

Evaluate GPTase agent output quality using the built-in three-tier eval
framework: Schema validation, key fact assertions, and completeness metrics.

---

## Framework Overview

The eval framework lives in `gptase/evals/`:

| Component | File | Purpose |
|---|---|---|
| Runner | `gptase/evals/runner.py` | `EvalRunner` -- loads golden data, runs agent, evaluates output |
| Assertions | `gptase/evals/assertions.py` | `validate_schema()`, `evaluate_key_facts()`, `extract_field()` |
| Schemas | `gptase/evals/schemas.py` | Pydantic models in `SCHEMA_MAP` |
| Reports | `gptase/evals/report.py` | `print_eval_report()`, `save_eval_report()` |
| CLI | `gptase/main.py:759` | `gptase eval -a <agent>` subcommand |

Eval data is co-located with each agent:

```
.claude/agents/{agent_name}/
  {agent_name}.md           # Agent definition
  evals/
    golden.yaml             # Expected output spec + assertions
    input.md                # Input text (optional)
    images/                 # Input images (optional)
    output/                 # Cached outputs (optional, from --save-output)
      output_YYYYMMDD_HHMMSS.json   # Parsed agent output
      trace_YYYYMMDD_HHMMSS.json    # Full LLM trace (steps, tokens, timing)
```

---

## Workflow

### Phase 1: Determine intent

Ask the user (or infer from context) which of these they need:

1. **Run eval** -- evaluate an existing agent against its golden data
2. **Create eval** -- set up eval data for an agent that doesn't have it yet
3. **Diagnose failure** -- analyze why assertions are failing
4. **Add schema** -- register a new Pydantic output schema

### Phase 2: Run eval

1. Confirm the agent has eval data:
   ```
   Glob: .claude/agents/{agent_name}/evals/golden.yaml
   ```

2. If no `golden.yaml` exists, switch to Phase 3 (Create eval).

3. Run the eval command:
   ```bash
   # Cached eval (uses saved output, no API cost) -- use this first
   conda run -n llm gptase eval -a {agent_name}

   # Live eval (calls LLM API) -- use when cached output is stale or missing
   conda run -n llm gptase eval -a {agent_name} --live --save-output

   # Live eval with a specific LLM config (e.g., different model or API key)
   conda run -n llm gptase eval -a {agent_name} --live --config config/llm_config.json
   ```

   **When to use cached vs live**: Cached evals are free and instant -- always
   try them first. Use `--live` when: (a) no cached output exists yet, (b) the
   agent prompt changed, or (c) you're debugging flaky behavior.

4. Parse and present the results:
   - Schema validation status ([OK] / [FAIL])
   - Key facts score (X/Y passed, score 0.00-1.00)
   - Any failure details

### Phase 3: Create eval

For an agent that doesn't have eval data yet:

1. **Read the agent definition** to understand its expected output format:
   ```
   Read: .claude/agents/{agent_name}/{agent_name}.md
   ```
   Look for "Output Format" sections or JSON examples in the system prompt.

2. **Check existing schemas** in `gptase/evals/schemas.py` (`SCHEMA_MAP`):
   - `document_structure` -- for document-structure-analyzer
   - `enzyme_kinetics` -- for enzyme-kinetics-extractor
   - `vision_analysis` -- for vision-image-analyzer
   - `enzyme_summary` -- for enzyme-extraction-summary

   If no matching schema exists, guide the user to add one (see Phase 5).

3. **Prepare the eval directory**:
   ```bash
   mkdir -p .claude/agents/{agent_name}/evals
   ```

4. **Create `input.md`** with representative input text for the agent.

5. **Copy test images** (if the agent is multimodal):
   ```bash
   mkdir -p .claude/agents/{agent_name}/evals/images
   cp /path/to/test/images/* .claude/agents/{agent_name}/evals/images/
   ```

6. **Write `golden.yaml`** using this template:
   ```yaml
   schema: {schema_name}          # Key from SCHEMA_MAP
   input_file: input.md           # Relative to evals/ directory

   key_facts:
     # Count check: at least N items
     - field: "items"
       condition: length_gte
       value: 3

     # Substring check: a known value appears somewhere in a field
     - field: "result_field"
       condition: contains
       value: "expected substring"

     # Numeric check with tolerance
     - field: "metrics.accuracy"
       condition: gte
       value: 0.8

     # All values appear across a list field
     - field: "values[*].name"
       condition: contains_all
       values: ["Alpha", "Beta"]

     # Boolean field check -- booleans are compared as strings
     - field: "cases[case_id=foo].self_execute"
       condition: contains
       value: "False"          # Note: "True" / "False" as strings
   ```

   **Tip -- write good assertions**: Focus on facts that distinguish a correct
   output from a plausible-looking wrong one. A `length_gte: 1` assertion is
   weak; `contains_all` for specific entity names is strong.

7. **Run a live eval** to verify:
   ```bash
   conda run -n llm gptase eval -a {agent_name} --live --save-output
   ```

### Phase 4: Diagnose failure

When eval assertions are failing:

1. **Read the failing output** (cached in `evals/output/`):
   ```
   Glob: .claude/agents/{agent_name}/evals/output/*.json
   ```
   Read the most recent `output_*.json` -- this is the parsed agent output.

2. **Read the trace if needed**: The `trace_*.json` file captures the full LLM
   conversation steps, token counts, and timing. Check it when:
   - The output JSON looks correct but assertions still fail (field path issue)
   - The agent returned an error status
   - You need to see exactly what the model said before JSON parsing

3. **Read `golden.yaml`** to see the expected assertions.

4. **For each failing assertion**, compare:
   - The `field` path being checked
   - The `condition` and expected `value`
   - The actual value at that path in the output JSON

5. **Common failure patterns**:

   | Symptom | Likely Cause | Fix |
   |---|---|---|
   | `field resolved to None` | Field path wrong or output structure changed | Verify path against actual JSON structure |
   | `length X < Y` | Agent returned fewer items than expected | Lower threshold or improve agent prompt |
   | `expected ~X, got Y (diff Z%)` | Numerical extraction inaccurate | Adjust tolerance or improve agent prompt |
   | `missing values: [...]` | Agent didn't extract all items | Add more guidance to agent prompt |
   | Schema validation failed | Output structure doesn't match Pydantic model | Update schema or fix agent output format |
   | Boolean assertion failing | Used `value: False` instead of `value: "False"` | Booleans are string-compared; use quotes |

6. Present findings and suggest fixes to the user.

### Phase 5: Add new schema

When an agent's output doesn't match any existing schema:

1. **Analyze the agent's expected output format** from its definition file.

2. **Define a new Pydantic model** in `gptase/evals/schemas.py`:
   ```python
   class MyAgentOutput(BaseModel):
       """Expected output structure for my-agent."""
       results: Optional[List[MyResultEntry]] = None
       metadata: Optional[Dict[str, Any]] = None
   ```

   Use `Optional` fields -- the schema validates structure, not completeness.

3. **Register it in `SCHEMA_MAP`**:
   ```python
   SCHEMA_MAP: Dict[str, type] = {
       # ... existing entries ...
       "my_agent": MyAgentOutput,
   }
   ```

4. Reference the new schema name in `golden.yaml`.

---

## Assertion Reference

### Conditions

| Condition | Semantics | Example |
|---|---|---|
| `length_gte` | `len(field) >= value` | `{field: "items", condition: "length_gte", value: 5}` |
| `gte` | `float(field) >= value` | `{field: "score", condition: "gte", value: 0.8}` |
| `approx_eq` | `abs(a - e) / abs(e) <= tolerance` | `{field: "km", condition: "approx_eq", value: 0.21, tolerance: 0.15}` |
| `contains` | `value in str(field)` | `{field: "text", condition: "contains", value: "Des27"}` |
| `contains_all` | Every value found as substring | `{field: "names[*]", condition: "contains_all", values: ["A", "B"]}` |
| `contains_any` | At least one value found as substring | `{field: "text", condition: "contains_any", values: ["X", "Y"]}` |

**Note on booleans**: All conditions convert `actual` to string before comparing.
So `True` becomes `"True"` and `False` becomes `"False"`. Use `condition: contains,
value: "False"` (with quotes) when asserting on boolean fields.

**Note on `approx_eq` tolerance**: Default tolerance is 0.15 (15% relative error).
Specify `tolerance: 0.05` for tighter assertions, `tolerance: 0.30` for noisy
extractions.

### Field path DSL

| Syntax | Meaning | Example |
|---|---|---|
| `field` | Top-level key | `total_images` |
| `a.b.c` | Dotted traversal | `statistics.total_variants` |
| `list[*].field` | All items' field (returns list) | `reactions[*].enzyme_name` |
| `list[key=val].field` | Filter: first match, then traverse | `reactions[enzyme_name=Des27].kinetics.kcat/KM` |
| `list[0].field` | Integer index | `reactions[0].enzyme_name` |

Keys containing `/` (e.g., `kcat/KM`) are handled correctly.

---

## CLI Reference

```bash
# Evaluate with cached output (no API cost)
gptase eval -a vision-image-analyzer

# Evaluate with live LLM call
gptase eval -a vision-image-analyzer --live

# Live eval + save output for future cached runs
gptase eval -a vision-image-analyzer --live --save-output

# Save JSON report
gptase eval -a vision-image-analyzer --save report.json

# Use custom LLM config (different model, API key, or per-agent overrides)
gptase eval -a vision-image-analyzer --live --config config/llm_config.json

# Underscore and hyphen are interchangeable
gptase eval -a vision_image_analyzer
```

---

## Existing Eval Datasets

To find agents that already have eval data:
```
Glob: .claude/agents/*/evals/golden.yaml
```

Currently covered: `vision-image-analyzer`, `orchestrator`

---

## Examples

### Example 1: Evaluate an existing agent

```
User: "Evaluate the vision-image-analyzer"

1. Confirm golden.yaml exists at .claude/agents/vision-image-analyzer/evals/golden.yaml
2. Run: gptase eval -a vision-image-analyzer
3. Present results: schema status, facts score, any failures
```

### Example 2: Create eval for a new agent

```
User: "I want to add eval data for the enzyme-kinetics-extractor"

1. Read .claude/agents/enzyme-kinetics-extractor/enzyme-kinetics-extractor.md
2. Find "enzyme_kinetics" schema already in SCHEMA_MAP
3. Create evals/ directory, prepare input.md with sample paper text
4. Write golden.yaml with key fact assertions for Km, kcat values
5. Run live eval to verify
```

### Example 3: Diagnose failing eval

```
User: "The eval for vision-image-analyzer is failing"

1. Read .claude/agents/vision-image-analyzer/evals/output/output_*.json
2. Read golden.yaml to see expected assertions
3. If needed, read trace_*.json to inspect LLM conversation steps
4. For each failed fact, compare actual vs expected
5. Report: "field extracted_tables[*].csv_data missing 'Des27.7' -- agent
   extracted 12/13 variants, the bar chart for Des27.7 may be unclear"
```
