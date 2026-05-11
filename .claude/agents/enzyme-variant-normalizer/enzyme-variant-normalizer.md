---
name: enzyme-variant-normalizer
description: Reconciles raw enzyme extraction replicas into canonical variant records with normalized kinetics and sequence augmentation hints.
tools: []
result_validation: |
  Accept if the result reconciles extraction replicas into deduplicated variant records
  with consistent naming, merged kinetics, and sequence augmentation where PDB codes
  are available. Also accept an empty normalization when no input data was provided.
  Reject if the output drops valid variant data, introduces spurious variants not
  present in any replica, or fails to attempt reconciliation.
---

This agent is hook-driven: the `pre_run` hook in the sibling `hooks.py`
intercepts the run, parses the task inputs out of the prompt envelope,
expands any upstream-artifact references, and calls
`normalize_variant_payload` directly. The LLM is never invoked, so this
prompt body is informational only — it documents the contract for
human readers and downstream result validators.

## Input shape

The task description carries a JSON object whose `inputs` field has
these keys:

- `text_extraction_data`: list of replica payloads from
  `enzyme-kinetics-extractor`. Each replica is an object with a
  `reactions` list.
- `vision_extraction_data`: list of replica payloads from
  `vision-image-analyzer` (typically the `extracted_tables` field from
  each replica).
- `si_extraction_data` (optional): a single payload from a
  supplementary-information extraction run, or `null`.
- `document_path`: absolute path to the original paper markdown.
- `si_document_path` (optional): absolute path to the supplementary-
  information markdown, when one was extracted.

## Behavior

1. The hook parses the JSON object out of the prompt envelope built by
   `Agent._build_user_prompt`.
2. String values that point at upstream worker artifacts (JSON files
   written by `DelegateTaskTool._save_artifact`) are loaded and their
   wrapped payloads substituted in place. Strings that aren't artifacts
   pass through verbatim.
3. `si_extraction_data` (when present) is folded into
   `text_extraction_data` so the normalizer sees a single replica list.
4. `normalize_variant_payload` returns the canonical variant records;
   the hook serializes them and returns the standard `Agent.run()`
   result shape.

## Constraints (enforced inside the hook / normalizer)

- Variants not present in any replica are not invented.
- Variants present in any replica are not dropped.
- The hook short-circuits exactly once per task; the LLM never runs.
