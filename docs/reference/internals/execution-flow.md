# Execution Flow

> [Home](../README.md) → [Internals](./) → Execution Flow

**Files:** `gptase/agents/base.py`, `gptase/sop/orchestrator_agent.py`

---

## Single-Agent Execution

When you call `await agent.run(content, image_paths=...)`, the flow is:

```
agent.run(content, image_paths)
  │
  ├─ image_paths provided?
  │    ├─ yes: _load_image_as_content() for each path → base64 + MIME
  │    │       content list = [img1, img2, ..., {"type":"text","text":content}]
  │    └─ no:  content list = [{"type":"text","text":content}]
  │
  ├─ is_claude_model()?  (model_name.startswith("claude-"))
  │    ├─ yes: _run_with_sdk(content_list)
  │    └─ no:  _run_with_llm(content_list)
  │
  └─ return {"status":"success","data":{...}}  or  {"status":"error","error":"..."}
```

### Claude SDK Path (`_run_with_sdk`)

Delegates directly to the Claude Agent SDK. The SDK handles multi-turn tool use internally, including tool call execution and result injection. The agent's `tools` list from the YAML frontmatter is passed as allowed tools.

```
_run_with_sdk(content_list)
  │
  ├─ Build messages: [{"role":"user","content":content_list}]
  ├─ sdk.run(messages, tools=self.tools, system=self.system_prompt, ...)
  └─ Return normalized {"status": ..., "data": {"content": response_text}}
```

### LLM Loop Path (`_run_with_llm`)

Implements a multi-turn ReAct-style loop using `ToolExecutor`:

```
_run_with_llm(content_list)
  │
  ├─ Build messages list (with system prompt)
  ├─ loop (max 10 iterations):
  │    ├─ model.generate(messages, tools=tool_schemas)
  │    ├─ finish_reason == "stop"?  → break, return content
  │    ├─ finish_reason == "tool_calls"?
  │    │    ├─ for each tool_call in response.tool_calls:
  │    │    │    tool_executor.execute(tool_name, tool_args)
  │    │    └─ append assistant + tool results to messages
  │    └─ continue loop
  └─ Return {"status":"success","data":{"content": final_text}}
```

### `process_task()` Pre-processing

Before `run()`, `process_task(task: AgentTask)` performs:

1. `task.get_image_paths()` — merges `image_path`, `image_paths`, `images` fields, deduplicates preserving order
2. `_build_user_prompt(task)` — serializes task to JSON, injects as user message text
3. Calls `run(prompt_text, image_paths=merged_paths)`

The `AgentTask` model uses `extra="allow"`, so any extra fields (passed in from SOP step `inputs`) become part of the JSON prompt automatically.

---

## SOP Execution Flow

```
orchestrator.execute_sop(plan_id, input_data, ...)
  │
  ├─ registry.get_sop(plan_id)       → SOPDefinition
  ├─ _calculate_sop_hash(sop)        → MD5 of step signatures
  │
  ├─ checkpoint/session provided?
  │    ├─ checkpoint dict: ExecutionContext.from_checkpoint(checkpoint)
  │    ├─ session_id: _load_checkpoint_from_db(session_id) → from_checkpoint()
  │    └─ fresh: new ExecutionContext(plan_id, input_data, ...)
  │
  ├─ set_variable("input_data", input_data)
  ├─ set_variable("input_text", input_data["text"])   (if present)
  │
  ├─ _start_session(sop, context)    → store AgentState in memory
  ├─ _save_checkpoint_to_db(...)     (if auto_checkpoint)
  │
  ├─ for each workflow_item in sop.workflow:
  │    ├─ ParallelStep?
  │    │    └─ _execute_parallel_with_resume(parallel_step, context, sop)
  │    └─ SOPStep?
  │         └─ _execute_step_with_resume(step, context, sop)
  │    └─ _save_checkpoint_to_db(...)  (after each item)
  │
  ├─ context.to_result() → final dict
  ├─ _save_checkpoint_to_db(..., "completed")
  └─ return result
```

### Step Execution with Resume Logic

`_execute_step_with_resume()` checks the existing context before running:

```
_execute_step_with_resume(step, context, sop)
  │
  ├─ existing = context.get_step_result(step.step_id)
  │
  ├─ existing.status == SUCCESS?
  │    └─ return existing_result  (skip — already done)
  │
  ├─ existing.status == FAILED?
  │    └─ pop from context.step_results (clear for retry)
  │
  └─ _execute_step(step, context, sop)
       ├─ context.current_step = step.step_id
       ├─ create StepResult(status=RUNNING), update context
       ├─ dispatcher.dispatch(step, context) → TaskResult
       ├─ success? update StepResult(SUCCESS), return
       └─ failure? _handle_failure(step, result, context, sop)
```

### Parallel Execution with Resume

`_execute_parallel_with_resume()` categorizes existing steps before re-running:

```
_execute_parallel_with_resume(parallel_step, context, sop)
  │
  ├─ Categorize all steps:
  │    ├─ completed_steps  (status == SUCCESS)  → skip
  │    ├─ pending_steps    (no result yet)       → execute
  │    └─ failed_steps     (status == FAILED)    → clear + retry
  │
  ├─ steps_to_execute = pending_steps + failed_steps
  ├─ dispatcher.dispatch_parallel(steps_to_execute, context, max_concurrent=sop.max_parallel)
  │    └─ asyncio.gather with semaphore(max_concurrent)
  └─ for each (step, result): update context or _handle_failure()
```

### Failure Handling

`_handle_failure()` runs an AI-driven recovery loop:

```
_handle_failure(step, result, context, sop)
  │
  ├─ max_retries = step.retry_count or sop.default_retry_count or 3
  ├─ attempt = 0
  │
  └─ loop:
       ├─ failure_handler.decide(step, error, context, attempt) → FailureDecision
       │
       ├─ ABORT: update context(FAILED), raise SOPExecutionError
       │          └─ caller saves checkpoint, adds session_id to error details
       │
       ├─ SKIP:  update context(SKIPPED), return step_result
       │
       └─ RETRY:
            ├─ attempt += 1
            ├─ attempt > max_retries? → raise SOPExecutionError("Max retries exceeded")
            ├─ dispatcher.dispatch(step, context) → new result
            ├─ success? update context(SUCCESS), return
            └─ update error, continue loop
```

---

## Checkpoint Lifecycle

```
Session ID format: "sop_YYYYMMDD_HHMMSS_<8hex>"

execute_sop()
  │
  ├─ [start]    _save_checkpoint("in_progress")
  ├─ [step N]   _save_checkpoint("in_progress")   ← after each workflow item
  ├─ [success]  _save_checkpoint("completed")
  └─ [failure]  _save_checkpoint("failed")
                └─ session_id added to SOPExecutionError.details

resume_sop(session_id)
  ├─ load_checkpoint(session_id)          → validates version + required fields
  ├─ execute_sop(plan_id, ..., checkpoint=data)
  └─ _execute_step_with_resume() skips SUCCESS steps automatically
```

### SOP Hash Compatibility

Before restoring from a checkpoint, the SOP hash is calculated:

```python
# Hash = MD5[:16] of pipe-separated step signatures
"step:1:document-structure-analyzer|parallel:2a,2b|step:3:summarizer"
```

If the YAML has changed structure (steps added/removed/reordered), the hash differs. Invalid step IDs in the checkpoint are silently removed by `ExecutionContext.from_checkpoint()`.

---

## Data Flow Diagram

```
input_data
    │
    ▼
ExecutionContext.input_data
    │   variables["input_text"] = input_data["text"]
    │
    ▼
Step 1: dispatcher.dispatch()
    │   _resolve_inputs(step.inputs, context)
    │      {{input_text}} → context.input_data["text"]
    │
    ▼
TaskResult.data = {"content": "..."}
    │
    ▼
context.step_results["1"] = StepResult(result=TaskResult)
    │
    ▼
Step 2: dispatcher.dispatch()
    │   {{step1}}       → context.get_step_data("1")
    │   {{step1.field}} → get_nested_field(data, "field")
    │                     └─ fallback: parse content as JSON, retry lookup
    │
    ▼
context.to_result()
    → {"step_results": {"1": {...}, "2": {...}}, ...}
```

---

*Related: [Dispatcher Internals →](./dispatcher.md) | [SOP API →](../api/sop.md)*
