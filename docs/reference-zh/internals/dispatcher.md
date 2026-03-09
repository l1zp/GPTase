# 调度器内部实现

> [首页](../README.md) → [内部实现](./) → 调度器

**文件：** `gptase/sop/dispatcher.py`

---

## TaskDispatcher

`TaskDispatcher` 是 SOP 编排器与各 Agent 之间的桥梁。每个 `SOPOrchestratorAgent` 实例化时创建一个，并在整个执行生命周期内持续存在。

```python
dispatcher = TaskDispatcher(
    memory_manager=memory_manager,
    model_manager=model_manager,
)
```

### Agent 缓存

Agent 按需创建，缓存在 `self._agents: Dict[str, Agent]` 中：

```python
async def _get_agent(agent_id: str) -> Agent:
    if agent_id in self._agents:
        return self._agents[agent_id]   # 复用
    agent = Agent.from_markdown(agent_id, model_manager=...)
    self._agents[agent_id] = agent
    return agent
```

这意味着同一个 Agent 实例在一次 SOP 执行中处理多个步骤。每次 `dispatch()` 调用时，Agent 的 `workspace_dir` 会被覆写为当前文档目录。调用 `dispatcher.clear_agents()` 可重置缓存。

---

## `dispatch()` 逐步分解

```
dispatch(step, context)
  │
  ├─ 1. _get_agent(step.agent)
  │       └─ Agent.from_markdown(agent_id)  （或从缓存获取）
  │
  ├─ 2. 设置 agent.workspace_dir = context.document_path 或 context.workspace_dir
  │
  ├─ 3. 准备 Agent 输出目录：
  │       agent_workspace = workspace_dir / step.agent
  │       agent_workspace.mkdir(parents=True, exist_ok=True)
  │
  ├─ 4. _resolve_inputs(step.inputs, context)
  │       → 展开模板变量后的解析字典
  │
  ├─ 5. _normalize_image_fields(resolved_inputs)
  │       → 从图片元数据字典中提取字符串路径
  │
  ├─ 6. AgentTask(action=step.action, step_id=step.step_id, **resolved_inputs)
  │
  ├─ 7. agent.process_task(task) → {"status":..., "data":{...}}
  │
  ├─ 8. TaskResult(agent_id, step_id, status, data, execution_time)
  │
  └─ 9. 如果成功且有 workspace：
          ├─ 写入 workspace/agent_name/step_id_result.json
          └─ _post_process_result(step, task_result, agent_workspace)
```

---

## 模板变量解析

`_resolve_inputs()` 遍历 `step.inputs`，对每个值调用 `_resolve_value()`。只有匹配 `{{...}}` 的字符串值会被解析；其他所有类型直接透传。

### `_resolve_value()` 的解析顺序

| 模板 | 解析为 |
|---|---|
| `{{input_text}}` | `context.input_data["text"]` |
| `{{document_path}}` | `context.document_path` 或 `context.input_data["document_path"]` |
| `{{input_data}}` | 完整的 `context.input_data` 字典 |
| `{{stepN}}` | `_resolve_step_reference("stepN", context)` |
| `{{stepN.field.nested}}` | 步骤 N 结果数据中的嵌套字段 |
| `{{var_name}}` | `context.variables["var_name"]` |
| `{{var_name}}`（回退） | `context.input_data["var_name"]` |
| 未知变量 | 原样返回，并输出警告 |

非字符串值（int、list、dict）不经过模板处理，直接返回。

### 步骤引用解析（`_resolve_step_reference`）

```
ref = "step2a.analysis.images"
  │
  ├─ split(".", 1) → ["step2a", "analysis.images"]
  ├─ step_id = "2a"    （去除 "step" 前缀）
  ├─ step_data = context.get_step_data("2a")  → TaskResult.data 字典
  │
  └─ _get_nested_field(step_data, "analysis.images")
```

### 嵌套字段解析（`_get_nested_field`）

嵌套字段遍历器为 JSON 包装的 LLM 输出提供了特殊回退机制：

```
data = {"content": "```json\n{\"analysis\":{\"images\":[...]}}\n```"}
path = "analysis.images"

遍历路径 = ["analysis", "images"]：
  ├─ 步骤 "analysis"：不在 data 中
  ├─ 但存在 "content" 键 → _try_parse_content_json(data["content"])
  │       → {"analysis": {"images": [...]}}
  ├─ "analysis" 在已解析数据中？是
  ├─ current = parsed["analysis"] = {"images": [...]}
  └─ 步骤 "images"：在 current 中 → 返回 [...]
```

这意味着 Agent 可以输出原始 JSON 或 markdown 代码块包裹的 JSON，下游步骤无需任何手动解包即可引用嵌套字段。

---

## `_try_parse_content_json()` — 四重解析策略

该方法按顺序尝试四种策略：

```python
# 策略 1：markdown ```json 代码块
if "```json" in content:
    json_part = content.split("```json")[1].split("```")[0]
    return json.loads(json_part)
    # 失败时：用正则修复尾部逗号

# 策略 2：通用 ``` 代码块
elif content.startswith("```"):
    json_part = content.split("```")[1]
    # 如果有语言标识符行则跳过
    return json.loads(json_part)

# 策略 3：原始 JSON（以 { 或 [ 开头）
if content.startswith("{") or content.startswith("["):
    return json.loads(content)

# 策略 4：正则扫描第一个 {...} 对象
json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
return json.loads(json_match.group())
```

策略 1 还包含尾部逗号修复步骤（`re.sub(r',\s*([}\]])', r'\1', ...)`），用于处理 LLM 常见的 JSON 格式错误。

---

## 图片字段归一化（`_normalize_image_fields`）

当图片来自上一步骤的结果（例如 `{{step1.images}}`）时，可能是元数据字典结构而非纯路径：

```python
# 来自 document-structure-analyzer 步骤的数据：
images = [
    {"figure_id": "Figure 3a", "image_path": "/doc/images/figure_3a.png", ...},
    {"figure_id": "Figure 4",  "image_path": None, ...},
]

# AgentTask 需要的格式：
images = ["/doc/images/figure_3a.png"]
```

归一化逻辑：

```
对 ["images", "image_paths"] 中的每个字段：
  如果值是字典列表：
    对每个元素：
      尝试 item["image_path"]  → 非空则使用
      否则：通过正则提取 figure_id 中的图号 "Figure\s*(\d+[a-z]?)"
            尝试模式：images/figure_N.png, images/fig_N.png, ...
            如果文件在 workspace 中存在 → 使用该路径
    如果没有找到路径 → 将字段设为 []（并输出警告）
```

路径解析的 `workspace` 来自 `inputs["workspace_dir"]` 或 `inputs["document_path"]`。

---

## `_post_process_result()` — 自动文件提取

步骤成功后，调度器会尝试从 LLM 的文本输出中提取结构化文件：

```
_post_process_result(step, task_result, agent_workspace)
  │
  ├─ 获取 task_result.data["content"]（字符串）
  ├─ 解析为 JSON（与 _try_parse_content_json 相同逻辑）
  │
  ├─ 写入：workspace/agent_name/step_id_parsed.json
  │
  ├─ 有 "extracted_tables" 键？
  │    └─ 对每个表格：从 csv_data 字段写入 table_{image_number}.csv
  │
  └─ 通用键："reactions"、"tables"、"images"、"sections"、"analysis_results"
       └─ 每个字典列表 → 写入 step_id_{key}.csv
```

CSV 写入会收集所有字典条目的所有唯一键作为表头列。嵌套的 dict/list 值在每个单元格中会被 JSON 序列化。

---

## 并行调度

```python
async def dispatch_parallel(steps, context, max_concurrent=10):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def dispatch_with_semaphore(step):
        async with semaphore:
            return await self.dispatch(step, context)

    results = await asyncio.gather(
        *[dispatch_with_semaphore(s) for s in steps],
        return_exceptions=True,
    )
    # 异常 → TaskResult(status="failed", error=str(exc))
```

`max_concurrent` 值来自 `SOPDefinition.max_parallel`（默认 10）。并行组中的所有步骤共享同一个 `context`，这意味着它们可以看到之前顺序步骤的结果，但彼此之间无法互相获取结果（因为是并发执行的）。

---

*相关：[执行流程 →](./execution-flow.md) | [SOP API →](../api/sop.md)*
