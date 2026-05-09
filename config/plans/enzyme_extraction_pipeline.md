Goal: Standard Enzyme Extraction Pipeline

Sequential workflow with parallel extraction:
Structure Scan -> (LLM + Vision Extraction) -> Summary Report

Document: {{document_path}}
Supplementary information: {{si_document_path}}
Workspace: {{workspace_dir}}

Execute these steps IN ORDER. Each step must complete before issuing
the next step's DelegateTask call(s). Use the DelegateTask tool to
invoke each agent.

Within a step, multiple replicas are issued as parallel DelegateTask
calls in the SAME assistant message — do NOT serialize them.

Each DelegateTask call returns a compact reference object
    {"agent_id": ..., "status": ..., "output_path": "<file>",
     "content_chars": N, "content_preview": "<first 1500 chars>"}
The full worker output is written to that output_path file. When a
downstream step needs upstream results, pass the upstream
output_path string(s) directly — DO NOT re-emit the full content.
Deterministic agents (see step rendering) auto-load these paths.

────────────────────────────────────────────────────────────

Step 1 — Perform physical scan of the document to locate tables and images.
  Issue ONE DelegateTask call:
    DelegateTask(
      agent_id="document-structure-analyzer",
      task_description="""
        Perform physical scan of the document to locate tables and images.
        Inputs:
          - document_path: {{document_path}}
      """
    )


Step 2a — Extract structured kinetic parameters from document text.
  Issue EXACTLY 3 parallel DelegateTask calls in ONE assistant message:
    DelegateTask(
      agent_id="enzyme-kinetics-extractor",
      task_description="""
        Extract structured kinetic parameters from document text.
        Inputs:
          - document_path: {{document_path}}
          - relevant_sections: {{step1.sections}}
          - relevant_tables: {{step1.tables}}
      """
    )
  Repeat the above call 3 times in the SAME assistant message.

Step 2b — Analyze figures to extract tabular data using vision model.
  Issue EXACTLY 3 parallel DelegateTask calls in ONE assistant message:
  This agent has AUTO_RESOLVE_ARTIFACTS — pass arguments via task_inputs.
  For upstream worker outputs, use the upstream output_path STRING
  (e.g. analyzer's artifact path); DelegateTask will mine the
  payload for `images[].image_path` and embed those images as
  multimodal content. Plain strings are pass-through.
    DelegateTask(
      agent_id="vision-image-analyzer",
      task_description="Analyze figures to extract tabular data using vision model.",
      task_inputs={
        "images": <{{step1.images}}>,
        "workspace_dir": <{{document_path}}>,
      }
    )
  Repeat the above call 3 times in the SAME assistant message.


Step 3s — Extract kinetic data from supplementary information document.
  IF the condition `{{si_document_path}} is empty` evaluates true, SKIP this step.
  Issue ONE DelegateTask call:
    DelegateTask(
      agent_id="enzyme-kinetics-extractor",
      task_description="""
        Extract kinetic data from supplementary information document.
        Inputs:
          - document_path: {{si_document_path}}
          - relevant_sections: {{step1.sections}}
          - relevant_tables: {{step1.tables}}
      """
    )


Step 4 — Reconcile replicated extraction rows into normalized variant records,
merging SI data when available. Pass full replica payloads so both
`reactions` and `protein_sequences` reach the normalizer (sequences
may appear in the main paper or SI).
  Issue ONE DelegateTask call:
  This agent is DETERMINISTIC — DelegateTask will call its tool
  directly. Pass arguments via task_inputs.
  For fields whose data lives in upstream worker outputs,
  use the upstream output_path STRING (or list of strings)
  — DelegateTask reads and parses each artifact for you.
  Plain string fields (e.g. document_path) are pass-through.
    DelegateTask(
      agent_id="enzyme-variant-normalizer",
      task_description="Reconcile replicated extraction rows into normalized variant records,
merging SI data when available. Pass full replica payloads so both
`reactions` and `protein_sequences` reach the normalizer (sequences
may appear in the main paper or SI).",
      task_inputs={
        "text_extraction_data": <{{step2a}}>,
        "vision_extraction_data": <{{step2b.extracted_tables}}>,
        "si_extraction_data": <{{step3s}}>,
        "document_path": <{{document_path}}>,
      }
    )


Step 5 — Generate statistical analysis and top-performer ranking from merged data.
  Issue ONE DelegateTask call:
    DelegateTask(
      agent_id="enzyme-extraction-summary",
      task_description="""
        Generate statistical analysis and top-performer ranking from merged data.
        Inputs:
          - normalized_variant_data: {{step4.normalized_variants}}
          - text_extraction_data: {{step2a.reactions}}
          - vision_extraction_data: {{step2b.extracted_tables}}
      """
    )

────────────────────────────────────────────────────────────

After the final step completes, return its output as your final answer.
