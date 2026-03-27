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
- It now performs targeted `Grep`/`Read` calls against the source markdown using the relevant section and table hints from step 1.
- This significantly reduces initial prompt size and avoids loading the entire paper into context up front.

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

Each agent call is now tracked at the conversation level in `data/conversations.db`, including:
- `agent_id`
- `step_id`
- message sizes
- per-call latency

This is important for debugging slow or unstable runs.

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

## Current Bottleneck

After the latest optimization, the main text extractor (`2a`) is no longer dominated by a massive initial prompt. The remaining heavy payload in this pipeline is the vision path (`2b`), which still carries large multimodal inputs for embedded figures.
