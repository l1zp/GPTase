# Eval API

> [Home](../README.md) → [API](.) → Eval

**Source files:** `gptase/evals/__init__.py`, `gptase/evals/assertions.py`, `gptase/evals/runner.py`, `gptase/evals/report.py`, `gptase/evals/schemas.py`

---

## Overview

The eval framework assesses agent output quality across three tiers:

| Tier | What it checks | Implementation |
|---|---|---|
| **Schema validation** | Is the JSON structure correct? | Pydantic models (`schemas.py`) |
| **Key fact assertions** | Are important values present and correct? | `golden.yaml` + `assertions.py` |
| **Completeness metrics** | How many expected entities were found? | `length_gte` / `contains_all` conditions |

No LLM-as-judge — avoids extra API cost and non-determinism.

---

## CLI

```bash
# List available eval papers
gptase eval --list

# Evaluate all agents using cached outputs (no API cost)
gptase eval -p listov2025

# Evaluate a single agent
gptase eval -p listov2025 -a enzyme_kinetics_extractor

# Evaluate with live LLM run (hits API)
gptase eval -p listov2025 --live

# Use a specific cached output directory
gptase eval -p listov2025 --cache-dir data/output/listov2025/enzyme_extraction_pipeline_20260319_232337

# Save JSON report
gptase eval -p listov2025 --save report.json
```

**Example output:**

```
Agent Evaluation: listov2025
============================================================
Agent                          Schema   Facts    Score
------------------------------------------------------------
document_structure_analyzer    [OK]     3/3      1.00
enzyme_kinetics_extractor      [OK]     5/5      1.00
vision_image_analyzer          [OK]     1/1      1.00
enzyme_extraction_summary      [OK]     2/2      1.00
------------------------------------------------------------
Overall: 11/11 key facts passed (1.00)
```

---

## Python API

### `run_eval()`

```python
from gptase.evals import run_eval

results = await run_eval(
    paper_id="listov2025",     # required: subdirectory name under data/evals/
    agent_name=None,           # optional: evaluate only this agent
    live=False,                # if True, run agents against the LLM API
    cache_dir=None,            # custom path to a cached output directory
)
# returns List[EvalResult]
```

### `EvalRunner`

```python
from gptase.evals import EvalRunner

runner = EvalRunner(
    paper_id="listov2025",
    cache_dir=None,   # auto-discovers latest directory under data/output/{paper_id}/
)

# Evaluate all agents
results = await runner.eval_all(live=False)

# Evaluate a single agent
result = await runner.eval_agent("enzyme_kinetics_extractor", live=False)
```

### `EvalResult`

```python
@dataclass
class EvalResult:
    agent_name: str
    paper_id: str
    schema_valid: bool        # True if Pydantic schema validation passed
    schema_error: str         # Error description on schema failure
    total_facts: int          # Total assertions defined in golden.yaml
    passed_facts: int         # Number of passing assertions
    failed_facts: List[str]   # Human-readable failure descriptions

    @property
    def score(self) -> float: ...   # passed_facts / total_facts
```

---

## Data Layout

```
data/evals/
  {paper_id}/
    golden.yaml          # Human-curated expected values

data/output/
  {paper_id}/
    {plan_id}_{timestamp}/        # Pipeline run output (cache source)
      document_structure_analyzer/
        1_parsed.json
      enzyme_kinetics_extractor/
        2a_parsed.json
      vision_image_analyzer/
        2b_parsed.json
      enzyme_extraction_summary/
        3_parsed.json
```

---

## `golden.yaml` Format

```yaml
paper_id: listov2025
input_file: data/input/listov2025/listov2025.md       # used for live runs
input_images_dir: data/input/listov2025/images        # used for live runs

agents:
  enzyme_kinetics_extractor:
    schema: enzyme_kinetics          # key in SCHEMA_MAP
    key_facts:
      - { field: "reactions", condition: "length_gte", value: 25 }
      - { field: "reactions[*].enzyme_name", condition: "contains_all",
          values: ["Des27", "Des27.7"] }
      - { field: "reactions[enzyme_name=Des27].kinetics.kcat/KM",
          condition: "approx_eq", value: 131, tolerance: 0.15 }
```

### Supported Conditions

| Condition | Semantics |
|---|---|
| `length_gte` | `len(field) >= value` |
| `gte` | `field >= value` |
| `approx_eq` | `abs(actual - expected) / expected <= tolerance` (default 0.15) |
| `contains` | `value in str(field)` |
| `contains_all` | all values found in the list |
| `contains_any` | at least one value found in the list |

### Field Path DSL

```
"statistics.total_variants"                  # dotted traversal
"reactions[*].enzyme_name"                   # wildcard: list of all .enzyme_name values
"reactions[enzyme_name=Des27].kinetics.kcat" # filter: first match, then field access
"reactions[0].enzyme_name"                   # integer index
```

Keys containing `/` (e.g. `kcat/KM`) are handled correctly.

---

## Supported Schemas

| Schema name | Agent | Pydantic model |
|---|---|---|
| `document_structure` | `document_structure_analyzer` | `DocumentStructureOutput` |
| `enzyme_kinetics` | `enzyme_kinetics_extractor` | `EnzymeKineticsOutput` |
| `vision_analysis` | `vision_image_analyzer` | `VisionAnalysisOutput` |
| `enzyme_summary` | `enzyme_extraction_summary` | `EnzymeSummaryOutput` |

---

## Adding a New Paper

One file, no code changes:

```bash
# 1. Create the golden file
mkdir -p data/evals/<paper_id>
vim data/evals/<paper_id>/golden.yaml

# 2. Place input files (needed for live runs only)
mkdir -p data/input/<paper_id>/images

# 3. Verify
gptase eval --list         # should show the new paper
gptase eval -p <paper_id>  # run against cache
```

`gptase eval --list` auto-discovers all subdirectories under `data/evals/` that contain a `golden.yaml`.
