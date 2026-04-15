## 1. Remove Runtime Integration

- [x] 1.1 Remove working-memory loading and update hooks from `gptase/agents/base.py`
- [x] 1.2 Delete `gptase/memory/agent_memory.py` usage and clean up related imports and initialization paths
- [x] 1.3 Remove working-memory-specific config handling that no longer affects runtime behavior

## 2. Remove Storage and Public Surfaces

- [x] 2.1 Remove `agent_working_memory` models, manager methods, and storage helpers from the memory layer
- [x] 2.2 Remove the dedicated `agent_working_memory` schema definition and any reset/cleanup logic that references it
- [x] 2.3 Remove CLI and Web/API endpoints for inspecting working memory

## 3. Update Documentation and Tests

- [x] 3.1 Remove or rewrite tests that assume working-memory injection, persistence, or inspection support
- [x] 3.2 Update reference and development docs to describe the post-removal memory/session model
- [x] 3.3 Verify there are no remaining user-facing references to working memory in CLI help, API docs, or developer docs

## 4. Validate Feature Removal

- [x] 4.1 Run targeted tests for agent execution, memory storage, CLI dispatch, and Web server behavior after the removal
- [x] 4.2 Confirm direct sessions, plan checkpoints, and raw conversation tracking still work without hidden working-memory state
