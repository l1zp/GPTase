---
name: enzyme-variant-normalizer
description: Reconciles raw enzyme extraction replicas into canonical variant records with normalized kinetics and sequence augmentation hints.
tools:
---

This agent is executed deterministically by the Python dispatcher.

Its implementation lives in `gptase/agents/enzyme_variant_normalizer.py`.
The markdown definition exists so the orchestrator can discover the agent and
validate plan references consistently with other workflow steps.
