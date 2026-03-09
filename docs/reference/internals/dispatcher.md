# Dispatcher Internals

> [Home](../README.md) → [Internals](./) → Dispatcher

**File:** `gptase/sop/dispatcher.py`

---

## TaskDispatcher

`TaskDispatcher` bridges the SOP orchestrator and individual agents. It is instantiated once per `SOPOrchestratorAgent` and persists for the lifetime of the execution.

```python
dispatcher = TaskDispatcher(
    memory_manager=memory_manager,
    model_manager=model_manager,
)
```

### Agent Caching

Agents are created on demand and cached in `self._agents: Dict[str, Agent]`:

```python
async def _get_agent(agent_id: str) -> Agent:
    if agent_id in self._agents:
        return self._agents[agent_id]   # reuse
    agent = Agent.from_markdown(agent_id, model_manager=...)
    self._agents[agent_id] = agent
    return agent
```

This means the same agent instance handles multiple steps within one SOP execution. The agent's `workspace_dir` is overwritten on each `dispatch()` call to point at the current document's directory. Call `dispatcher.clear_agents()` to reset the cache.

---

## `dispatch()` Step-by-Step

```
dispatch(step, context)
  │
  ├─ 1. _get_agent(step.agent)
  │       └─ Agent.from_markdown(agent_id)  (or from cache)
  │
  ├─ 2. Set agent.workspace_dir = context.document_path or context.workspace_dir
  │
  ├─ 3. Provision agent output directory:
  │       agent_workspace = workspace_dir / step.agent
  │       agent_workspace.mkdir(parents=True, exist_ok=True)
  │
  ├─ 4. _resolve_inputs(step.inputs, context)
  │       → resolved dict with template vars expanded
  │
  ├─ 5. _normalize_image_fields(resolved_inputs)
  │       → extract string paths from image metadata dicts
  │
  ├─ 6. AgentTask(action=step.action, step_id=step.step_id, **resolved_inputs)
  │
  ├─ 7. agent.process_task(task) → {"status":..., "data":{...}}
  │
  ├─ 8. TaskResult(agent_id, step_id, status, data, execution_time)
  │
  └─ 9. If success + workspace:
          ├─ write workspace/agent_name/step_id_result.json
          └─ _post_process_result(step, task_result, agent_workspace)
```

---

## Template Variable Resolution

`_resolve_inputs()` iterates over `step.inputs` and calls `_resolve_value()` for each value. Only string values matching `{{...}}` are resolved; all other types are passed through unchanged.

### Resolution Order in `_resolve_value()`

| Pattern | Resolves to |
|---|---|
| `{{input_text}}` | `context.input_data["text"]` |
| `{{document_path}}` | `context.document_path` or `context.input_data["document_path"]` |
| `{{input_data}}` | Full `context.input_data` dict |
| `{{stepN}}` | `_resolve_step_reference("stepN", context)` |
| `{{stepN.field.nested}}` | Nested field from step N's result data |
| `{{var_name}}` | `context.variables["var_name"]` |
| `{{var_name}}` (fallback) | `context.input_data["var_name"]` |
| unknown | Return as-is with a warning |

Non-string values (int, list, dict) are returned unchanged without template processing.

### Step Reference Resolution (`_resolve_step_reference`)

```
ref = "step2a.analysis.images"
  │
  ├─ split(".", 1) → ["step2a", "analysis.images"]
  ├─ step_id = "2a"    (strip "step" prefix)
  ├─ step_data = context.get_step_data("2a")  → TaskResult.data dict
  │
  └─ _get_nested_field(step_data, "analysis.images")
```

### Nested Field Resolution (`_get_nested_field`)

The nested field walker has a special fallback for JSON-wrapped LLM output:

```
data = {"content": "```json\n{\"analysis\":{\"images\":[...]}}\n```"}
path = "analysis.images"

Walk path = ["analysis", "images"]:
  ├─ step "analysis": not in data
  ├─ but "content" key exists → _try_parse_content_json(data["content"])
  │       → {"analysis": {"images": [...]}}
  ├─ "analysis" in parsed? yes
  ├─ current = parsed["analysis"] = {"images": [...]}
  └─ step "images": in current → return [...]
```

This means agents can output raw JSON or markdown-fenced JSON and downstream steps can reference nested fields without any manual unwrapping.

---

## `_try_parse_content_json()` — 4-Strategy Parser

The method tries four strategies in order:

```python
# Strategy 1: markdown ```json block
if "```json" in content:
    json_part = content.split("```json")[1].split("```")[0]
    return json.loads(json_part)
    # On failure: try trailing-comma repair with regex

# Strategy 2: generic ``` block
elif content.startswith("```"):
    json_part = content.split("```")[1]
    # Skip language identifier line if present
    return json.loads(json_part)

# Strategy 3: raw JSON (starts with { or [)
if content.startswith("{") or content.startswith("["):
    return json.loads(content)

# Strategy 4: regex scan for first {...} object
json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
return json.loads(json_match.group())
```

Strategy 1 also includes a trailing-comma repair step (`re.sub(r',\s*([}\]])', r'\1', ...)`) to handle common LLM JSON formatting errors.

---

## Image Field Normalization (`_normalize_image_fields`)

When images come from a previous step's result (e.g., `{{step1.images}}`), they may be structured as metadata dicts instead of plain paths:

```python
# What arrives from a document-structure-analyzer step:
images = [
    {"figure_id": "Figure 3a", "image_path": "/doc/images/figure_3a.png", ...},
    {"figure_id": "Figure 4",  "image_path": None, ...},
]

# What AgentTask needs:
images = ["/doc/images/figure_3a.png"]
```

The normalization logic:

```
for field in ["images", "image_paths"]:
  if value is list of dicts:
    for each item:
      try item["image_path"]  → use if non-empty
      else: extract figure_id via regex "Figure\s*(\d+[a-z]?)"
            try patterns: images/figure_N.png, images/fig_N.png, ...
            if file exists in workspace → use that path
    if no paths found → set field to []  (with warning)
```

The `workspace` for path resolution comes from `inputs["workspace_dir"]` or `inputs["document_path"]`.

---

## `_post_process_result()` — Automatic File Extraction

After a successful step, the dispatcher attempts to extract structured files from the LLM's text output:

```
_post_process_result(step, task_result, agent_workspace)
  │
  ├─ Get task_result.data["content"]  (string)
  ├─ Parse as JSON (same logic as _try_parse_content_json)
  │
  ├─ Write: workspace/agent_name/step_id_parsed.json
  │
  ├─ "extracted_tables" key?
  │    └─ for each table: write table_{image_number}.csv from csv_data field
  │
  └─ General keys: "reactions", "tables", "images", "sections", "analysis_results"
       └─ each list-of-dicts → write step_id_{key}.csv
```

CSV writing collects all unique keys across all dict entries as header columns. Nested dict/list values are JSON-stringified in each cell.

---

## Parallel Dispatch

```python
async def dispatch_parallel(steps, context, max_concurrent=10):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def dispatch_with_semaphore(step):
        async with semaphore:
            return await self.dispatch(step, context)

    results = await asyncio.gather(
        *[dispatch_with_semaphore(s) for s in steps],
        return_exceptions=True,
    )
    # Exceptions → TaskResult(status="failed", error=str(exc))
```

The `max_concurrent` value comes from `SOPDefinition.max_parallel` (default 10). All steps in a parallel group share the same `context`, meaning they see the same step results from prior sequential steps but cannot see each other's results (they run concurrently).

---

*Related: [Execution Flow →](./execution-flow.md) | [SOP API →](../api/sop.md)*
