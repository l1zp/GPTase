## Why

GPTase's working memory feature adds a second, implicit context path on top of explicit task inputs, direct sessions, and plan checkpoints. This increases conceptual and implementation complexity while making plan execution less predictable, because agent behavior can depend on hidden cross-session state.

## What Changes

- Remove persistent agent working memory injection and update behavior from `Agent.run()` and related execution paths.
- Remove the `AgentMemoryService` integration and the `agent_working_memory` storage surface from the runtime and memory layer.
- Remove public inspection surfaces for working memory, including the CLI and Web/API endpoints that expose it.
- Remove tests and documentation that describe working memory as a supported feature.
- **BREAKING**: GPTase will no longer preserve or expose long-lived per-agent compressed memory across runs.

## Capabilities

### New Capabilities
- `working-memory-removal`: Defines the runtime, storage, and API behavior after the working memory feature is removed.

### Modified Capabilities

## Impact

- Affected code: `gptase/agents/base.py`, `gptase/memory/agent_memory.py`, `gptase/memory/manager.py`, `gptase/memory/storage.py`, `gptase/memory/models.py`, `gptase/memory/schema.sql`, `gptase/core/orchestrator.py`, `gptase/main.py`, `gptase/web/server.py`
- Affected tests: working-memory-specific unit and API tests
- Affected docs: memory/session reference docs and any CLI/API docs that mention working memory
- Storage impact: removal of the dedicated `agent_working_memory` persistence path and its schema references
