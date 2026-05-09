# Coordinator-Only Refactor 整体复盘（Slice 1-5）

**日期**：2026-05-08
**前置文档**：
- 计划：[coordinator_only_refactor_2026-05-08_zh.md](coordinator_only_refactor_2026-05-08_zh.md)
- Slice 1 详细复盘：[coordinator_only_refactor_slice1_retrospective_2026-05-08_zh.md](coordinator_only_refactor_slice1_retrospective_2026-05-08_zh.md)

**状态**：5 个 Slice 全部 land。本文不重复 Slice 1 retro 已记载的 4 个潜伏 bug（DelegateTask wiring、plan handoff 冲突、Doubao 请求脆弱性、fan-in payload），聚焦 Slice 2-5 的实测教训与跨切片模式。

---

## 1. 整体落地节奏

| Slice | Commit | 净 LoC | 实施特点 |
|---|---|---:|---|
| 1（核心机制）| 多 commit 累积至 1.19 | 加法为主 | 引入 DelegateTask + plan_prompt + deterministic agent + artifact comms |
| 2（CLI 收敛）| 历史 commits | 中性 | `gptase chat -p` 加 deprecation warning（**未做** alias，保留 54% 覆盖率信号） |
| 3（PlanManager 删除）| `4c22fc7` + `fd21791` | -6,700 | 删 6 个文件 + 1663 行 test_planner |
| 4（Web 清理）| `23129bb` `45d85a0` `520c0bd` `77014f5` | -2,400 | 后端 + 前端两段提交（git pathspec 坑） |
| 5（文档收尾）| `6b5687a` `ad4f6bf` | -1,300 | 删 4 docs + 重写 16 docs + YAML schema 迁移 |
| /simplify | `7987dff` | -1 净 | 6 个质量修复（含 polling closure-staleness 隐藏 bug） |
| **总计** | — | **-10,400 LoC** | 5 个 worktree 跑了 1 个工作日 |

测试基线：`249 → 295（Slice 1 高峰）→ 189（Slice 3 删测后）→ 179（Slice 4 删 web tests 后稳定）`

---

## 2. Slice 2 — 实测中性，但暴露一个旧 bug

**目标**：CLI 入口收敛到 `gptase chat -p`，旧 `gptase plan run` 加 deprecation warning。

**意外**：deprecation warning 触发 `format_plan_list` 时报 `KeyError: 'version'` — 一个 main 分支就存在的潜伏 bug，YAML 没声明 `version` 字段就崩。这是经典的 "新警告路径暴露旧错误处理" 模式。

**修复**：`if plan.get("version"):` 条件守护。一行修复，但属于 Slice 2 不应承担的 scope（main 分支早就该处理）。

**教训**：deprecation/警告路径默认应该走"宽松解析" — 它们不是热路径，错失字段不该让用户看错误堆栈。

---

## 3. Slice 1.18 — 计划外但成为整个重构的关键

**情境**：Slice 1 land 后，listov_2025 e2e 跑通但 Coordinator 上下文爆到 122KB（vs Slice 1 baseline 9.8KB）。

**用户原话**："worker 和 coordinator 通信时候这些不要塞进 context, 把文件路径告诉 coordinator 就好了吧"。

**根因**：`_build_coordinator_followup_prompt` 把 `coordinator_turns[].worker_results[].content` JSON 序列化全部塞回下一轮 prompt。Slice 1.13 修 trace 完整性时把 truncated content 改成 full content，反而让这条路径放大了 12 倍。

**修复（Slice 1.18）**：
- worker 结果写入 `<workspace>/worker_results/NNN_<agent>.json`
- DelegateTask 返回紧凑引用 `{output_path, content_chars, content_preview}`
- 下游 step 通过 path 字符串引用上游产物
- Deterministic agent 通过 `_resolve_path_inputs` 自动 `Read` 路径并 `parse JSON`

**影响**：
- listov 122KB → 9.8KB outer prompt（-92%）
- Slice 3 删除 PlanManager 后整个架构终于可行（旧路径 inline content 在 7+ workers 时根本跑不动）
- 但**埋下一个隐藏契约**：LLM-driven 下游 worker 必须有 `Read` 工具才能读取 path（见 §5）

**教训**：**计划文档预测不到所有性能问题**。原计划假设 LLM 通过 message history 自然看到上游输出 — 但 Coordinator 多 turn 迭代时 message history 会被序列化重发，inline content 在 fan-out 场景指数膨胀。

---

## 4. Slice 1.19 — 一个被忽略的 outer-loop bug

**问题**：实测 LLM 在某 turn 既调用 `DelegateTask` 又写 final answer 时，外层循环看到"有 delegation"就再发一轮 followup prompt（多花一次 LLM 调用，浪费 ~10 KB token）。

**修复**：`_execute_coordinator` 信任 `stop_reason == "final_answer"` 作为终止信号，即使本 turn 有 delegation 也直接返回。

**测试**：新增 `test_auto_intake_returns_immediately_on_final_answer_with_delegations`。

**教训**：**外层循环的退出条件应该跟随 LLM 的 stop_reason，而不是基于"是否有 delegation"启发式判断**。LLM 已经写了 final answer 就是它认为完成了。

---

## 5. Slice 3 后置缺陷 — `enzyme-extraction-summary` Read-tool 缺口

**情境**：Slice 3 删完 PlanManager，listov 重跑 92% recall（vs gold），但 `010_enzyme-extraction-summary.json` 的 `summary_report` 写："Quantitative analysis could not be completed... only file paths to source data were referenced."

**根因**：Slice 1.18 引入的 artifact-mode 让上游 `task_inputs` 是路径列表。两类下游 worker 行为不一样：

| Worker 类型 | 收到的 | 自动解析路径？|
|---|---|---|
| `deterministic: true`（如 normalizer）| `task_inputs` kwargs | ✅ DelegateTool `_resolve_path_inputs` 自动 Read |
| LLM-driven（如 summary）| 提示文本 | ❌ 除非 agent 有 `Read` 工具 |

旧 `PlanTaskDispatcher`（Slice 3 已删）通过 `{{stepN.field}}` 模板展开 inline 数据 — 这条契约随 PlanManager 一起消失，但 summary agent 的 frontmatter 还在依赖它。frontmatter 注释甚至预言了未来："`If a fallback read is ever required, add Read here.`"

**修复（commit `fd21791`）**：
- summary agent 加 `tools: Read`
- Workflow §1 改写："如果 task_inputs 字段是 `*.json` 路径，先用 Read 加载"

**验证**：listov 重跑 → summary 充分填充（5 top performers + 4 quality flags），broom 也充分填充（HG3→HG4 705x improvement）。

**教训（关键）**：**架构变更必须扫描所有下游消费者的隐式契约**。Slice 1.18 把"inline data"换成"path string"是合理的优化，但只验证了 deterministic worker 的行为；LLM-driven worker 安静地降级了一周才被发现。审计 checklist 应该包括："对于每个 LLM-driven worker，它读取上游数据的方式是什么？变更后该方式还成立吗？"

### 5b. broom_2020 调查 — 同型缺陷的第二实例（commit `4fe81c5`）

后续追查 broom_2020 33% recall 时发现两个 stacked bug 都属于这个 pattern：

**Bug A（已修）**：`document-structure-analyzer` 把 `![Table 1](images/...jpg)` 误标为 `figure_id: "Figure 1", is_table_image: 不存在`。analyzer 提示没要求读 markdown alt text，只是按顺序自动编号。修复：明确要求"alt text 即权威，verbatim 取用"+ 新增 `is_table_image: bool` 字段。验证：postfix 跑出 `figure_id: "Table 1", is_table_image: true`。**HG3.17（gold 标杆变体）从完全缺失变为成功提取**。

**Bug B（仅部分修复）**：vision-image-analyzer 提示要求"Images are already embedded in this conversation"，但 Coordinator 的 DelegateTask 只把 `images: <path>` 写进 task_description 文本 — 框架层从未把图片字节嵌入到 worker 的消息里。这条契约也是从 PlanTaskDispatcher 删除时一起消失的。

我修了 `plan_prompt._render_step` 让它把 `images` 输入渲染到 DelegateTask 的 `image_paths=` 参数槽，并加内联注释提示 Coordinator。但实测**仍未起效**：Coordinator agent 只有 `DelegateTask` 工具，**没有 Read**，无法读取上游 analyzer 完整输出 (`001_*.json`) 来提取 `images[]` 数组里的具体路径。它收到的 followup prompt 只有 `content_preview`（前 1500 字符），prompt 中的 `<{{step1.images}}>` 占位符无法在 Coordinator 里解析为真实路径列表。

**真正的修复需要框架层工作**（出本批次范围）：
- 选项 A：给 Coordinator agent 加 `Read` 工具，prompt 显式指示"读 step 1 的 artifact，提取 images 数组，转为绝对路径，传 image_paths"
- 选项 B：DelegateTask 模仿 deterministic agent 的 path 解析 — 检测 vision agent + `task_inputs.images` 是路径 → 自动 Read 上游 artifact + 提取 image_paths → 喂给 Task
- 选项 C：新增 `is_vision_agent: true` frontmatter，作为 deterministic 的对偶 — DelegateTask 见到此标志就特殊处理图像输入

**当前状态**：broom_2020 unique = 3（HG3, HG3.17, HG4），相比修复前的 (HG2, HG3, HG4) 是**质量提升**（HG3.17 是论文 headline）但**数量不变**。其余 3 个进化中间体（HG3.3b, HG3.7, HG3.14）只在 Table 1 图片中可见，需要 Bug B 的真正修复才能拿到。

**这是 Slice 1.18 隐式契约缺陷的第二实例**：Read-tool 缺口（summary worker）和 image embedding 缺口（vision worker）是同一类 pattern — legacy PlanTaskDispatcher 帮 LLM-driven worker 做了"组装上下文"的工作，新路径让 Coordinator 通过 prompt 指令做，但 Coordinator 没有 Read 工具就组装不了。

---

## 6. Slice 4 — git pathspec 模式三连击

**情境**：Slice 3、4、5 每次都遇到同一个提交时的 pattern：

```bash
git rm <file>          # stage 删除
# 编辑其他文件
git add <new-files> <deleted-file>   # FAILS: 'fatal: pathspec ... did not match'
```

git 一遇到不存在的 pathspec 整条 `git add` 就退出非零，且 pre-commit hooks 的 stash-rollback 把未 stage 的修改也回滚 — 结果只有最初 `git rm` 的文件进了 commit，所有手工 edit 都没进。需要 follow-up commit 补救。

每次都是双 commit：

| Slice | 删除 commit | 修改 commit |
|---|---|---|
| 4 backend | `23129bb` | `45d85a0` |
| 4 frontend | `520c0bd` | `77014f5` |
| 5 docs | `6b5687a` | `ad4f6bf` |

**修复模式**（已验证）：
```bash
git rm <files>           # commit-1: 仅删除
git commit -m "delete X"
# 接着编辑其他文件
git add -u && git add <new>   # commit-2: 修改
git commit -m "rewrite Y after X removal"
```

或一次到位：`git add` 时 **不要** 把已 `git rm` 的路径再列出来。

**教训**：git 的 `add` 不是事务性的 — 一个 pathspec 失败就让整条命令异常退出，已成功的项也不会自动 commit。这种行为在 IDE 里被掩盖（IDE 是逐个文件 add），但 CLI 批量 add 必须警惕。

---

## 7. Slice 5 — 文档清扫的范围真相

**计划文档预估**：+100 / -300 LoC，0.5 个工作日。

**实际**：+408 / -1,287 LoC，~1.5 小时。

**多出的工作量来源**：
1. **`api/plan.md` + `internals/dispatcher.md` 整删**（zh + en 共 4 文件）— 计划没写删除，只说"清理 plan 引用"，但描述已删除模块的 422 + 140 行 docs 留着没意义
2. **`api/web.md` 重写**（zh + en 共 ~500 行）— 计划没意识到这两个文件 80% 在描述已删端点
3. **`internals/execution-flow.md` 重写**（zh + en）— 老文件描述 PlanManager DAG 流程，必须重写
4. **plan-mode 在 4 个前端组件渗透**（types.ts、App.tsx、MainWorkspace、SessionList）— 计划只点了 App.tsx 和 PlanWorkspaceExplorer

**教训**：**架构变更的文档影响是树状传染** — 删一个核心组件（PlanManager），其文档级影响是 N+1 个文件，因为：
- 直接描述它的 docs 要删
- 间接引用它的 docs 要改
- 索引/导航 docs 要重排
- 多语言镜像翻倍

预算 LoC 时应按"代码删除 LoC × 1.5"估文档工作量，而不是按"docs/ 目录现有 plan 引用数"估（后者只覆盖了显式引用）。

---

## 8. /simplify 暴露的隐藏 perf bug

**情境**：Slice 5 后跑 `/simplify`，三个 reviewer agent 并发审查，发现 App.tsx 的 polling 模式：

```tsx
useEffect(() => {
  const timer = setInterval(refreshSessionSummaries, 10000);
  return () => clearInterval(timer);
}, [currentSessionId]);  // ← BUG
```

**问题**：deps 含 `currentSessionId` → 每次切 session timer 被 teardown 重建。用户活跃切换时（每 5 秒切一次），轮询永远跑不到第 10 秒。后台数据从此"看起来"在更新，实则一次都没刷。

**修复**：deps 改 `[]` + `refreshSessionSummaries` 用 functional setState 拿最新 `currentSessionId`。

**附带**：`mergeSessions` 每 tick 返回新数组（即使 zero-diff）→ React 全局重渲染。加 same-reference 短路。

**教训**：**`useEffect` deps 数组是性能契约，不只是依赖跟踪**。把 state 放进 polling/subscription effect 的 deps 是常见 closure-staleness 误解 — 正确做法是 deps 用 `[]` + 用 functional setter 拿最新值。这种 bug 在用户层永远不会报，因为"它看起来在工作"。需要专门工具（`/simplify` 这类 efficiency reviewer）才会发现。

---

## 9. 关键指标演化曲线

### 9.1 listov_2025 recall（gold = 52 unique variants）

| 阶段 | unique | recall | 备注 |
|---|---:|---:|---|
| 旧 plan run（main 基线）| 44 | 85% | 走 PlanTaskDispatcher inline 路径 |
| Slice 1 首次 e2e | 28 | 54% | SI 子目录未加载（缺陷 A）|
| Slice 1.13 + 1.14 | ~40 | ~77% | trace + SI 修复 |
| Slice 1.18（artifact comms）| 48 | 92% | 关键转折 |
| Slice 3（PlanManager 删）| 48 | 92% | 重构无回归 |
| Slice 3 + Read-tool 修 | 45 | 87% | summary 也充分填充（重要质变）|

**注**：recall 数字本身在 LLM 提取器的 ±3-5 variant 方差范围内；真正的胜利是 summary 从"无统计"变成"5 top performers + 4 quality flags"。

### 9.2 broom_2020 仍 33%（独立瓶颈）

3 个 extractor replicas 全部只识别到 `HG3` + `HG4`（identical 2 个）。这与 Coordinator-only 重构无关，是 `enzyme-kinetics-extractor` 对 Table 1 多行 markdown 表的覆盖弱点。**不在本重构 scope，需独立 follow-up**。

### 9.3 上下文规模（Coordinator user prompt）

| 阶段 | 单轮 prompt | 累计变化 |
|---|---:|---|
| Slice 1 baseline | 9.8KB | — |
| Slice 1.13（full content）| 122KB | **+1144%** |
| Slice 1.18（artifact comms）| 9.8KB | -92%（回到健康线）|
| Slice 3 后 final turn | 23KB | 1.7KB/turn 线性增长（path strings + envelope）|

---

## 10. 5 个跨切片教训（汇总）

1. **架构契约是隐式的** — Slice 1.18 把通信从 inline 改成 path 解决了一个性能问题，但破坏了 LLM-driven worker 的 "PlanTaskDispatcher 给我 inline 数据" 假设，且只在 Slice 3 跑实测时才暴露。**审计 checklist 必须包括所有下游消费者**。

2. **预测不到的性能问题** — 原计划假设 message history 自然传递上下文。实测发现 Coordinator 多 turn 迭代会指数级膨胀。Slice 1.18 是事后补的，不是 plan 文档预测的。**性能假设要在第一次 multi-turn e2e 时验证，不要等 Slice 3+**。

3. **删除 ≠ 收尾** — 每次"删 X"都伴随 "重写描述 X 的文档" + "审计 X 的隐式消费者"。Slice 5 文档预算翻 5 倍证实这一点。

4. **git CLI 不是事务性的** — `git rm` + `git add <被删的>` 让整条命令失败，pre-commit stash-rollback 把所有修改回滚。这次重构 3 次踩同一个坑。**修复模式**：删除单独 commit，修改单独 commit，不混着 add。

5. **e2e 是唯一的真理** — Slice 1 看起来 257 测试全绿，但 e2e 暴露 4 个 bug；Slice 3 看起来 179 全绿 + listov 92%，但 summary 静默降级；`/simplify` 看起来 build 通过，但 polling timer 永远 reset。**单测无法覆盖跨组件运行时交互；e2e 也不是终点（要看产物质量、上下文规模、shutdown 行为等多维度）**。

---

## 11. 待办（重构外）

| 项 | 优先级 | 备注 |
|---|---|---|
| broom_2020 提取器 multi-row table 覆盖 | 中 | 独立工作，与 Coordinator-only 正交 |
| `agent_working_memory` 串台调研（Slice 1 retro 缺陷 D）| 低 | 暂未观察到实际污染最终输出 |
| `memoryCacheRef` LRU eviction | 低 | 长会话内存（未观察到实际问题，跳过）|
| Web UI 复活 plan 入口（可选）| 低 | 需要把 plan_prompt 展开后转 chat WebSocket |
| 多 paper 大规模验证脚本 | 中 | 跑 5+ 不同结构 paper，对比 plan run 与 chat -p 覆盖率 |

---

## 12. 文档历史

- 2026-05-08：初版，整合 Slice 2-5 经验，引用 Slice 1 retro
