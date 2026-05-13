# GPTase 架构 Refactor 审计

**日期**：2026-05-07
**分支**：`data/pipeline`
**范围**：框架级复杂度审计，在任何 refactor 动手之前完成。
**方法**：只读 Explore agent 单次扫描，覆盖 Tier 1（orchestrator / planner / dispatcher / runtime）、Tier 2（type 文件）、Tier 3（models / tools / memory）。

本审计的目的是给后续的 refactor 提案提供**有具体引用的依据**。文中每一处主张都附带 `file:line`，未来回看时可以直接验证热点是否仍然存在。

---

## 1. 架构地图

CLAUDE.md 宣称的是一套干净的三模式 dispatch（Agent / Coordinator / Plan Manager）。代码里实际看到的是：

- **11 个 type 类**分散在 3 个文件中（`types.py`、`runtime_types.py`、`execution_types.py`）。
- **4 个重量级编排类**：
  - `orchestrator.py` — 1179 行
  - `plan_dispatcher.py` — 1152 行
  - `planner.py` — 870 行
  - `enzyme_variant_normalizer` — 940 行，仅被 `plan_dispatcher` 引用
- 领域专属的 enzyme 归一化逻辑被硬编码进**通用** task dispatcher。
- `orchestrator` 与 `planner` 之间存在显著职责重叠（session / checkpoint / 重试逻辑两边都写了一遍）。

净结果：当前的"分层"只存在于概念层面，调用方层面没有强制力。例如 `orchestrator.py:20-25` 同时跨越三个 type 文件 import，意味着这些边界对消费者**完全不可见**。

---

## 2. 复杂度 Top 5 热点

### 热点 1 — `gptase/core/orchestrator.py`（1179 行，24 方法）
- **病灶**：god-object | 职责重叠
- **证据**：
  - 三条 dispatch 路径（`_execute_agent`、`_execute_coordinator`、`_execute_plan`）与 session 持久化（DirectSession / SessionMessage / SessionTrace 创建 + 加载）和 plan-resume 逻辑共存。
  - 第 194–435 行包含 coordinator 事件循环、plan handoff 检测、worker 委派 —— 这部分逻辑**部分重复了** `TaskDispatcher` 的 dispatch 模式。
- **Refactor 杠杆**：把 session 持久化 + 恢复抽到独立的 `SessionManager`；把 coordinator 循环搬到 `runtime.py`，因为 plan-handoff 决策本来就在那里。

### 热点 2 — `gptase/agents/plan_dispatcher.py`（1152 行，26 方法）
- **病灶**：职责重叠 | 领域泄漏
- **证据**：
  - 第 21–22 行 import 了三个 enzyme 专属函数。
  - `_dispatch_enzyme_variant_normalizer`（第 610+ 行）把领域逻辑硬编码到通用 dispatcher；除此之外没有任何 dispatcher 路径会调用这个 940 行的 `enzyme_variant_normalizer` 模块。
- **Refactor 杠杆**：把 enzyme 归一化改造成后处理 hook（agent-agnostic 回调）。可消除约 90 行条件分支以及跨领域 import。

### 热点 3 — `gptase/agents/planner.py`（870 行，11 个 public 方法）
- **病灶**：职责重叠
- **证据**：
  - `planner.py:184-214` 的 checkpoint 恢复 / 创建逻辑与 `orchestrator.py:320-335` 相互镜像。
  - `FailureHandler` 在 `planner.py:116` 被实例化，但只在 `planner.py:389` 被调用一次。
  - `planner.py:338-431` 的重试循环重复了 orchestrator 的任务执行逻辑。
- **Refactor 杠杆**：把 checkpoint 管理收进 `ExecutionContext`；把重试 / 失败决策合并到 `TaskDispatcher` 的重试 wrapper 里。

### 热点 4 — 类型系统碎片化
- **病灶**：type-fragmentation
- **证据**：三个文件之间没有相互 import，但外部调用方却横跨三者：
  - `types.py` — Task、Plan、SessionMessage、SessionTrace、DirectSession（session 相关）
  - `runtime_types.py` — InteractiveRuntimeResult、InteractiveTurn、CoordinatorRuntimeSummary（运行时遥测）
  - `execution_types.py` — TaskExecutionResult、ExecutionContext、PlanCheckpoint（plan 执行状态）
  - `orchestrator.py:20-25` 与 `planner.py:22-25` 都跨越这三个边界 import。
- **Refactor 杠杆**：引入一个统一的 `SessionState` 顶层类，持有（messages、traces、execution_context）。把 `runtime_types` 和 `types` 中的 session 类合并进这个层级，调用方只需一次 import 即可拿到"这个 session 当前的全部状态"。

### 热点 5 — `gptase/agents/plan_failure_handler.py`（312 行）
- **病灶**：speculative-abstraction（投机式抽象）
- **证据**：
  - LLM 驱动的决策逻辑位于第 79–184 行；启发式 fallback 位于第 190–300 行。
  - 全代码库**只在一处实例化**（`planner.py:116`），**只从一条失败路径调用**（`planner.py:389`）。
  - 大多数生产环境失败在到达 LLM 分支之前就被尝试次数限制兜底了 —— 也就是说，LLM 分支在实际运行中**几乎没被走过**。
  - 看不到测试覆盖；其他 agent 或 workflow 也没有调用方。
- **Refactor 杠杆**：把启发式决策直接内联到 `planner._execute_single_task()` 里，做成一段小条件判断。除非 LLM 失败恢复是已经对外宣传的功能，否则砍掉 LLM 分支。

---

## 3. 类型系统判定

**不合理。**

三个文件确实命名了三个真实的领域（session 元数据、运行时遥测、plan 执行状态），但**没有任何调用方按这三个领域思考**。`orchestrator`、`web/server`、`planner` 都需要从三者中同时 import 才能完成有意义的工作 —— 这是教科书式的"分层泄漏"信号。

建议：把 `runtime_types` 和 `types` 中的 session 相关类合并进 `SessionState` 层级，`execution_types` 作为子对象暴露。这样可以减少 import sprawl，并把"我只是想拿到这个 session 当前的状态"这个高频用例变成一次 import。

---

## 4. 幽灵抽象清单 — 验证后状态（2026-05-07 更新）

原 Explore agent 审计标记了 5 个候选"幽灵抽象"。grep 验证后，只有 1 个确认是死代码，其余 4 个分别属于"误报"或"半死"。

| 符号 | 原审计判定 | 验证后状态 | 处理 |
|---|---|---|---|
| `GoalEvaluation`（`types.py:352-358`） | "只在 orchestrator 单点调用" | **误报** — `orchestrator.py` 5 处 + `tests/integration/test_orchestrator.py` 4 处使用；是 `_evaluate_goal_completion` 的核心返回类型。 | 保留。 |
| `DirectSession.metadata`（`types.py:371`） | "从未写入" | **半死** — orchestrator 任何路径都没有主动写入它，但 `DirectSession(**raw)`（`orchestrator.py:1039,1114`）会从外部 JSON 接收该字段；删除会改变序列化 schema。 | 暂缓 — 需要确认前端/存储是否依赖。 |
| `PlanCheckpoint.plan_hash`（`execution_types.py:231`） | "定义后从未读写" | **确认死** — 全代码库只有字段定义；零调用，构造时不传。 | **已删除（2026-05-07）**。 |
| `FailureHandler.max_retries`（`plan_failure_handler.py:77`） | "被 `Task.retry_count` 影子覆盖" | **半死** — 构造函数参数从未被传入（`planner.py:116` 用的是默认值）；但 `self.max_retries` 在 `FailureHandler` 内部确实被 5 处使用。 | **已由 Slice 4 处理（2026-05-07）** — 保留为构造参数（默认 `DEFAULT_MAX_RETRIES`）；`planner.py:116` 不再传 `model`。 |
| `InteractiveSessionState`（`runtime_types.py:126-136`） | "从不持久化或共享" | **误报** — `runtime.py` 内部 6 处使用，是活跃的 runtime 状态类型。 | 保留。 |

**对未来审计的教训**：Explore agent 报告通过"调用次数少"等信号标记候选项，这些信号是 hint 而非 fact。**动手前必须 grep 验证** —— 调用次数少 ≠ 死代码。

本轮实际删除的死代码面积：约 1 行（即上述字段）。识别出但留给 Slice 4 一并处理的：约 310 行（`FailureHandler` 若退役）。

---

## 5. 建议的 refactor 切片（按 ROI 排序）

每个 slice 都按"独立 PR 体量"设计。

### Slice 1 — 拆出 `session_types.py` 持久化模块（风险：低，已重新定标）

**前提修订（2026-05-07 grep 复核）**：原稿要把 `SessionMessage` / `SessionTrace` / `DirectSession` / `InteractiveSessionState` **合并**到统一的 `SessionState` 类树。grep 反驳了这个前提：
- `DirectSession` 系（`types.py:331-373`，含 `SessionType` / `DirectSessionStatus` / `SessionMessage` / `SessionTrace`）只在 `orchestrator.py` + `tests/test_session_split.py` 使用 —— 是 **SQLite 持久化** lifecycle。
- `InteractiveSessionState`（`runtime_types.py:126-135`）只在 `runtime.py` 内部 6 处使用，已干净继承自 `InteractiveRuntimeSnapshot` —— 是 **内存中 turn-by-turn** lifecycle。
- 两端**零交叉 import**；`planner.py` / `web/server.py` 根本不依赖这五个 Session 符号。共名 *Session* 是命名巧合。

合并 → 把"持久化"与"运行时控制"耦合进同一类树，blast radius 反而扩大。负 ROI。

**新范围（收敛而非合并）**：
- 把 `types.py:314-373` 的 5 个 session 持久化符号（`SessionType` / `DirectSessionStatus` / `SessionMessage` / `SessionTrace` / `DirectSession`）原地搬到新文件 `gptase/agents/session_types.py`。`types.py` 回归为 "agent definition + workflow"（`Task` / `Plan` / `AgentDefinition` / `AgentState` / `TaskStatus` / `GoalEvaluation`），从 373 行降到约 245 行。
- `orchestrator.py:20-23` 的 4 行 import 改为 `from gptase.agents.session_types import …`（一处变更，行数不增不减）。
- `runtime_types.py` / `runtime.py` 完全不动 —— 该领域已经自洽。

**删除**：0 行净代码（搬运）；但消除 `types.py` 中"agent 定义 / workflow / 持久化 session"三种语义的混淆，给 Slice 2 抽 `SessionManager` 提供干净的入口模块。

**为什么真低风险**：
- 调用面已 grep 验证 —— 仅 `orchestrator.py`（生产）+ `test_session_split.py:7-8`（测试）+ `types.py` 自身。
- 不改字段、不改方法签名，只改 import 路径；mypy / pytest 即可证伪。
- `tests/test_session_split.py` 是天然回归网。

**显式不在本切片范围**：
- 不合并 `InteractiveSessionState` —— 不同 lifecycle，强行合并是反模式。
- 不重构 `_save_direct_session` / `_load_direct_session` / `_result_to_session_traces` —— 留给 Slice 2 的 `SessionManager` 抽取。
- 不动 `DirectSession.metadata` 字段（参见第 4 节"半死"判定）。

### Slice 2 — 把 `SessionManager` 抽出 orchestrator（风险：中）
- **范围**：把 DirectSession 的 CRUD、加载 / 保存、恢复逻辑从 `orchestrator.py:920-1050` 抽出，新建 `SessionManager` 类。
- **删除**：`orchestrator` 减少约 130 行；澄清"dispatch 逻辑 vs 持久化"边界。
- **为什么中风险**：`SessionManager` 需要读取 agent 注册表才能干净地恢复 session，这个边界比较微妙。

### Slice 3 — 抽取 enzyme 归一化为后处理 adapter（风险：中）
- **范围**：把 `_dispatch_enzyme_variant_normalizer()` 和 enzyme 相关 import 从 `plan_dispatcher.py` 中抽出，新建 `EnzymeNormalizationAdapter`，wrap `TaskDispatcher`。
- **删除**：通用 dispatcher 减少约 90 行领域逻辑；940 行的 normalizer 模块降级为 plugin-only。
- **为什么中风险**：enzyme 步骤会变换中间任务结果，adapter 必须挂在 dispatch pipeline 的正确位置。
- **背景**：这块复杂度是在 `data/pipeline` 分支引入的 —— 趁记忆还热的时候纠正成本最低。

### Slice 4 — 内联或退役 `FailureHandler`（风险：低）— **已完成 2026-05-07**
- **实际选择的范围**：保留 `FailureHandler` 类骨架（`pm.failure_handler.decide` 是 `tests/test_planner.py:770` mock 的公开接口，必须保留），删除 LLM 投机分支（`_llm_decide`、`DECISION_PROMPT`），删除 `model` / `model_config` 构造字段，删除无调用方的 `should_skip_on_failure` 方法，并把 `planner.py:116` 改为 `FailureHandler()` 无 model 参数构造。
- **净删除**：441 行（vs 原估 311 行）。分布：`plan_failure_handler.py` 312 → 144（−168）；`tests/test_plan_failure_handler.py` 408 → 144（−264，删除 19 个 LLM/init/skip 测试，保留 14 个启发式测试）；`planner.py` 1 行构造调用更新。
- **为什么没有全退役**：`_classify_error` 承载真实产品行为（timeout / rate-limit → retry，unauthorized / not-found → abort），且 `pm.failure_handler.decide` 是 planner 集成测试 mock 的公开接口。全退役需要重写测试、且有行为漂移风险。真正的"投机"特指 LLM 分支 —— 启发式核心是 load-bearing 的。
- **验证**：14/14 focused failure-handler 测试通过；189/189 套件其余测试通过（绕过预先损坏的 `test_planner.py`）；inline smoke test 验证 `PlanManager() → pm.failure_handler.decide("connection timeout", …) → RETRY` 端到端可用。

### Slice 5 — 合并 `ExecutionContext` 与 `PlanCheckpoint`（风险：高）
- **范围**：合并成一个 `ExecutionState` 类；调和重叠字段（`plan_id`、`session_id`、`task_results`、`workspace_dir`、`variables`）。
- **删除**：`execution_types.py:153-211` 的 checkpoint 序列化样板；澄清 plan resume 语义。
- **为什么高风险**：会触碰 `planner.py:184-227`（resume 逻辑）和 `web/server.py` 的持久化 API —— 后者是框架对外暴露的表面。
- **建议**：等 Slices 1–4 落地后再考虑。

---

## 6. 建议的执行顺序

1. ~~**先做 Slice 4**~~ — **已完成 2026-05-07**（净 −441 行，含测试瘦身；选择了"保留启发式核心、砍 LLM 分支"的稳健路径，未全退役）。
2. **再做 Slice 1** —— 建立 Slice 2 即将依赖的类型词汇。
3. **接着 Slice 2** —— `orchestrator.py` 可读性收益最大的一刀。
4. **然后 Slice 3** —— 趁早纠正 `data/pipeline` 分支留下的 dispatcher 不洁问题。
5. **最后 Slice 5** —— 只有当前三个 slice 落地后仍觉得复杂才动手。

---

## 未来重审时的注意事项

- 本文档基于一次 Explore-agent 单轮扫描；**所有行号会随代码演化而漂移**。动手前请重新 grep 验证。
- 如果 Slices 1–4 完成后框架仍显沉重，下一层应当审 `web/server.py` 的持久化表面（本次 Tier 3 未深入）。
- **类型系统碎片化是观察到的最高杠杆点**；即使 Slice 1 看起来"只是改名"，也不要跳过。
