# Enzyme Extraction Pipeline

## Overview

`enzyme_extraction_pipeline` extracts enzyme kinetics data from a paper in three stages:

1. `document-structure-analyzer`
2. Parallel extraction:
   - `enzyme-kinetics-extractor` (`2a`, replicated 3x)
   - `vision-image-analyzer` (`2b`, replicated 3x)
3. `enzyme-extraction-summary`

The pipeline is designed for markdown-converted papers such as `listov2025.md`.

## Workflow

### Step 1: Document Structure Analysis

Agent: `document-structure-analyzer`

Input:
- `document_path`

Output:
- `sections`
- `tables`
- `images`

Purpose:
- Identify which sections, tables, and figures are relevant to enzyme kinetics extraction.
- Provide structured guidance for downstream text and vision agents.

### Step 2a: Text-Based Kinetics Extraction

Agent: `enzyme-kinetics-extractor`
Replicates: `3`

Input:
- `document_path`
- `relevant_sections` from `step1.sections`
- `relevant_tables` from `step1.tables`

Purpose:
- Extract enzyme variants and kinetic measurements from text and markdown tables.
- Use `step1` metadata to narrow search scope before reading local regions of the file.

Current optimization:
- The extractor no longer receives the full paper text as a giant prompt.
- It now receives `document_path`, `relevant_sections`, and `relevant_tables`.
- It performs targeted `Grep`/`Read` calls against the source markdown using the structure hints from step 1.
- This significantly reduces the initial prompt size and avoids loading the entire paper into context up front.
- In validation runs, the initial `2a` user message dropped from roughly `102k` characters to roughly `4.4k` characters.

Expected output:
- `reactions`

### Step 2b: Vision-Based Figure Extraction

Agent: `vision-image-analyzer`
Replicates: `3`

Input:
- `images` from `step1.images`
- `workspace_dir`

Purpose:
- Analyze figure images directly with multimodal input.
- Extract chart/table content and produce CSV-compatible outputs for downstream aggregation.

Expected output:
- `analysis_results`
- `extracted_tables`

### Step 3: Summary Generation

Agent: `enzyme-extraction-summary`

Input:
- `text_extraction_data` from `step2a.reactions`
- `vision_extraction_data` from `step2b.extracted_tables`

Purpose:
- Summarize variant coverage, parameter coverage, and top performers.
- Generate a final structured report from the combined extraction outputs.

Expected output:
- `summary_report`
- `statistics`
- `top_performers`
- `data_quality_flags`

## Important Runtime Notes

### Checkpointing

The planner now checkpoints progress after each completed task instead of waiting for an entire parallel batch to finish. This makes live progress reporting more accurate for long-running replicated steps.

### Tracking

Each non-Claude LLM agent call is now tracked at the conversation level in `data/conversations.db`, including:
- `agent_id`
- `step_id`
- message sizes
- per-call latency

This is important for debugging slow or unstable runs and for identifying which step is holding up a plan execution.

### Output Layout

Task outputs are written into per-task subdirectories:

```text
data/output/<document_name>/<run_id>/
  document-structure-analyzer/1/
  enzyme-kinetics-extractor/2a_r1/
  enzyme-kinetics-extractor/2a_r2/
  enzyme-kinetics-extractor/2a_r3/
  vision-image-analyzer/2b_r1/
  vision-image-analyzer/2b_r2/
  vision-image-analyzer/2b_r3/
  enzyme-extraction-summary/3/
```

This replaces the older flat per-agent layout and keeps each task's artifacts grouped together.

## Typical Files Produced

Examples:

- `document-structure-analyzer/1/1_result.json`
- `document-structure-analyzer/1/1_sections.csv`
- `enzyme-kinetics-extractor/2a_r1/2a_r1_reactions.csv`
- `vision-image-analyzer/2b_r1/2b_r1_analysis_results.csv`
- `vision-image-analyzer/2b_r1/table_4.csv`
- `enzyme-extraction-summary/3/3_parsed.json`

## Example Run

Run the pipeline from the repo root:

```bash
conda run -n llm python -m gptase.main plan \
  -p enzyme_extraction_pipeline \
  -i /Users/ryanxu/CodeBase/GPTase/data/input/listov2025/listov2025.md
```

Typical output root:

```text
data/output/listov2025/enzyme_extraction_pipeline_<timestamp>/
```

Example completed layout:

```text
data/output/listov2025/enzyme_extraction_pipeline_<timestamp>/
  document-structure-analyzer/1/1_result.json
  enzyme-kinetics-extractor/2a_r1/2a_r1_result.json
  enzyme-kinetics-extractor/2a_r2/2a_r2_result.json
  enzyme-kinetics-extractor/2a_r3/2a_r3_result.json
  vision-image-analyzer/2b_r1/2b_r1_result.json
  vision-image-analyzer/2b_r2/2b_r2_result.json
  vision-image-analyzer/2b_r3/2b_r3_result.json
  enzyme-extraction-summary/3/3_result.json
```

Useful runtime checks:

```bash
sqlite3 data/conversations.db "select session_id,status,completed_steps,total_steps,updated_at from plan_checkpoints order by updated_at desc limit 5;"
```

```bash
sqlite3 data/conversations.db "select id,agent_id,status,timestamp from conversations order by timestamp desc limit 20;"
```

## Current Bottleneck

After the latest optimization, `2a` is no longer dominated by a massive initial prompt. The heaviest remaining payload is the vision path (`2b`), which still carries large multimodal image inputs.

There is also a secondary cost in `step1`: `document-structure-analyzer` may still read a large portion of the markdown file during its internal tool loop. However, this is no longer the primary blocker once the pipeline moves into parallel extraction.

## Troubleshooting

### Progress appears stuck at `0/8`

Check whether `document-structure-analyzer` is still running multiple internal tool-loop turns. This can happen before the first checkpoint increments to `1/8`.

### Step 2a is slow

Inspect recent `enzyme-kinetics-extractor` conversations in `data/conversations.db`.
The optimized path should show a much smaller initial user message and targeted `Grep`/`Read` usage instead of a full-document prompt.

### Step 2b is slow

This is expected more often than `2a`, because the vision agent still receives large multimodal image payloads.

### Summary finished at the model layer but files are missing

Check `conversations` and `responses` for `agent_id='enzyme-extraction-summary'`. If the response exists but `enzyme-extraction-summary/3/` is empty, the issue is in result persistence rather than model generation.
