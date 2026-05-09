# Slice 1 落地复盘（含已知缺陷）

**日期**：2026-05-08
**前置文档**：[coordinator_only_refactor_2026-05-08_zh.md](coordinator_only_refactor_2026-05-08_zh.md)
**状态**：Slice 1 代码全部 land 并通过 e2e，但**效果未达 plan run 基线**，本文记录差距与根因，供 Slice 2/3 推进前参考。

---

## 1. 实际落地的代码变更

| 类型 | 文件 | 说明 |
|---|---|---|
| 加 | [gptase/agents/plan_prompt.py](../../gptase/agents/plan_prompt.py) | YAML→Coordinator prompt 扩展器（~310 LoC，新旧 schema 兼容） |
| 加 | [.claude/agents/enzyme-variant-normalizer/tools.py](../../.claude/agents/enzyme-variant-normalizer/tools.py) | `NormalizeEnzymeVariantsTool` |
| 改 | [.claude/agents/enzyme-variant-normalizer/enzyme-variant-normalizer.md](../../.claude/agents/enzyme-variant-normalizer/enzyme-variant-normalizer.md) | 新增 `deterministic: true`，重写为 LLM-trampoline |
| 改 | [gptase/agents/base.py](../../gptase/agents/base.py) | `Agent.from_markdown` 自动发现 sibling `tools.py`；带 `allowed_agents` 权限隔离；deterministic 字段验证 |
| 改 | [gptase/agents/types.py](../../gptase/agents/types.py) | `AgentDefinition.deterministic: bool` |
| 改 | [gptase/core/types.py](../../gptase/core/types.py) | `DispatchRequest.disable_plan_handoff: bool` |
| 改 | [gptase/core/orchestrator.py](../../gptase/core/orchestrator.py) | `_MAX_COORDINATOR_TURNS = 10`；orchestrator agent `tools=["DelegateTask"]`（关键 bug fix）；`DelegateTaskTool.orchestrator = self`（Slice 1.9 修复）；`disable_plan_handoff` 路由 |
| 改 | [gptase/tools/handlers.py](../../gptase/tools/handlers.py) | `DelegateTaskTool` 新增 `task_inputs` 结构化参数 + `_execute_deterministic` 分支 + `_try_parse_json_object` 辅助 |
| 改 | [gptase/main.py](../../gptase/main.py) | `gptase chat -p/-i/-o` 标志 + `_dump_chat_plan_artifacts` |
| 改 | [config/llm_config.template.json](../../config/llm_config.template.json) | 新增 `agent_models.orchestrator`：`temperature=0.1, stream=false, enable_thinking=false` |
| 加 | [tests/test_plan_prompt.py](../../tests/test_plan_prompt.py) | 8 用例 |
| 加 | [tests/test_agent_local_tools.py](../../tests/test_agent_local_tools.py) | 5 用例 |
| 加 | [tests/test_deterministic_delegate.py](../../tests/test_deterministic_delegate.py) | 8 用例 |

测试基线：**257 passing**（原 249 + 新增 8 个 deterministic delegate 测试；test_plan_prompt 与 test_agent_local_tools 已计入原 249）。

---

## 2. e2e 实测对比 (listov_2025 vs 金标准)

输入：[papers/markdowns/listov_2025_complete_computational_design_kemp/main.md](../../papers/markdowns/listov_2025_complete_computational_design_kemp/main.md)
基线：[papers/_gold_standard/listov_2025_complete_computational_design_kemp/result.json](../../papers/_gold_standard/listov_2025_complete_computational_design_kemp/result.json)

### 2.1 流程 timing

| 时间 | 事件 |
|---|---|
| 14:42:32 | gptase chat -p 启动 |
| 14:42:41 | Coordinator Turn 1 emit Step 1 DelegateTask（9s） |
| 14:44:43 | Step 1 worker (analyzer) success |
| 14:44:43–14:51:19 | Coordinator Turn 2 经历 3 次 SDK retry，6.5 min 才得到响应 |
| 14:51:19 | **6 parallel DelegateTask 在同一 assistant message 内 emit** |
| 14:51:24–14:53:28 | 6 workers 逐个完成（vision 先返回，extractor 后） |
| 14:55:01 | Coordinator emit Step 4 with **`task_inputs` 结构化字段** |
| 14:55:09 | Normalizer **7 秒返回**（deterministic shortcut 生效，零 LLM hop） |
| 14:55:09–14:59:07 | Coordinator Turn 4 又被 Doubao 断连一次，retry 后 emit Step 5 |
| 15:00:24 | Summary worker success |
| 15:01:08 | Final answer 落盘 |

**总耗时**：~18.5 分钟。其中 ~10 分钟是 Doubao API 抖动相关的等待。

### 2.2 数据覆盖度

| 指标 | 金标准 | 新流程 | 覆盖率 |
|---|---:|---:|---:|
| 唯一 variant_name | 52（50 real + 2 noise） | 28 | **54%** |
| 主要变体（Des27 / Des27.7 / Des27.10-13 / De61 / Des61 / Des49 / HG3.17 / R2.Des39 family） | 全部命中 | ✅ 命中 | 100% |
| Des27.7 衍生子变体（D162A、F113L、F113M 等） | 命中 | ❌ 缺失 | 0% |
| FuncLib / PROSS 派生命名 | 多版本 | 部分命中 | ~60% |

### 2.3 已知质量缺陷

#### A. SI 子目录未自动加载（覆盖率主要损失来源）

[gptase/main.py:198-205](../../gptase/main.py#L198) 的自动 SI 检测只识别 sibling `*_si.md`：
```python
candidate = doc_path.with_name(doc_path.stem + "_si" + doc_path.suffix)
if candidate.exists():
    si_path = str(candidate)
```

但 listov_2025 的 SI 在 `SI_41586_2025_9136_MOESM*/main.md` 子目录里。这导致：
- `si_document_path` 为空 → Step 3s 被 LLM 判定 SKIP
- normalizer 的 `_collect_html_table_rows` 跳过 SI 的 HTML 表
- 大量子变体（D162A、F113L 等记录在 SI Table S3 等）丢失

**legacy plan run 路径**对此有同样的问题，但部分 paper 通过 `paper_data.json` sidecar 或专门的预处理脚本绕过。这是数据预处理层的职责，与 Slice 1 重构正交。

#### B. 3 个 extractor replicas 高度趋同

观察：3 个 extractor 全部返回 Des27 作为第一个 variant，整体内容差异很小。原 plan_dispatcher 路径下 replicas 相对独立（每个 LLM 调用是独立 conversation）；新路径下 Coordinator 把 3 个并行调用任务描述写得**完全一致**，extractor LLM 在相同输入下倾向产生相似输出。

潜在缓解：
- prompt 模板里给每个 replica 加微小的随机化提示（"focus on tables 1-2" / "focus on tables 3-4"）
- 提高 extractor 自身的 temperature（已经是 0.1，可能太低）
- 不在 Slice 1 范围内，记入 Slice 5 或后续优化

#### C. Coordinator trace 不完整

`enzyme_extraction_pipeline_result.json` 的 `trace.runtime.coordinator.turns[]` 只记录了 4 个 worker（3 vision + 1 summary），缺失 analyzer、3 extractor、normalizer。

**根因**：[orchestrator.py:_execute_coordinator](../../gptase/core/orchestrator.py#L194) 多次调用 `self.run()`，每次返回独立 `coordinator_summary`。`_merge_coordinator_summaries` 应该累积所有 turns，但实测下来只保留了某几次的。需要进一步排查 `InteractiveSessionState` 在多次 `runtime.run()` 调用之间的状态传递。

**影响**：
- `worker_results/` 目录下只有 4 个文件，难以做精细 e2e 对比
- 用户面 final answer 内容**正确**（Coordinator LLM 在最后 turn 看到所有 message history）
- 不是阻塞性问题，但应在 Slice 3 删除 plan_dispatcher 之前修复，否则诊断能力会大幅下降

#### D. agent_working_memory 串台

观察：`enzyme-extraction-summary` 的 working_memory 写入了 "Zarifi 2025" 字样（来自上一次别的 paper 的会话），后续被注入到 user prompt 的 "Recent context"。虽然不影响最终 summary 内容（LLM 优先采用 current task），但有概率污染输出。

**潜在缓解**：在 chat -p 启动时清空相关 agent 的 working_memory；或改用 session-scoped memory 而非 agent-scoped。不在 Slice 1 范围内。

---

## 3. Slice 1 实施过程中暴露的预期外问题

### 3.1 DelegateTaskTool 从未连接 orchestrator（潜伏 bug）

[gptase/tools/handlers.py:359](../../gptase/tools/handlers.py#L359) `DelegateTaskTool.__init__(orchestrator=None)`，`register_default_tools` 直接 `registry.register(DelegateTaskTool())` — 整个仓库**没有任何代码**给 `delegate_tool.orchestrator` 赋值。

含义：旧 coordinator 路径**从未真正使用过 DelegateTask** —— 实际生产用的是 plan-handoff（`_evaluate_handoff` → 升级到 PlanManager）。Slice 1 改造让这条路径首次活跃，立即暴露了这个潜伏的依赖注入缺口。

修复：[orchestrator.py:75-83](../../gptase/core/orchestrator.py#L75)，在 `AgentOrchestrator.__init__` 末尾从 registry 取出 DelegateTask 实例并赋值。

### 3.2 Plan handoff 与新 Coordinator 路径冲突

[runtime.py:_evaluate_handoff](../../gptase/agents/runtime.py) 在每个 Coordinator turn 后跑一次 planner 子调用判断"是否升级到 plan"。即使新流程已经有 plan prompt，planner 仍可能误判为"needs_plan"，导致 PlanManager 接管运行（**实测出现过一次**：planner 生成了一个新 plan 然后 plan_dispatcher 重新启动整个流程）。

修复：新增 `DispatchRequest.disable_plan_handoff` 字段，chat -p 路径设为 True；orchestrator 据此跳过 `_evaluate_handoff`。

### 3.3 Doubao API 对 orchestrator 请求形态的特定脆弱性

新增的 Coordinator 请求形态（`stream=false + enable_thinking=true + tools=[DelegateTask] + 非空 tool history`）触发 Doubao 服务端长时间处理（>90s），openai SDK 的 keepalive 在 ~90s 后断开连接，触发 `RemoteProtocolError: Server disconnected without sending a response`。

旧 plan 路径下 orchestrator agent 用 `tools=[]` 总是 1 turn 直接返回，从未触发该形态。

**缓解**（已 land）：[config/llm_config.template.json](../../config/llm_config.template.json) 新增 `agent_models.orchestrator`：
```json
{
  "temperature": 0.1,
  "max_tokens": 8000,
  "stream": false,
  "enable_thinking": false
}
```

`enable_thinking=false` 让 Doubao 不生成长 reasoning，响应更快，更不容易被 keepalive 断。但仍未完全消除 retry 现象（每个 Coordinator turn 仍有 ~1/2 概率走 1-2 次 SDK retry）。

**真正的根治**：Slice 3 删除 `_evaluate_handoff` 之后，Coordinator 路径会更简单；可在 Slice 3 后再调研是否需要更激进的 retry/timeout 调整。

### 3.4 Fan-in 步骤 task_description 字符串化不可行

未做 deterministic shortcut 时，Coordinator 把 3 个 extractor 的 reactions 序列化成 28KB JSON 字符串塞进 normalizer worker 的 task_description。这条请求体（35KB）100% 触发 Doubao 断连，重试也救不回来。

设计文档第 11 节"风险登记"未列出此项 —— 是 Slice 1 实测才发现的关键风险。

**修复**（方向 2）：deterministic agent shortcut，把数据通过 `task_inputs: object` 结构化字段传，DelegateTask 直接调工具绕过 normalizer LLM。

---

## 4. 未达 plan run 基线的影响评估

### 4.1 推进 Slice 2 的可行性

**结论**：可以推进，但要带着已知缺陷意识。

- ✅ Slice 2 是文档/CLI 切换 + 历史 plan 删除，纯加法/重命名，不依赖 Slice 1 数据完美
- ✅ Slice 2 的 deprecation warning 让 plan run 路径继续可用，可作为 Slice 1 不足时的兜底

### 4.2 推进 Slice 3 的前置条件（**升级了**）

原文档列出的 Slice 3 前置：
> Slice 3 之后不可轻易回滚。Slice 1/2 必须充分验证多个 paper 后才能动 Slice 3。

实测之后追加的前置条件：

| 条件 | 阻塞 Slice 3? | 状态 |
|---|---|---|
| **修复 Coordinator trace 不完整（C）** | 是 | ✅ Slice 1.13 已修（executor truncation）|
| **解决 SI 子目录加载（A）** | 否，但强烈建议 | ✅ Slice 1.14 已修（detect_supplementary_path + --si）|
| **稳定 Doubao retry（D）** | 否，可接受 | 仅依赖 orchestrator 配置调优（已 land），更多优化推到 Slice 3 后 |
| **多 paper 端到端验证** | 是 | ⏳ 待办：跑 5+ 不同结构 paper，确认覆盖率不再普遍低于 plan run |

### 4.3 不影响 plan run 路径

Slice 1 完全是加法 + 配置调优。`gptase plan run` 路径**0 改动**，与 main 分支行为一致。生产数据不应回退。

---

## 5. Slice 2 之前的待办（来自本次复盘）

1. ~~**修复 trace 完整性**（缺陷 C）~~ — **Slice 1.13 已落地**。根因不在 `_merge_coordinator_summaries`，在 [tools/executor.py:160-165](../../gptase/tools/executor.py#L160) 的 `tool_results.content` 错误地用了 truncated 版本，导致大型 DelegateTask payload 经 `json.loads` 解析失败被静默丢弃。修复：trace 用完整原始输出，LLM-facing message 仍 truncate。新增 `test_tool_results_keep_full_content_when_message_is_truncated` 单测。
2. ~~**改进 SI 自动检测**（缺陷 A）~~ — **Slice 1.14 已落地**。新增 [plan_prompt.detect_supplementary_path()](../../gptase/agents/plan_prompt.py)：sibling `*_si.md` → 子目录 `SI*/` `MOESM*/` `supplementary*/` `_SI*/` 多种 pattern。listov_2025 现在正确解析到 `SI_41586_2025_9136_MOESM1_ESM/main.md`。新增 `--si <path>` CLI 显式覆盖。9 个新单测覆盖各 layout。
3. **多 paper 验证脚本**：写一个对比脚本，遍历 [papers/_gold_standard/](../../papers/_gold_standard/) 所有 paper，跑新旧两路径，对比 normalized_variants 数量、kinetics 完整度。**Slice 2/3 之间任务**（仍待办）。
4. **agent_working_memory 串台调研**（缺陷 D）：是否影响其他流程，是否需要在 chat -p 启动时清空。**优先级低**（仍待办）。
5. ~~**chat -p shutdown 卡住**~~ — **Slice 1.16 已修**。多 paper 验证暴露：每次 `gptase chat -p` 收尾 hangs 14+ 分钟才退出。诊断：`Model._provider_cache` 里的 `OpenAIProvider` 实例从未被关闭，`AsyncOpenAI` 客户端的 httpx 连接残留为 CLOSE_WAIT，asyncio loop 无法干净退出。修复：[providers.py](../../gptase/models/providers.py) 给 `OpenAIProvider` 加 `close()`（调用 `client.aclose()`）；[model.py](../../gptase/models/model.py) `Model.shutdown()` 遍历 `_provider_cache` 调 close 然后清缓存。新增 2 个 shutdown 单测。**legacy `gptase plan run` 没这个问题**是因为它的 orchestrator agent 从不调 LLM（plan 路径只让 worker 调），shutdown 时进程很快退出来不及暴露。新 chat -p 路径下 orchestrator 自己也调 LLM，每个 Coordinator turn 创建新 Model → 新 OpenAIProvider，都被 cache 住，过去 6 turns 累积 6+ 条泄漏连接。

---

## 6. 经验总结

1. **"代码完成"≠"e2e 通过"**：Slice 1 看起来 257 测试全绿就 OK 了，但 e2e 暴露了 4 个潜伏 bug（DelegateTask wiring、plan handoff 误升级、Doubao 请求形态脆弱性、fan-in payload）。**单测无法覆盖跨组件运行时交互**。
2. **依赖注入的诊断责任**：`DelegateTaskTool(orchestrator=None)` 默认值是隐式契约 —— 谁负责注入？仓库里没有人。这种"默认值是 None，要求外部赋值"的模式应该在框架层强制（如初始化时 assert 非 None）。
3. **LLM 不是万能的**：原 plan_dispatcher 的"领域硬编码"被 audit 文档批为反模式，但它**确实**绕过了一个真实的网络层瓶颈。新方案（deterministic frontmatter）是个好的折衷 —— 不污染通用框架，又保留了"跳过 LLM"的健壮性。
4. **配置即代码**：orchestrator 是新引入的"agent"，但因为它在代码里硬编码、不在 .claude/agents/ 下，调优只能通过 `agent_models.orchestrator` 配置入口。这种隐式的"代码 + 配置"边界对维护者不直观，未来重构可考虑把 orchestrator 也变成 .md 文件。

---

## 7. 文档历史

- 2026-05-08：初版，记录 Slice 1 实测结果与已知缺陷
- 2026-05-08（later）：Slice 1.13（trace 完整性）+ Slice 1.14（SI 子目录检测）落地，更新 §4.2 与 §5；测试基线 257 → 267
- 2026-05-08（even later）：Slice 1.16（shutdown 连接泄漏）落地，多 paper 验证开始；测试基线 267 → 269
