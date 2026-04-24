---
name: enzyme-variant-normalizer
description: Reconciles raw enzyme extraction replicas into canonical variant records with normalized kinetics and sequence augmentation hints.
tools:
result_validation: |
  Accept if the result reconciles extraction replicas into deduplicated variant records
  with consistent naming, merged kinetics, and sequence augmentation where PDB codes
  are available. Also accept an empty normalization when no input data was provided.
  Reject if the output drops valid variant data, introduces spurious variants not
  present in any replica, or fails to attempt reconciliation.
---

This agent is executed deterministically by the Python dispatcher.

Its implementation lives in `gptase/agents/enzyme_variant_normalizer.py`.
The markdown definition exists so the orchestrator can discover the agent and
validate plan references consistently with other workflow steps.
