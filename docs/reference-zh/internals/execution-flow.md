# 执行流程

> [首页](../README.md) → [内部实现](./) → 执行流程

**文件：** `gptase/agents/base.py`、`gptase/sop/orchestrator_agent.py`

---

## 单 Agent 执行

调用 `await agent.run(content, image_paths=...)` 时的执行流程：

```
agent.run(content, image_paths)
  │
  ├─ 提供了 image_paths？
  │    ├─ 是：对每张图片调用 _load_image_as_content() → base64 + MIME
  │    │       content list = [img1, img2, ..., {"type":"text","text":content}]
  │    └─ 否：content list = [{"type":"text","text":content}]
  │
  ├─ is_claude_model()？  (model_name.startswith("claude-"))
  │    ├─ 是：_run_with_sdk(content_list)
  │    └─ 否：_run_with_llm(content_list)
  │
  └─ 返回 {"status":"success","data":{...}}  或  {"status":"error","error":"..."}
```

### Claude SDK 路径（`_run_with_sdk`）

直接委托给 Claude Agent SDK。SDK 在内部处理多轮工具调用，包括工具执行和结果注入。YAML 头部中的 `tools` 列表作为允许的工具传入。

```
_run_with_sdk(content_list)
  │
  ├─ 构建消息：[{"role":"user","content":content_list}]
  ├─ sdk.run(messages, tools=self.tools, system=self.system_prompt, ...)
  └─ 返回标准化的 {"status": ..., "data": {"content": response_text}}
```

### LLM 循环路径（`_run_with_llm`）

使用 `ToolExecutor` 实现多轮 ReAct 风格循环：

```
_run_with_llm(content_list)
  │
  ├─ 构建消息列表（含 system prompt）
  ├─ 循环（最多 10 次）：
  │    ├─ model.generate(messages, tools=tool_schemas)
  │    ├─ finish_reason == "stop"？ → 跳出循环，返回 content
  │    ├─ finish_reason == "tool_calls"？
  │    │    ├─ 对每个 tool_call：
  │    │    │    tool_executor.execute(tool_name, tool_args)
  │    │    └─ 将 assistant + 工具结果追加到 messages
  │    └─ 继续循环
  └─ 返回 {"status":"success","data":{"content": final_text}}
```

### `process_task()` 预处理

在 `run()` 之前，`process_task(task: AgentTask)` 会执行：

1. `task.get_image_paths()` — 合并 `image_path`、`image_paths`、`images` 三个字段，去重并保留顺序
2. `_build_user_prompt(task)` — 将 task 序列化为 JSON，注入为用户消息文本
3. 调用 `run(prompt_text, image_paths=merged_paths)`

`AgentTask` 模型使用 `extra="allow"`，因此从 SOP 步骤 `inputs` 传入的任何额外字段都会自动成为 JSON 提示的一部分。

---

## SOP 执行流程

```
orchestrator.execute_sop(plan_id, input_data, ...)
  │
  ├─ registry.get_sop(plan_id)       → SOPDefinition
  ├─ _calculate_sop_hash(sop)        → 步骤签名的 MD5
  │
  ├─ 提供了 checkpoint/session？
  │    ├─ checkpoint 字典：ExecutionContext.from_checkpoint(checkpoint)
  │    ├─ session_id：_load_checkpoint_from_db(session_id) → from_checkpoint()
  │    └─ 全新执行：new ExecutionContext(plan_id, input_data, ...)
  │
  ├─ set_variable("input_data", input_data)
  ├─ set_variable("input_text", input_data["text"])   （如果存在）
  │
  ├─ _start_session(sop, context)    → 在内存中存储 AgentState
  ├─ _save_checkpoint_to_db(...)     （如果 auto_checkpoint）
  │
  ├─ 遍历 sop.workflow 中的每个 workflow_item：
  │    ├─ ParallelStep？
  │    │    └─ _execute_parallel_with_resume(parallel_step, context, sop)
  │    └─ SOPStep？
  │         └─ _execute_step_with_resume(step, context, sop)
  │    └─ _save_checkpoint_to_db(...)  （每个 item 后）
  │
  ├─ context.to_result() → 最终结果字典
  ├─ _save_checkpoint_to_db(..., "completed")
  └─ 返回结果
```

### 带恢复逻辑的步骤执行

`_execute_step_with_resume()` 在运行前检查现有 context：

```
_execute_step_with_resume(step, context, sop)
  │
  ├─ existing = context.get_step_result(step.step_id)
  │
  ├─ existing.status == SUCCESS？
  │    └─ 返回 existing_result  （跳过 — 已完成）
  │
  ├─ existing.status == FAILED？
  │    └─ 从 context.step_results 中删除（清除以便重试）
  │
  └─ _execute_step(step, context, sop)
       ├─ context.current_step = step.step_id
       ├─ 创建 StepResult(status=RUNNING)，更新 context
       ├─ dispatcher.dispatch(step, context) → TaskResult
       ├─ 成功？更新 StepResult(SUCCESS)，返回
       └─ 失败？_handle_failure(step, result, context, sop)
```

### 带恢复逻辑的并行执行

`_execute_parallel_with_resume()` 在重新运行前对现有步骤进行分类：

```
_execute_parallel_with_resume(parallel_step, context, sop)
  │
  ├─ 对所有步骤分类：
  │    ├─ completed_steps  (status == SUCCESS)  → 跳过
  │    ├─ pending_steps    （无结果）             → 执行
  │    └─ failed_steps     (status == FAILED)    → 清除并重试
  │
  ├─ steps_to_execute = pending_steps + failed_steps
  ├─ dispatcher.dispatch_parallel(steps_to_execute, context, max_concurrent=sop.max_parallel)
  │    └─ asyncio.gather + semaphore(max_concurrent)
  └─ 对每对 (step, result)：更新 context 或调用 _handle_failure()
```

### 失败处理

`_handle_failure()` 运行 AI 驱动的恢复循环：

```
_handle_failure(step, result, context, sop)
  │
  ├─ max_retries = step.retry_count or sop.default_retry_count or 3
  ├─ attempt = 0
  │
  └─ 循环：
       ├─ failure_handler.decide(step, error, context, attempt) → FailureDecision
       │
       ├─ ABORT：更新 context(FAILED)，抛出 SOPExecutionError
       │          └─ 调用方保存 checkpoint，将 session_id 添加到错误详情
       │
       ├─ SKIP：更新 context(SKIPPED)，返回 step_result
       │
       └─ RETRY：
            ├─ attempt += 1
            ├─ attempt > max_retries？ → 抛出 SOPExecutionError("超过最大重试次数")
            ├─ dispatcher.dispatch(step, context) → 新结果
            ├─ 成功？更新 context(SUCCESS)，返回
            └─ 更新错误信息，继续循环
```

---

## Checkpoint 生命周期

```
Session ID 格式："sop_YYYYMMDD_HHMMSS_<8hex>"

execute_sop()
  │
  ├─ [开始]   _save_checkpoint("in_progress")
  ├─ [步骤 N] _save_checkpoint("in_progress")   ← 每个 workflow item 后
  ├─ [成功]   _save_checkpoint("completed")
  └─ [失败]   _save_checkpoint("failed")
               └─ session_id 添加到 SOPExecutionError.details

resume_sop(session_id)
  ├─ load_checkpoint(session_id)          → 验证版本和必填字段
  ├─ execute_sop(plan_id, ..., checkpoint=data)
  └─ _execute_step_with_resume() 自动跳过 SUCCESS 步骤
```

### SOP 哈希兼容性

从 checkpoint 恢复之前，会计算 SOP 哈希：

```python
# 哈希 = MD5[:16]，由管道分隔的步骤签名组成
"step:1:document-structure-analyzer|parallel:2a,2b|step:3:summarizer"
```

如果 YAML 的结构发生变化（步骤增减或重排），哈希就会不同。checkpoint 中无效的步骤 ID 会被 `ExecutionContext.from_checkpoint()` 静默删除。

---

## 数据流图

```
input_data
    │
    ▼
ExecutionContext.input_data
    │   variables["input_text"] = input_data["text"]
    │
    ▼
步骤 1：dispatcher.dispatch()
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
步骤 2：dispatcher.dispatch()
    │   {{step1}}       → context.get_step_data("1")
    │   {{step1.field}} → get_nested_field(data, "field")
    │                     └─ 回退：将 content 解析为 JSON，重试查找
    │
    ▼
context.to_result()
    → {"step_results": {"1": {...}, "2": {...}}, ...}
```

---

*相关：[调度器内部实现 →](./dispatcher.md) | [SOP API →](../api/sop.md)*
