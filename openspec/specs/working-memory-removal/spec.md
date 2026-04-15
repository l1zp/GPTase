# working-memory-removal Specification

## Purpose
TBD - created by archiving change remove-working-memory. Update Purpose after archive.
## Requirements
### Requirement: Agents execute without persistent working memory
The system SHALL execute named and anonymous agents without loading, injecting, or updating any persistent working-memory summary.

#### Scenario: Named agent run does not inject prior summary
- **WHEN** a named agent executes a task
- **THEN** the runtime MUST not prepend any stored working-memory context to the task input

#### Scenario: Agent run does not update persistent memory
- **WHEN** an agent run completes successfully or fails
- **THEN** the runtime MUST not write or refresh any per-agent working-memory summary

### Requirement: GPTase exposes no working-memory inspection surface
The system SHALL not expose CLI or Web/API interfaces for inspecting agent working memory.

#### Scenario: CLI surface is removed
- **WHEN** a user inspects the available GPTase CLI commands
- **THEN** there MUST be no supported command for reading agent working memory

#### Scenario: Web/API surface is removed
- **WHEN** a client inspects the supported Web/API endpoints
- **THEN** there MUST be no supported endpoint for retrieving agent working memory

### Requirement: Dedicated working-memory persistence is removed
The system SHALL not define or use a dedicated persistent storage path for agent working memory.

#### Scenario: Storage layer has no dedicated working-memory table dependency
- **WHEN** the memory schema and storage layer are initialized
- **THEN** they MUST not require a dedicated `agent_working_memory` persistence path to support supported runtime features

#### Scenario: Remaining session storage continues to function explicitly
- **WHEN** direct sessions, plan checkpoints, or low-level LLM conversation tracking are used
- **THEN** they MUST continue to operate through their explicit storage paths without relying on hidden working-memory state
