## Context

Working memory is currently implemented as an agent-scoped summary layer that is loaded before `Agent.run()` and updated after successful runs. It is persisted separately from direct sessions and plan checkpoints in the `agent_working_memory` table, and it is also exposed through dedicated CLI and Web/API surfaces.

This creates a cross-cutting feature that touches agent execution, memory storage, runtime configuration, documentation, and user-facing inspection endpoints. The removal must preserve the rest of the conversation/session model: raw LLM tracking, direct session snapshots, and plan checkpoints must continue to work without any hidden memory injection path.

## Goals / Non-Goals

**Goals:**
- Remove all runtime behavior that loads or updates persistent working memory.
- Remove dedicated storage, models, and manager methods for working memory.
- Remove user-facing CLI and Web/API inspection surfaces for working memory.
- Keep direct sessions, plan checkpoints, and low-level conversation tracking intact.
- Leave the post-removal architecture with a single explicit context path: task input, session state, and checkpoint state.

**Non-Goals:**
- Redesigning the full session storage model in this change.
- Replacing working memory with a new memory abstraction.
- Changing direct session or checkpoint semantics beyond removing working-memory references.

## Decisions

### 1. Remove the feature completely rather than disabling it by config

The codebase already treats working memory as optional in places, but the feature still adds model-time branching, storage schema, and public APIs. Keeping a dormant code path would preserve most of the conceptual overhead. Full removal is the simpler end state.

Alternative considered:
- Keep the feature but set `memory.enabled=false` by default.
  Rejected because the code, schema, tests, and docs would still carry the complexity.

### 2. Preserve other memory/session layers unchanged

The change removes only the working-memory layer. It does not merge or redesign:

- raw LLM conversation tracking in `conversations` / `messages` / `responses`
- direct sessions stored in `agent_states`
- plan checkpoints stored in `plan_checkpoints`

Alternative considered:
- Combine removal with a larger session-storage refactor.
  Rejected because it increases scope and migration risk for a change whose goal is simplification by deletion.

### 3. Remove user-facing access surfaces together with runtime support

The CLI command and Web/API endpoint for working memory should be removed in the same change. Keeping read-only inspection endpoints for deleted runtime behavior would create dead or misleading product surface.

Alternative considered:
- Keep inspection endpoints temporarily for backward compatibility.
  Rejected because they would expose stale or no-longer-updated state with unclear semantics.

### 4. Remove the dedicated persistence path from the schema and storage layer

The `agent_working_memory` table and its storage helpers should be removed along with the runtime integration. This keeps the database schema aligned with supported features.

Alternative considered:
- Leave the table in place but unused.
  Rejected because it preserves storage complexity and makes the schema harder to reason about.

## Risks / Trade-offs

- [Breaking existing workflows that relied on cross-run agent summaries] -> Remove all public references, update docs, and keep explicit task/session context paths documented as the supported mechanism.
- [Tests or code paths still importing `AgentMemoryService`] -> Remove imports and run targeted cleanup across agent, memory, CLI, and Web modules.
- [Schema compatibility concerns for existing databases] -> Treat this as a forward schema cleanup; runtime should not depend on the removed table after the change.
- [Confusion between removing working memory and removing all memory] -> Keep docs explicit that direct sessions, checkpoints, and low-level conversation tracking remain supported.
