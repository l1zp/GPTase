# GPTase Architecture Refactor Audit

**Date**: 2026-05-07
**Branch**: `data/pipeline`
**Scope**: Framework-level complexity audit, performed before any refactor work begins.
**Method**: Read-only Explore agent pass over Tier 1 (orchestrator/planner/dispatcher/runtime), Tier 2 (type files), Tier 3 (models/tools/memory).

The goal of this audit is to give a refactor proposal something concrete to point at. Every claim below carries a `file:line` reference so future work can verify whether a hotspot is still present.

---

## 1. Architecture map

CLAUDE.md advertises a clean 3-mode dispatch (Agent / Coordinator / Plan Manager). The code shows:

- **11 type classes** fragmented across 3 files (`types.py`, `runtime_types.py`, `execution_types.py`).
- **4 heavyweight orchestration classes**:
  - `orchestrator.py` — 1179 lines
  - `plan_dispatcher.py` — 1152 lines
  - `planner.py` — 870 lines
  - `enzyme_variant_normalizer` — 940 lines, imported only by `plan_dispatcher`
- Domain-specific enzyme normalization is tightly coupled into the **generic** task dispatcher.
- Significant overlapping responsibility between `orchestrator` and `planner` (session/checkpoint/retry logic mirrored in both).

Net: the current separation is conceptual, not enforced. Callers (e.g. `orchestrator.py` lines 20–25) cross all three type-file boundaries, so the boundaries are invisible at the consumer level.

---

## 2. Top 5 complexity hotspots

### Hotspot 1 — `gptase/core/orchestrator.py` (1179 lines, 24 methods)
- **Smell**: god-object | overlapping-responsibility
- **Evidence**:
  - Three dispatch paths (`_execute_agent`, `_execute_coordinator`, `_execute_plan`) coexist with session persistence (DirectSession / SessionMessage / SessionTrace creation + load) and plan-resume logic.
  - Lines 194–435 hold the coordinator event loop, plan handoff detection, and worker delegation — partially duplicating `TaskDispatcher`'s dispatch pattern.
- **Refactor lever**: extract session persistence + resumption into a standalone `SessionManager`; move the coordinator loop into `runtime.py` where plan-handoff decision-making already lives.

### Hotspot 2 — `gptase/agents/plan_dispatcher.py` (1152 lines, 26 methods)
- **Smell**: overlapping-responsibility | domain leak
- **Evidence**:
  - Imports three enzyme-specific functions (lines 21–22).
  - `_dispatch_enzyme_variant_normalizer` (lines 610+) hardcodes domain logic into the generic dispatcher; no other dispatcher path calls the 940-line `enzyme_variant_normalizer` module.
- **Refactor lever**: turn enzyme normalization into a post-processing hook (agent-agnostic callback). Removes ~90 lines of conditional branching and the cross-domain import.

### Hotspot 3 — `gptase/agents/planner.py` (870 lines, 11 public methods)
- **Smell**: overlapping-responsibility
- **Evidence**:
  - Checkpoint restore/create at `planner.py:184-214` mirrors `orchestrator.py:320-335`.
  - `FailureHandler` is initialized at `planner.py:116` but only invoked at `planner.py:389`.
  - Retry loops at `planner.py:338-431` duplicate orchestrator's task execution logic.
- **Refactor lever**: move checkpoint management into `ExecutionContext`; consolidate retry/failure decisions into a `TaskDispatcher` retry wrapper.

### Hotspot 4 — Type system fragmentation
- **Smell**: type-fragmentation
- **Evidence**: three files with no mutual imports, but external callers cross all three:
  - `types.py` — Task, Plan, SessionMessage, SessionTrace, DirectSession (session-specific).
  - `runtime_types.py` — InteractiveRuntimeResult, InteractiveTurn, CoordinatorRuntimeSummary (runtime telemetry).
  - `execution_types.py` — TaskExecutionResult, ExecutionContext, PlanCheckpoint (plan execution state).
  - `orchestrator.py:20-25` and `planner.py:22-25` both import across all three boundaries.
- **Refactor lever**: introduce a unified `SessionState` umbrella that owns (messages, traces, execution_context). Merging `runtime_types` and the session classes from `types` into this hierarchy clarifies the boundary at the call site.

### Hotspot 5 — `gptase/agents/plan_failure_handler.py` (312 lines)
- **Smell**: speculative-abstraction
- **Evidence**:
  - LLM-driven decision logic lives at lines 79–184; heuristic fallback at lines 190–300.
  - Instantiated **once** (`planner.py:116`), called from **one** failure path (`planner.py:389`).
  - Most production failures resolve via attempt limits before reaching the LLM branch — meaning the LLM path is rarely exercised in practice.
  - No test coverage visible; no callers from other agents or workflows.
- **Refactor lever**: inline the heuristic decision into `planner._execute_single_task()` as a small conditional. Retire the LLM branch unless it's a stated user-facing feature.

---

## 3. Type system verdict

**Not justified.**

The three files name three real domains (session metadata, runtime telemetry, plan execution state), but no consumer thinks in those terms. `orchestrator`, `web/server`, and `planner` all need to import from all three to do useful work — which is the textbook signal of a leaky split.

Recommended: merge `runtime_types` + session-related classes from `types` into a `SessionState` hierarchy, with `execution_types` exposed as a sub-object. This reduces import sprawl and makes the "I just want the state of this session" use case a one-import operation.

---

## 4. Speculative abstractions — verified status (updated 2026-05-07)

The original Explore-agent audit flagged five symbols as speculative. After a grep-based verification pass, only one was confirmed dead. The remaining four split between "false positive" and "partially dead".

| Symbol | Original audit claim | Verified status | Action |
|---|---|---|---|
| `GoalEvaluation` (`types.py:352-358`) | Used only once in orchestrator | **False positive** — used 5 places in `orchestrator.py` + 4 places in `tests/integration/test_orchestrator.py`; core return type of `_evaluate_goal_completion`. | Keep. |
| `DirectSession.metadata` (`types.py:371`) | Never written | **Partially dead** — never written by any orchestrator path, but `DirectSession(**raw)` (`orchestrator.py:1039,1114`) accepts it from external JSON; deleting would change the serialization schema. | Defer — needs frontend/storage check. |
| `PlanCheckpoint.plan_hash` (`execution_types.py:231`) | Never read or written | **Confirmed dead** — only the field definition existed; no callers, no construction kwarg. | **Removed (2026-05-07)**. |
| `FailureHandler.max_retries` (`plan_failure_handler.py:77`) | Shadowed by `Task.retry_count` | **Partially dead** — the constructor parameter is never passed (`planner.py:116` uses the default); but `self.max_retries` is genuinely used 5 places inside `FailureHandler`. | **Resolved by Slice 4 (2026-05-07)** — kept as constructor parameter with `DEFAULT_MAX_RETRIES`; `planner.py:116` no longer attempts to pass `model`. |
| `InteractiveSessionState` (`runtime_types.py:126-136`) | Never persisted or shared | **False positive** — used 6 places in `runtime.py` as the active runtime state type. | Keep. |

**Lesson for future audits**: Explore-agent reports flag candidates via call-count signals; those signals are hints, not facts. Always grep before acting — call count alone does not imply death.

Aggregate dead surface area genuinely removed by this audit: ~1 line (the one field). Aggregate flagged for later removal alongside Slice 4: ~310 lines (`FailureHandler` if retired).

---

## 5. Suggested refactor slices (ordered by ROI)

Each slice is sized as a self-contained PR.

### Slice 1 — Merge session type system  (Risk: Low)
- **Scope**: consolidate `SessionMessage`, `SessionTrace`, `DirectSession`, `InteractiveSessionState` into a unified `SessionState` class tree.
- **Removes**: redundant imports across `orchestrator`, `planner`, `web/server`; simplifies `runtime.py` state management.
- **Why low risk**: callers are confined to those four files; test coverage is light, so blast radius is small.

### Slice 2 — Extract `SessionManager` from orchestrator  (Risk: Medium)
- **Scope**: move DirectSession CRUD, load/save, and resumption logic from `orchestrator.py:920-1050` into a new `SessionManager` class.
- **Removes**: ~130 lines from `orchestrator`; clarifies dispatch-vs-persistence seam.
- **Why medium risk**: `SessionManager` needs read access to the agent registry to resume sessions cleanly; the boundary is subtle.

### Slice 3 — Extract enzyme normalization post-processor  (Risk: Medium)
- **Scope**: move `_dispatch_enzyme_variant_normalizer()` and enzyme imports out of `plan_dispatcher.py` into an `EnzymeNormalizationAdapter` that wraps `TaskDispatcher`.
- **Removes**: ~90 lines of domain logic from the generic dispatcher; the 940-line normalizer module becomes plugin-only.
- **Why medium risk**: the enzyme step transforms intermediate task results — the adapter must sit in the right place in the dispatch pipeline.
- **Context**: this complexity entered on the `data/pipeline` branch. Reviewing now while the change is still recent is cheap.

### Slice 4 — Inline or retire `FailureHandler`  (Risk: Low) — **DONE 2026-05-07**
- **Scope (chosen)**: kept the `FailureHandler` class skeleton (preserves `pm.failure_handler.decide` interface that `tests/test_planner.py:770` mocks), removed the speculative LLM branch (`_llm_decide`, `DECISION_PROMPT`), removed `model` / `model_config` constructor fields, removed the unused `should_skip_on_failure` method, and updated `planner.py:116` to construct `FailureHandler()` without the `model` arg.
- **Removed**: 441 lines net (vs 311 estimated). Breakdown: `plan_failure_handler.py` 312 → 144 (−168); `tests/test_plan_failure_handler.py` 408 → 144 (−264, dropped 19 LLM/init/skip tests, kept 14 heuristic tests); `planner.py` 1-line constructor change.
- **Why we kept the class instead of fully retiring**: `_classify_error` carries real product behavior (timeout / rate-limit → retry, unauthorized / not-found → abort) and `pm.failure_handler.decide` is a public surface the planner's integration test mocks. Full retirement would have required test rewrites and risked behavior drift. The "speculative" part was specifically the LLM branch — the heuristic core is load-bearing.
- **Verification**: 14/14 focused failure-handler tests pass; 189/189 wider-suite tests pass (excluding pre-broken `test_planner.py`); inline smoke test confirms `PlanManager() → pm.failure_handler.decide("connection timeout", …) → RETRY` round-trip.

### Slice 5 — Consolidate `ExecutionContext` + `PlanCheckpoint`  (Risk: High)
- **Scope**: merge into a single `ExecutionState` class; reconcile overlapping fields (`plan_id`, `session_id`, `task_results`, `workspace_dir`, `variables`).
- **Removes**: checkpoint serialization boilerplate at `execution_types.py:153-211`; clarifies plan resume semantics.
- **Why high risk**: touches `planner.py:184-227` (resume logic) and `web/server.py` persistence APIs — the latter is the external surface of the framework.
- **Recommendation**: defer until Slices 1–4 land.

---

## 6. Recommended order of attack

1. ~~**Slice 4** first~~ — **done 2026-05-07** (net −441 lines incl. test cleanup; less aggressive than full retirement, kept heuristic core).
2. **Slice 1** next — establishes the type vocabulary that Slice 2 will lean on.
3. **Slice 2** — the heaviest payoff in `orchestrator.py` readability.
4. **Slice 3** — addresses the recent `data/pipeline` regression in dispatcher cleanliness.
5. **Slice 5** — only if the three above didn't already buy enough simplicity.

---

## Notes for future re-audits

- This document was generated from a single Explore-agent pass; any line numbers will drift as code changes. Re-grep before acting.
- If after Slices 1–4 the framework still feels heavy, the next layer to investigate is the `web/server.py` persistence surface (not audited here — Tier 3).
- Type-system fragmentation is the single highest-leverage observation; do not skip Slice 1 even if it feels like "just renaming".
