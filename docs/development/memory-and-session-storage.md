# Memory and Session Storage

Developer notes for how GPTase currently stores conversation traces, direct
sessions, and plan checkpoints.

This document describes the implementation as it exists in the codebase today.
It is intentionally lower-level than the API reference.

## Scope

This document covers:

- the physical storage location
- the SQLite tables involved
- the difference between LLM tracking, direct sessions, and plan checkpoints
- the code paths that read and write each layer
- the Web/API surface that exposes only part of the stored state

This document does not cover:

- output workspace artifacts under `data/output/...`
- application-level business schemas produced by individual plans

## One Database, Multiple Layers

GPTase currently uses a single SQLite database by default:

```text
data/conversations.db
```

The database connection layer is:

- `gptase/memory/database.py`
- `gptase/memory/schema.sql`

At a high level:

```text
data/conversations.db
  |
  +-- LLM tracking tables
  |     conversations
  |     messages
  |     responses
  |     stream_chunks
  |     model_parameters
  |
  +-- workflow / extraction tables
  |     extraction_sessions
  |     extraction_session_steps
  |     extraction_results
  |
  +-- memory / messaging tables
  |     agent_messages
  |     agent_tasks
  |     agent_states
  |
  +-- plan checkpoint table
        plan_checkpoints
```

The important design point is that GPTase does not currently organize session
state as one file per session. Instead, multiple JSON-shaped payloads are stored
inside SQLite rows.

## Layer 1: Raw LLM Conversation Tracking

This is the lowest-level trace layer. It records model calls and their inputs
and outputs.

Relevant tables:

- `conversations`
- `messages`
- `responses`
- `stream_chunks`
- `model_parameters`

Primary code path:

- `gptase/models/model.py`
- `gptase/memory/storage.py`

Typical write flow:

```text
Model.generate() / generate_stream()
  -> ConversationStorage.start_conversation()
  -> ConversationStorage.add_messages()
  -> ConversationStorage.add_response()
  -> ConversationStorage.add_stream_chunk()   # streaming only
  -> ConversationStorage.complete_conversation()
```

What this layer is for:

- request/response auditing
- debugging model usage
- reconstructing message inputs and final outputs
- streaming replay at the raw response chunk level

What this layer is not:

- it is not the same thing as a user-facing chat session
- it is not the same thing as a resumable plan session

One direct session or one plan step can involve one or more rows in these
tables, depending on how the agent runs.

## Layer 2: Direct Sessions

Direct sessions are the chat-style sessions returned by:

- `POST /api/chat`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`

The runtime model for this is `DirectSession` in:

- `gptase/agents/types.py`

The shape contains:

- `session_id`
- `session_type`
- `title`
- `status`
- `agent_id`
- `messages`
- `traces`
- `metadata`
- `created_at`
- `updated_at`

### Where direct sessions are stored

Direct sessions are serialized as JSON and stored inside `agent_states`:

```text
agent_states.agent_id   = chat_session:<session_id>
agent_states.state_data = { ... DirectSession JSON ... }
```

or:

```text
agent_states.agent_id   = agent_session:<session_id>
agent_states.state_data = { ... DirectSession JSON ... }
```

The relevant orchestrator methods are in `gptase/core/orchestrator.py`:

- `_generate_direct_session_id()`
- `_direct_session_state_key()`
- `_save_direct_session()`
- `_load_direct_session()`
- `_load_any_direct_session()`
- `list_sessions()`
- `get_session_status()`

### Message and trace organization inside a direct session

Each direct session stores:

- `messages`: UI-facing thread entries
- `traces`: summarized execution trace entries derived from runtime output

These are not stored as append-only rows in separate tables. The whole
`DirectSession` object is rewritten into `agent_states.state_data` on each save.

That means the storage model is currently:

```text
latest snapshot only
```

not:

```text
full append-only event history
```

### Implications

Pros:

- simple load/save path
- easy to return through the Web API
- direct mapping to UI session state

Tradeoffs:

- no separate event log for direct-session evolution
- no per-message row-level querying for these UI sessions
- updating one message rewrites the whole session snapshot

## Layer 3: Plan Checkpoints

Plan execution uses a different storage model from direct sessions.

The runtime context is defined in:

- `gptase/agents/execution_types.py`

Important types:

- `ExecutionContext`
- `TaskExecutionResult`
- `PlanCheckpoint`

### Where plan checkpoints are stored

Plan checkpoints live in the `plan_checkpoints` table.

Important columns:

- `session_id`
- `plan_id`
- `status`
- `total_steps`
- `completed_steps`
- `checkpoint_data`

`checkpoint_data` is a serialized JSON snapshot of the latest checkpoint.

Primary code path:

- `gptase/agents/planner.py`

Relevant methods:

- `_save_checkpoint_to_db()`
- `_load_checkpoint_from_db()`
- `list_sessions()`
- `get_session_status()`
- `execute_plan()`

### What goes into checkpoint_data

The checkpoint snapshot includes:

- `plan_id`
- `session_id`
- `input_data`
- `document_path`
- `tasks`
- `variables`
- `workspace_dir`
- progress metadata such as total/completed task counts

Each `tasks[task_id]` record can contain:

- latest lifecycle `status`
- terminal `output`
- terminal `trace`
- in-progress `resume_state`
- lightweight `attempts` summaries

This is what makes resumption possible.

### Direct session vs plan checkpoint

These two are easy to confuse, but they are separate:

```text
Direct session
  -> stored in agent_states
  -> used by chat / worker session APIs
  -> contains messages + traces

Plan checkpoint
  -> stored in plan_checkpoints
  -> used by plan resume / status logic
  -> contains unified per-task runtime state
```

The current Web API only exposes the first class directly.

## Web/API View of Stored Data

The Web API does not expose every storage layer symmetrically.

Relevant file:

- `gptase/web/server.py`

Current behavior:

- `GET /api/sessions` returns recent direct sessions only
- `GET /api/sessions/{session_id}` returns direct session state only
- plan session IDs return `null` from the direct session status endpoint
- plan status and resume use the plan checkpoint path instead

So the externally visible model is narrower than the internal storage model.

```text
Internal storage:
  direct sessions + checkpoints + raw conversations

Web session API:
  direct sessions only
```

## Current Storage Pattern Summary

The codebase currently mixes two persistence styles:

1. Relational row storage
   Examples:
   - `conversations`
   - `messages`
   - `responses`
   - `stream_chunks`

2. JSON snapshot storage inside SQLite rows
   Examples:
   - `agent_states.state_data`
   - `plan_checkpoints.checkpoint_data`

That means GPTase already has structured JSON session state, but it is embedded
in SQLite instead of being written as standalone files.

## Practical Debugging Checklist

When you need to inspect a user-visible chat or agent session:

- look in `agent_states`
- find keys with `chat_session:` or `agent_session:`
- deserialize `state_data`

When you need to inspect a resumable plan run:

- look in `plan_checkpoints`
- find the row by `session_id`
- deserialize `checkpoint_data`

When you need raw model-call traces:

- inspect `conversations`, `messages`, `responses`, and `stream_chunks`

## Code Map

Storage and schema:

- `gptase/memory/schema.sql`
- `gptase/memory/database.py`
- `gptase/memory/storage.py`

High-level memory interface:

- `gptase/memory/manager.py`

Direct sessions:

- `gptase/agents/types.py`
- `gptase/core/orchestrator.py`

Plan checkpointing:

- `gptase/agents/execution_types.py`
- `gptase/agents/planner.py`

Web exposure:

- `gptase/web/server.py`

## Gaps and Constraints in the Current Design

Current constraints worth keeping in mind:

- direct sessions are snapshot-based, not event-log-based
- plan checkpoints store the latest resumable state, not a full checkpoint
  history per task turn
- raw LLM tracking and user-facing session state are related, but not unified
  under one shared session artifact
- there is no per-session file tree similar to transcript-based systems

These constraints are important if you want to evolve the design toward:

- per-session JSON artifacts
- append-only event logs
- session export/import
- file-based resume
