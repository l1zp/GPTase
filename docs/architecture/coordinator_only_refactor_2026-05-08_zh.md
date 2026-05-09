# GPTase 简化为 Coordinator-Only 架构

**日期**：2026-05-08
**分支**：`data/pipeline`
**前置文档**：[refactor_audit_2026-05-07_zh.md](refactor_audit_2026-05-07_zh.md)
**关系**：比 audit 文档的 Slice 序列**更激进**——覆盖原 Slice 2/3/5 的部分目标，并新增"Coordinator 化"作为根本简化方向。原 audit 的 Slice 1（types-split）与本次方案不冲突，可独立先做或合并进 Slice 3。

**Slice 1 已落地**：见 [coordinator_only_refactor_slice1_retrospective_2026-05-08_zh.md](coordinator_only_refactor_slice1_retrospective_2026-05-08_zh.md) — 记录实际改动、e2e 实测覆盖率（28/52 variants，~54%）、4 个潜伏 bug 与已知缺陷。**推进 Slice 3 前必读**。

---

## 1. 背景与动机

### 1.1 现状

CLAUDE.md 宣称的是干净的三模式 dispatch（Agent / Coordinator / Plan Manager）。审计 grep 后实际看到：

- **Plan 子系统生产代码 2,409 行**：[planner.py](../../gptase/agents/planner.py) 870 + [plan_dispatcher.py](../../gptase/agents/plan_dispatcher.py) 1152 + [plan_loader.py](../../gptase/agents/plan_loader.py) 243 + [plan_failure_handler.py](../../gptase/agents/plan_failure_handler.py) 144。
- **Plan 测试 1,807 行**：[test_planner.py](../../tests/test_planner.py) 1663 + [test_plan_failure_handler.py](../../tests/test_plan_failure_handler.py) 144。
- **Web UI plan 组件 767 行**：[PlanWorkspaceExplorer.tsx](../../ui/src/components/PlanWorkspaceExplorer.tsx) 711 + [PlanReview.tsx](../../ui/src/components/PlanReview.tsx) 56。
- **职责重叠**：[orchestrator.py:435-567](../../gptase/core/orchestrator.py#L435) 的 `_execute_plan` 与 [orchestrator.py:194-262](../../gptase/core/orchestrator.py#L194) 的 `_execute_coordinator` 大量逻辑相互镜像（session 持久化、checkpoint、重试）。
- **领域逻辑泄漏**：[enzyme_variant_normalizer.py](../../gptase/agents/enzyme_variant_normalizer.py)（940 行纯函数）通过 [plan_dispatcher.py](../../gptase/agents/plan_dispatcher.py) 的特例分支硬接到通用 dispatcher——这是审计文档第 2.2 节标记的反模式。

**实际在用的 Plan 只有 1 个**：[enzyme_extraction_pipeline.yaml](../../config/plans/enzyme_extraction_pipeline.yaml)（98 行）。另一份 [enzyme_design_pipeline.yaml](../../config/plans/enzyme_design_pipeline.yaml)（89 行）是历史遗留，未发现任何真实调用方。

### 1.2 用户的设计意图（已拍板的边界）

1. **保留"按 plan 顺序调用 agent"的确定性**：删 PlanManager 不等于让 LLM 完全自由调度。Coordinator 收到任务后应**按预设的 todo 序列**调用 subagent，而不是 3 轮自由发挥。
2. **YAML 退化为 Coordinator prompt 模板**：保留 [config/plans/*.yaml](../../config/plans/) 文件，但解释器换成"启动时把 YAML 拼成 prompt 给 Coordinator"。`gptase plan run` CLI 改造为"带预设 prompt 的 chat"。
3. **Web UI 一起删**：plan 相关前端组件全删，UI 简化为只有 chat。
4. **执行路径保持现状**：仍用 GPTase 自定义 LLM 路径 + tool calling，**不切到 Claude SDK 原生 Agent tool**。这保留了对非 Claude 模型（DeepSeek / Doubao 等）的支持。
5. **领域工具不污染通用框架**：enzyme 专属工具放进 agent 目录内（agent-local），通用 [gptase/tools/](../../gptase/tools/) 包零改动。

### 1.3 预期结果

- 全框架只剩 **Agent / Coordinator** 两种执行模式
- 净删 ~5,500 行（生产 + 测试 + UI + 文档）
- enzyme_extraction 业务能力（3 副本 + fan-in 归一化）通过 prompt 显式约束保留
- 通用工具系统（[gptase/tools/](../../gptase/tools/)）零改动——`git diff gptase/tools/` 应为空

---

## 2. 设计原则

按用户 CLAUDE.md 的三条不可违背原则：

| 原则 | 在本次重构的体现 |
|---|---|
| 简洁优先 | 删 5,500 行，留 ~290 行（Slice 1 加法）；只剩 Agent / Coordinator 两种模式 |
| 根因导向 | 不绕开 enzyme_variant_normalizer 的领域泄漏问题——直接把它兑现为 agent-local 真 worker |
| 最小影响 | 通用 tools 包零改动；CLI 入口仅微调；session DB schema 不变 |

外加两条本次特定原则：

| 原则 | 解释 |
|---|---|
| **关注点分离** | enzyme 概念全部 contain 在 enzyme 相关目录；通用框架（tools/、agents/base.py）不感知任何领域关键字 |
| **Prompt 显式约束代替代码强制约束** | DAG 顺序、replicate fan-out、optional skip 不再由 plan_dispatcher 强制保证，改由 Coordinator 主 Agent 解读 prompt 中"Step 1 → Step 2 → ..."的指令实现 |

---

## 3. 架构对比

### 3.1 Before（当前）

```
Input
  └─> dispatch (orchestrator.py:105-131)
        ├─> Agent (request.agent_id)
        │      └─> Agent.process_task → AgentRuntime
        │
        ├─> Coordinator (default)
        │      └─> _execute_coordinator (3 轮 LLM 决策循环)
        │             ├─> AgentRuntime (orchestrator agent)
        │             ├─> DelegateTask tool (调用 worker subagent)
        │             ├─> _evaluate_handoff() ── 检测 needs_plan
        │             │   └─> 跳到 Plan 路径 ↓
        │             └─> 合并 worker results 进入下一 turn
        │
        └─> Plan Manager (request.plan_id / plan_path)
               └─> _execute_plan
                      ├─> PlanLoader (YAML → DAG)
                      ├─> PlanManager.execute_plan
                      │      ├─> get_next_tasks (DAG 调度)
                      │      ├─> TaskDispatcher.dispatch (单任务)
                      │      ├─> TaskDispatcher.dispatch_parallel (并行 fan-out)
                      │      ├─> _resolve_inputs ({{stepN.field}} 模板解析)
                      │      ├─> _dispatch_enzyme_variant_normalizer (领域特例)
                      │      └─> FailureHandler (重试决策)
                      └─> PlanCheckpoint (DB 持久化、resume)
```

### 3.2 After

```
Input
  └─> dispatch
        ├─> Agent (request.agent_id)
        │      └─> Agent.process_task → AgentRuntime
        │
        └─> Coordinator (default + optional -p plan_id)
               └─> _execute_coordinator (10 轮 LLM 决策循环)
                      ├─> [可选] plan_prompt.expand_plan_to_prompt(plan_id)
                      │     注入 "按 N 步顺序执行" 的结构化 prompt
                      ├─> AgentRuntime (orchestrator agent)
                      ├─> DelegateTask tool (调用 worker subagent)
                      └─> 合并 worker results 进入下一 turn
```

**消失的分支**：Plan Manager、handoff 检测、TaskDispatcher、PlanLoader、FailureHandler、PlanCheckpoint。

**新增的最小机制**：[gptase/agents/plan_prompt.py](../../gptase/agents/plan_prompt.py)（YAML→prompt 扩展器，~150 行）+ [Agent.from_markdown](../../gptase/agents/base.py) 自动发现 agent-local `tools.py` 的扩展（~30 行）。

---

## 4. 推荐方案：Prompt-only Coordinator

### 4.1 核心机制（复用已有基础设施）

| 机制 | 现有位置 | 用法 |
|---|---|---|
| Coordinator → Worker 调用 | [DelegateTaskTool](../../gptase/tools/handlers.py#L353) | LLM emit `DelegateTask(agent_id=..., task_description=...)`；orchestrator 调用 [Agent.process_task](../../gptase/agents/base.py) |
| 单 turn 内并发调用 | [ToolExecutor.execute_calls](../../gptase/agents/runtime.py#L161) | LLM 在同一 assistant message 中 emit N 个 tool calls，executor 用 asyncio.gather 并行执行 |
| Worker discovery | `Agent.discover_agents` (orchestrator 启动时) | `.claude/agents/<name>/<name>.md` 自动注册 |
| Session 持久化 | [DirectSession](../../gptase/agents/types.py)（chat/agent 前缀）+ [_continue_direct_session](../../gptase/core/orchestrator.py#L161) | session_id 透传，DB 自动写入 |
| 工具权限隔离 | [ToolRegistry.allowed_agents](../../gptase/tools/base.py#L120-L135) | 当前未使用，本次激活 |

### 4.2 新增 plan_prompt 扩展器

[gptase/agents/plan_prompt.py](../../gptase/agents/plan_prompt.py)（~150 LoC），公开 API：

```python
def expand_plan_to_prompt(
    plan_id: str,
    document_path: Optional[str] = None,
    si_document_path: Optional[str] = None,
    workspace_dir: Optional[str] = None,
    **extra_vars: str,
) -> str:
    """加载 YAML，将其展开为给 Coordinator 主 Agent 的结构化 prompt。

    职责：
      - 读取 config/plans/<plan_id>.yaml
      - 替换 {{document_path}} / {{si_document_path}} 等启动参数
      - 把每个 step 渲染为 "Step <id> — DelegateTask(...)" 文本
      - 处理 replicate: 3 → "Issue EXACTLY 3 parallel DelegateTask calls"
      - 处理 optional: true → "If <condition>, skip; otherwise..."
      - 归一化 agent_id 为 dash 形式（agent_id 在 .claude/agents/ 下都是 dash）

    不做：
      - 不解析 {{stepN.field}}（中间步骤数据流由 LLM 自然 thread）
      - 不执行 plan（只生成 prompt）
      - 不连接数据库或 session
    """
```

**为什么不解析 `{{stepN.field}}`**：当前 plan_dispatcher 用模板解析把上游结果注入下游输入。新架构下，LLM 在多 turn 间通过 message history 自然看到上游 worker 的输出，下一个 DelegateTask 的 `task_description` 直接由 LLM 拼出来。这是 LLM 主导编排的核心——若强行解析模板，等于把 PlanManager 复活了。

### 4.3 enzyme-variant-normalizer 兑现为真正 Worker（关键前置）

[现有 .md](../../.claude/agents/enzyme-variant-normalizer/enzyme-variant-normalizer.md) 仅是 discovery 标记，正文写着 "executed deterministically by the Python dispatcher"。**实际执行路径**是 plan_dispatcher 的特例分支绕过 LLM 直接调 Python 模块。删 plan_dispatcher 后这条路径断裂。

#### 4.3.1 落地位置（agent self-contained）

```
.claude/agents/enzyme-variant-normalizer/
  enzyme-variant-normalizer.md     # frontmatter 添加 tools: NormalizeEnzymeVariants
  tools.py                         # 新增 ~50 行：NormalizeEnzymeVariantsTool(BaseTool)
  evals/                           # 已存在
```

#### 4.3.2 NormalizeEnzymeVariantsTool 草稿

```python
# .claude/agents/enzyme-variant-normalizer/tools.py
"""Agent-local tool for enzyme-variant-normalizer.

Wraps deterministic functions in gptase/agents/enzyme_variant_normalizer.py
so the LLM-driven agent can call them via DelegateTask → tool call chain.
"""
import json
from typing import Any, Dict, List, Optional

from gptase.tools.base import BaseTool
from gptase.agents.enzyme_variant_normalizer import normalize_variant_payload


_SCHEMA = {
    "type": "object",
    "properties": {
        "text_extraction_data": {
            "type": "array",
            "description": "List of replica payloads from enzyme-kinetics-extractor",
        },
        "vision_extraction_data": {
            "type": "array",
            "description": "List of replica payloads from vision-image-analyzer (extracted_tables field)",
        },
        "si_extraction_data": {
            "type": "object",
            "description": "Optional supplementary-information extraction payload",
        },
        "document_path": {"type": "string"},
    },
    "required": ["text_extraction_data", "vision_extraction_data", "document_path"],
}


class NormalizeEnzymeVariantsTool(BaseTool):
    name = "NormalizeEnzymeVariants"
    description = (
        "Reconcile replicated enzyme extraction results into deduplicated, "
        "canonically named variant records with merged kinetics."
    )

    def get_schema(self) -> Dict[str, Any]:
        return _SCHEMA

    async def execute(
        self,
        text_extraction_data: List[Dict[str, Any]],
        vision_extraction_data: List[Dict[str, Any]],
        document_path: str,
        si_extraction_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        result = normalize_variant_payload(
            text_extraction_data=text_extraction_data,
            vision_extraction_data=vision_extraction_data,
            si_extraction_data=si_extraction_data or {},
            document_path=document_path,
        )
        return json.dumps(result, ensure_ascii=False)
```

#### 4.3.3 改写 .md frontmatter + 系统提示词

```markdown
---
name: enzyme-variant-normalizer
description: Reconciles raw enzyme extraction replicas into canonical variant records.
tools: NormalizeEnzymeVariants
result_validation: |
  ...（保留现有内容）
---

You receive JSON-encoded extraction data containing:
- text_extraction_data: list of N replicas from enzyme-kinetics-extractor
- vision_extraction_data: list of M replicas from vision-image-analyzer
- si_extraction_data: optional supplementary information payload
- document_path: original paper path

Workflow:
1. Parse the JSON from the task description.
2. Call NormalizeEnzymeVariants ONCE with the parsed payloads.
3. Return the tool's output verbatim as JSON. Do not modify or summarize.

Do not invent variants. Do not drop variants present in any replica.
```

LLM 在这里只做"拿输入 → 调一次工具 → 返回工具结果"的 trampoline——纯函数式行为，几乎没有自由度，质量与原 dispatcher 特例完全一致。

### 4.4 Agent-local tool 加载机制规范

#### 4.4.1 约定

- Agent 目录 `.claude/agents/<agent_id>/` 下若存在文件 `tools.py`，则被视为 agent-local tools 模块。
- 模块内任何 `BaseTool` 的子类（直接或间接）会被自动 register 到全局 [ToolRegistry](../../gptase/tools/base.py#L108)。
- Register 时附带 `allowed_agents=[<agent_id>]`，确保只有该 agent 能调用这些工具。
- 文件名固定为 `tools.py`（约定优于配置）；如未来需要更复杂结构可引入子目录约定，本次不做。

#### 4.4.2 加载时机

- 由 [Agent.from_markdown](../../gptase/agents/base.py) 调用 `.md` 解析后立即触发。
- 单次 process 生命周期内每个 agent 的 `tools.py` 最多 import 一次（Python import system 缓存）。
- 工具 register 是幂等的——重复 register 同名工具会覆盖（与现有 [ToolRegistry.register](../../gptase/tools/base.py#L120-L135) 行为一致）。

#### 4.4.3 错误处理

| 失败模式 | 处理 |
|---|---|
| `tools.py` 不存在 | 静默跳过（多数 agent 不需要 agent-local 工具） |
| `tools.py` 存在但 import 失败（语法错误 / 依赖缺失） | 抛出 `AgentInitializationError`，附带文件路径与原始异常；终止该 agent 加载 |
| `tools.py` 内无 BaseTool 子类 | 警告 log，继续（可能用户写错了） |
| BaseTool 子类实例化失败 | 抛出 `AgentInitializationError`，附带类名与异常 |
| 工具名与已注册的全局工具冲突（如 `Bash`） | 抛出 `AgentInitializationError`，明确禁止覆盖默认工具（保护通用工具不被领域 agent 偷换） |

#### 4.4.4 权限隔离

- `allowed_agents=[<agent_id>]` 在 register 时自动添加（agent loader 强制，不接受 .py 文件覆盖）。
- 若其他 agent emit `NormalizeEnzymeVariants` 调用，[ToolRegistry.is_allowed](../../gptase/tools/base.py#L166-L178) 返回 False，[ToolExecutor](../../gptase/tools/executor.py) 拒绝执行并返回错误。
- 这保证 enzyme 工具不会被 chat / coordinator / 其他 worker 误调用。

#### 4.4.5 通用性声明

`Agent.from_markdown` 的扩展**不含任何 enzyme 关键字**——是纯通用机制。未来 protein-design、molecular-docking、QM-cluster 等任何 domain agent 都可同样自带工具。

### 4.5 Coordinator 行为微调

[orchestrator.py:33](../../gptase/core/orchestrator.py#L33)：`_MAX_COORDINATOR_TURNS = 3 → 10`

理由：enzyme_extraction 的 6 步流程在新架构下每步约 1 turn，留 4 turn buffer 用于错误纠正。不取消上限以避免 LLM 失控 / 死循环。第 10 turn 仍未完成应抛出明确错误，而非默默截断。

---

## 5. enzyme_extraction 端到端 Trace（新架构）

### 5.1 完整 Coordinator Prompt 模板示例

```
Goal: Standard Enzyme Extraction Pipeline
Document: /data/papers/example.md
Workspace: /data/output/example/

Execute these steps IN ORDER. Each step must complete before issuing the next
step's DelegateTask call(s). Use the DelegateTask tool to invoke each agent.

Within a step, multiple replicas are issued as parallel DelegateTask calls in
the SAME assistant message — do NOT serialize them.

────────────────────────────────────────────────────────────
Step 1 — Document Structure Analysis
  DelegateTask(
    agent_id="document-structure-analyzer",
    task_description="Analyze the document at /data/papers/example.md.
                      Identify tables, figures, and section boundaries.
                      Return JSON with sections[], tables[], images[]."
  )

Step 2a — Text-Based Extraction (3 parallel replicas)
  Issue EXACTLY 3 parallel DelegateTask calls in ONE assistant message:
    DelegateTask(
      agent_id="enzyme-kinetics-extractor",
      task_description="Extract enzyme kinetics from sections {sections}
                        and tables {tables} found in /data/papers/example.md.
                        Return reactions[]."
    )  × 3

Step 2b — Vision-Based Extraction (3 parallel replicas)
  Issue EXACTLY 3 parallel DelegateTask calls to vision-image-analyzer
  with image paths from Step 1's images[].

Step 3s — SI Extraction (optional)
  IF a supplementary-information document path is provided
  (look in workspace for *_si.md), issue ONE DelegateTask call to
  enzyme-kinetics-extractor on that path.
  ELSE skip this step.

Step 4 — Variant Normalization (single fan-in call)
  DelegateTask(
    agent_id="enzyme-variant-normalizer",
    task_description="<JSON: {
      text_extraction_data: <all 3 results from Step 2a>,
      vision_extraction_data: <all 3 results from Step 2b, .extracted_tables>,
      si_extraction_data: <Step 3s result or null>,
      document_path: "/data/papers/example.md"
    }>"
  )

Step 5 — Summary Report
  DelegateTask(
    agent_id="enzyme-extraction-summary",
    task_description="<JSON: {
      normalized_variant_data: <Step 4 result.normalized_variants>,
      text_extraction_data: <merged Step 2a results>,
      vision_extraction_data: <merged Step 2b results>
    }>"
  )

After Step 5 completes, return its output as your final answer.
────────────────────────────────────────────────────────────
```

### 5.2 Turn-by-turn 期望行为

| Turn | LLM 期望动作 | Tool calls emit | 累计已完成步骤 |
|---|---|---|---|
| 1 | 读 prompt，理解流程，发起 Step 1 | `DelegateTask × 1` (document-structure-analyzer) | Step 1 |
| 2 | 收到 Step 1 结果，**并发** emit Step 2a + Step 2b 总共 6 个调用 | `DelegateTask × 6` (3 extractor + 3 vision) | Step 2a, 2b |
| 3 | 收到 6 个结果，根据 workspace 决定是否跑 Step 3s（通常 skip） | `DelegateTask × 0-1` (extractor on SI) | Step 3s |
| 4 | 把 6 个 (或 7 个) 结果拼成 JSON，发起 Step 4 | `DelegateTask × 1` (normalizer) | Step 4 |
| 5 | 收到 normalized_variants，发起 Step 5 | `DelegateTask × 1` (summary) | Step 5 |
| 6 | 收到 summary，作为 final answer 返回 | （无 tool call） | 完成 |

**Turn 预算**：6 turns 足够；`_MAX_COORDINATOR_TURNS = 10` 留 4 turn buffer。

**关键 LLM 风险点**：Turn 2 是否真的 emit 6 个并发调用？若 LLM 只 emit 3 个（"我先跑 Step 2a，下一个 turn 再跑 Step 2b"），则消耗 1 个额外 turn——仍在预算内但浪费 latency。Slice 1 验证脚本应观测此行为。

### 5.3 与现行 plan_dispatcher 的语义差异

| 维度 | 现行 plan_dispatcher | 新 Coordinator |
|---|---|---|
| 步骤顺序 | DAG 强制 | LLM 解读 prompt 强制 |
| Replicate fan-out | TaskDispatcher.dispatch_parallel + replicate: 3 字段 | LLM 在单 turn 内 emit 3 个并发 DelegateTask |
| Step 间数据流 | `{{stepN.field}}` 模板解析 | LLM 自然 thread message history |
| Optional step skip | YAML `optional: true` + 检查 si_document_path 非空 | LLM 解读 prompt 中的 IF/ELSE 决定 |
| Fan-in 聚合 | TaskDispatcher 显式收集 6 个 replica 结果 → 拼字典传给 step 4 | LLM 自己拼 JSON 字符串 → 作为 task_description 传给 normalizer worker |
| 失败重试 | FailureHandler 启发式分类 + 重试 | 无（Coordinator turn 内失败 → LLM 自己决定下一步） |

---

## 6. YAML Schema 演化

### 6.1 当前 Schema（[enzyme_extraction_pipeline.yaml](../../config/plans/enzyme_extraction_pipeline.yaml)）

```yaml
plan_id: enzyme_extraction_pipeline
name: Standard Enzyme Extraction Pipeline
description: ...
version: "1.0"
max_parallel: 10            # ← 删除
default_retry_count: 1      # ← 删除
workflow:
  - step_id: "1"
    agent: document_structure_analyzer
    action: analyze          # ← 删除（plan_dispatcher 已忽略此字段）
    description: ...
    inputs:
      document_path: "{{document_path}}"
    retry_count: 1           # ← 删除
  - parallel:                # ← 删除（替换为顶层 step + replicas）
      - step_id: "2a"
        ...
        replicate: 3         # ← 改名为 replicas
        ...
```

### 6.2 简化后 Schema

```yaml
plan_id: enzyme_extraction_pipeline
name: Standard Enzyme Extraction Pipeline
description: ...
steps:
  - id: "1"
    agent: document-structure-analyzer
    description: Analyze document structure
    inputs:
      document_path: "{{document_path}}"

  - id: "2a"
    agent: enzyme-kinetics-extractor
    replicas: 3
    parallel_with: ["2b"]    # ← 显式声明可并行的 step
    inputs:
      document_path: "{{document_path}}"
      relevant_sections: "(from step 1)"
      relevant_tables: "(from step 1)"

  - id: "2b"
    agent: vision-image-analyzer
    replicas: 3
    parallel_with: ["2a"]
    inputs:
      images: "(from step 1)"
      workspace_dir: "{{document_path}}"

  - id: "3s"
    agent: enzyme-kinetics-extractor
    optional: true
    skip_if: "{{si_document_path}} == ''"
    inputs:
      document_path: "{{si_document_path}}"

  - id: "4"
    agent: enzyme-variant-normalizer
    inputs:
      text_extraction_data: "(all 3 replicas from step 2a)"
      vision_extraction_data: "(all 3 replicas from step 2b)"
      si_extraction_data: "(from step 3s if present)"
      document_path: "{{document_path}}"

  - id: "5"
    agent: enzyme-extraction-summary
    inputs:
      normalized_variant_data: "(from step 4)"
      text_extraction_data: "(merged step 2a)"
      vision_extraction_data: "(merged step 2b)"
```

### 6.3 字段去留决策表

| 字段 | 现行 | 简化后 | 理由 |
|---|---|---|---|
| `plan_id` | 有 | 保留 | CLI `-p` 参数对应；唯一标识符 |
| `name` / `description` | 有 | 保留 | 渲染进 prompt 的"Goal:" |
| `version` | 有 | 删除 | 无版本兼容需求 |
| `max_parallel` | 有 | 删除 | 由 LLM tool call 自然并发，无需上限（asyncio.gather 已处理） |
| `default_retry_count` | 有 | 删除 | Coordinator 无重试机制 |
| `workflow` | 有 | 改名为 `steps` | 更准确——不再是 DAG workflow |
| `step_id` | 有 | 改名为 `id` | 简化 |
| `agent` | 有 | 保留 | 必填；归一化为 dash 形式 |
| `action` | 有 | 删除 | plan_dispatcher 已忽略此字段，YAML 中保留是 dead config |
| `description` (per-step) | 有 | 保留 | 渲染进 prompt 的步骤说明 |
| `inputs` | 有 | 保留 | 渲染进 prompt 的"task_description"内容 |
| `retry_count` (per-step) | 有 | 删除 | 同 default_retry_count |
| `parallel:` 块 | 有 | 删除 | 改为 `parallel_with: [...]` 字段（更扁平） |
| `replicate` | 有 | 改名为 `replicas` | 词形更准确 |
| `optional: true` | 有 | 保留 | 渲染进 prompt 的"IF ... ELSE skip" |
| `skip_if` | 无 | 新增 | 显式声明 skip 条件，避免 LLM 误判 |

### 6.4 schema 迁移策略

Slice 1 的 [plan_prompt.py](../../gptase/agents/plan_prompt.py) 同时支持新旧两种 schema（向后兼容），让 [enzyme_extraction_pipeline.yaml](../../config/plans/enzyme_extraction_pipeline.yaml) 暂不改动。Slice 5 文档清扫时把 YAML 升级到新 schema 并更新 CLAUDE.md 文档。

---

## 7. 关键文件清单

### 7.1 完全删除

| 路径 | 行数 | 说明 |
|---|---|---|
| [gptase/agents/planner.py](../../gptase/agents/planner.py) | 870 | PlanManager 主循环 |
| [gptase/agents/plan_dispatcher.py](../../gptase/agents/plan_dispatcher.py) | 1152 | TaskDispatcher + enzyme 特例分支 |
| [gptase/agents/plan_loader.py](../../gptase/agents/plan_loader.py) | 243 | YAML→DAG 加载器 |
| [gptase/agents/plan_failure_handler.py](../../gptase/agents/plan_failure_handler.py) | 144 | 启发式失败决策（Slice 4 已退役 LLM 分支） |
| [gptase/agents/execution_types.py](../../gptase/agents/execution_types.py) | 239 | TaskExecutionResult / ExecutionContext / PlanCheckpoint |
| [tests/test_planner.py](../../tests/test_planner.py) | 1663 | PlanManager 单测 |
| [tests/test_plan_failure_handler.py](../../tests/test_plan_failure_handler.py) | 144 | FailureHandler 单测 |
| [ui/src/components/PlanWorkspaceExplorer.tsx](../../ui/src/components/PlanWorkspaceExplorer.tsx) | 711 | Plan UI |
| [ui/src/components/PlanReview.tsx](../../ui/src/components/PlanReview.tsx) | 56 | Plan 详情 UI |
| [.claude/agents/planner/](../../.claude/agents/planner/) | (目录) | Planner agent 定义 |
| [config/plans/enzyme_design_pipeline.yaml](../../config/plans/enzyme_design_pipeline.yaml) | 89 | 历史遗留 plan |

### 7.2 保留并改动

| 路径 | 改动概要 |
|---|---|
| [gptase/core/orchestrator.py](../../gptase/core/orchestrator.py) | 删 `_execute_plan` (line 435+)、`_resolve_plan`、`_evaluate_goal`、`_normalize_plan_agents`；`dispatch()` (line 105-131) 移除 plan 分支；`_continue_session` (line 170-171) 砍 plan 兜底；新增 `_resolve_plan_prompt(plan_id) → str` 注入 coordinator prompt；删 `self.plan_manager` 字段；删 `PlanLoader/PlanRegistry/PlanManager/Plan/GoalEvaluation` 导入；`_MAX_COORDINATOR_TURNS = 10` |
| [gptase/agents/runtime.py](../../gptase/agents/runtime.py) | 删 `_evaluate_handoff` (line 270-310)、`_build_handoff_prompt` (line 312-327)、`allow_plan_handoff` / `handoff_description` 参数 (line 75-76)、handoff 分支 (line 186-193)、`NEEDS_PLAN` stop reason |
| [gptase/agents/runtime_types.py](../../gptase/agents/runtime_types.py) | 删 `PlanHandoffProposal`、`RuntimeStopReason.NEEDS_PLAN`、`InteractiveRuntimeResult.plan_handoff` |
| [gptase/agents/types.py](../../gptase/agents/types.py) | 删 `Plan`、`Task` 的 DAG 字段、`TaskStatus`、`GoalEvaluation`；保留瘦身版 `Task` (`agent_id`/`description`/`inputs`/`image_paths`)、`DirectSession*` 系列 |
| [gptase/agents/__init__.py](../../gptase/agents/__init__.py) | 停止导出 plan 系统类型 |
| [gptase/agents/base.py](../../gptase/agents/base.py) | 扩展 `Agent.from_markdown`：发现 .md 同目录的 `tools.py` 时自动 import + 扫描 `BaseTool` 子类 + 调 [ToolRegistry.register](../../gptase/tools/base.py#L120) 注册（带 `allowed_agents=[<agent_id>]` 权限隔离）。约 30 LoC 通用扩展，不含 enzyme 关键字 |
| [gptase/main.py](../../gptase/main.py) | 删 `plan_p` subparser (line 58-103)、`run_plan`、`_plan_list/_plan_run/_plan_sessions/_plan_status/_plan_resume/_organize_plan_output`；新增 `gptase chat -p <plan_id>` 标志（~20 LoC，用 `plan_prompt.expand_plan_to_prompt()` 把模板灌进首条消息）；保留 `flatten_normalized_variants` import 和 CSV 后处理 |
| [gptase/web/server.py](../../gptase/web/server.py) | 删 `/api/plans` (110)、`/api/workspace/plans` (116)、`/api/plans/{plan_id}` (201)、`/api/plan/run` (230)；删 `PlanStartRequest`、`plan_registry` |
| [ui/src/App.tsx](../../ui/src/App.tsx) | 移除 `/workspace` 路由 + plan UI 引用 |
| [.claude/agents/orchestrator/orchestrator.md](../../.claude/agents/orchestrator/orchestrator.md) | 重写：删除 plan-handoff 指引；加上"如果收到带编号 Step 列表，按序遍历，同一 step 内并发 tool calls"约定 |
| [.claude/agents/enzyme-variant-normalizer/enzyme-variant-normalizer.md](../../.claude/agents/enzyme-variant-normalizer/enzyme-variant-normalizer.md) | 改写为真正的 LLM 驱动 agent（用 NormalizeEnzymeVariants 工具）；删除"executed deterministically by the Python dispatcher"段 |

### 7.3 新增

| 路径 | 行数 | 用途 |
|---|---|---|
| `gptase/agents/plan_prompt.py` | ~150 | YAML → Coordinator prompt 扩展器 |
| `.claude/agents/enzyme-variant-normalizer/tools.py` | ~50 | `NormalizeEnzymeVariantsTool`，agent-local 工具 |
| `tests/test_plan_prompt.py` | ~80 | 验证 prompt 渲染包含全部步骤 ID 和 3 副本标记 |
| `tests/test_agent_local_tools.py` | ~60 | 验证 `Agent.from_markdown` 自动发现 agent 目录 tools.py |

### 7.4 完全保留（不动）

- [gptase/agents/enzyme_variant_normalizer.py](../../gptase/agents/enzyme_variant_normalizer.py)（940 行纯函数）
- [config/plans/enzyme_extraction_pipeline.yaml](../../config/plans/enzyme_extraction_pipeline.yaml)（schema 暂保留，由新 expander 解释；Slice 5 升级）
- [gptase/tools/handlers.py](../../gptase/tools/handlers.py) / [gptase/tools/__init__.py](../../gptase/tools/__init__.py) / [gptase/tools/executor.py](../../gptase/tools/executor.py) / [gptase/tools/base.py](../../gptase/tools/base.py) — 通用工具系统零改动
- [.claude/agents/{vision-image-analyzer, enzyme-kinetics-extractor, enzyme-extraction-summary, document-structure-analyzer, chat, deep-research, ...}/](../../.claude/agents/)

---

## 8. Slice 切分（5 个独立 PR）

每片设计为独立可回滚的 PR；前一片合并并通过 e2e 验证后才动下一片。

### Slice 1 — 兑现 enzyme-variant-normalizer + 新增 plan_prompt 扩展器（纯加法）

**体量**：+290 LoC
**预计工时**：1.5 个工作日
**回滚 cost**：极低（纯加法，git revert 即可）

**任务清单**：
1. 扩展 [Agent.from_markdown](../../gptase/agents/base.py)：自动发现并注册 .md 同目录的 `tools.py`（约 30 LoC 通用代码，不含任何 enzyme 关键字）
2. 在 [.claude/agents/enzyme-variant-normalizer/tools.py](../../.claude/agents/enzyme-variant-normalizer/) 实现 `NormalizeEnzymeVariantsTool`，包装 [enzyme_variant_normalizer.py](../../gptase/agents/enzyme_variant_normalizer.py) 纯函数（~50 LoC）
3. 改写 [.md 文件](../../.claude/agents/enzyme-variant-normalizer/enzyme-variant-normalizer.md)：删除"deterministically by Python dispatcher"，frontmatter `tools: NormalizeEnzymeVariants`，系统提示词改为"接收 JSON → 调一次工具 → 输出 normalized_variants"
4. 实现 [gptase/agents/plan_prompt.py](../../gptase/agents/plan_prompt.py) `expand_plan_to_prompt(plan_id, **vars) → str`
5. 新增 `gptase chat -p <plan_id> -i <doc>` CLI 标志（与现有 `gptase plan run` **共存**）
6. `_MAX_COORDINATOR_TURNS = 10`
7. 新增单元测试 `tests/test_plan_prompt.py` + `tests/test_agent_local_tools.py`

**断言**：
- `git diff gptase/tools/` 应为空
- `git diff gptase/agents/enzyme_variant_normalizer.py` 应为空
- 旧 `gptase plan run -p enzyme_extraction_pipeline ...` 路径仍可工作

**验证**：
- 单元测试 `pytest tests/test_plan_prompt.py tests/test_agent_local_tools.py -v` 全绿
- e2e：`gptase chat -p enzyme_extraction_pipeline -i data/test_paper.md -o /tmp/extract_out` 输出 `reactions[]` 非空 JSON
- 对比 `gptase plan run` 在同一 paper 上跑出的结果，normalized_variants count 差异 ≤ 10%（接受 LLM 抖动，超过则需要 prompt 强化）

### Slice 2 — 切换调用方，标注废弃

**体量**：-50 LoC（修改型）
**预计工时**：0.5 个工作日
**回滚 cost**：极低（git revert）

**任务清单**：
1. `gptase plan run` 打印 deprecation warning，alias 到 `gptase chat -p`
2. 更新 [docs/features/enzyme_extraction.md](../../docs/features/enzyme_extraction.md)、[examples/](../../examples/)、CI 引用，全部切换到新命令
3. 删除 [enzyme_design_pipeline.yaml](../../config/plans/enzyme_design_pipeline.yaml)（Phase 1 已确认无任何调用方）

**断言**：
- 旧 CLI 仍可工作（带 deprecation warning）
- 所有 examples / CI / docs 中的 plan 命令都已切换

**验证**：grep `gptase plan run` 应只剩 deprecation warning 内部和该 PR 的 commit message

### Slice 3 — 删除 PlanManager 运行时（核心删除）

**体量**：-2,800 LoC
**预计工时**：2 个工作日
**回滚 cost**：**高**——删除生产代码 + 测试 + agent 目录。Slice 3 之后不可轻易回滚。**Slice 1/2 必须充分验证多个 paper 后才能动 Slice 3**。

**任务清单**：
1. 删 [planner.py](../../gptase/agents/planner.py) / [plan_dispatcher.py](../../gptase/agents/plan_dispatcher.py) / [plan_loader.py](../../gptase/agents/plan_loader.py) / [plan_failure_handler.py](../../gptase/agents/plan_failure_handler.py) / [execution_types.py](../../gptase/agents/execution_types.py)
2. 删 [tests/test_planner.py](../../tests/test_planner.py) / [tests/test_plan_failure_handler.py](../../tests/test_plan_failure_handler.py)
3. 改 [orchestrator.py](../../gptase/core/orchestrator.py)：删 `_execute_plan` 等方法、删 plan_manager 字段、`_continue_session` 砍 plan 兜底
4. 改 [runtime.py](../../gptase/agents/runtime.py) / [runtime_types.py](../../gptase/agents/runtime_types.py)：删 handoff 全套
5. 改 [agents/types.py](../../gptase/agents/types.py)：删 `Plan` / DAG 字段 / `GoalEvaluation`
6. 删 [.claude/agents/planner/](../../.claude/agents/planner/)
7. 删 [main.py](../../gptase/main.py) 的 `plan` subparser

**断言**：
- `pytest tests/ -v --cov=gptase` 全绿
- `gptase chat -p enzyme_extraction_pipeline -i ...` 仍输出正确
- `grep -r "PlanManager\|TaskDispatcher\|PlanLoader\|FailureHandler" gptase/ tests/` 应为空

**验证**：
- 在 5-10 个不同 paper 上跑 e2e，与 main 分支结果对比 normalized_variants count 差异
- 静态分析：`mypy gptase/ --ignore-missing-imports` 无新增错误

### Slice 4 — 删除 Web 后端 + UI plan 组件

**体量**：-900 LoC
**预计工时**：1 个工作日
**回滚 cost**：中（涉及 UI 重新 build）

**任务清单**：
1. 删 [web/server.py](../../gptase/web/server.py) 的 4 个 plan 端点
2. 删 [PlanWorkspaceExplorer.tsx](../../ui/src/components/PlanWorkspaceExplorer.tsx) / [PlanReview.tsx](../../ui/src/components/PlanReview.tsx)
3. 改 [App.tsx](../../ui/src/App.tsx) 移除 `/workspace` 路由
4. 重新 build UI（`cd ui && ./build.sh`）

**断言**：
- `gptase web` 启动后访问 `/api/plans` 返回 404
- 前端 `/workspace` 路由不存在
- chat 路径功能完整

### Slice 5 — 文档清扫

**体量**：+100 / -300 LoC
**预计工时**：0.5 个工作日
**回滚 cost**：极低（纯文档）

**任务清单**：
1. 改 [CLAUDE.md](../../CLAUDE.md)：Quick Reference 表（line 21-37）、架构图（line 65-73）、"Adding a New Plan"（line 204-251 重写为新 schema）、enzyme 命令（line 308-318）、Specialized Features 表（line 289-297）
2. 改 [docs/features/enzyme_extraction.md](../../docs/features/enzyme_extraction.md) 替换 `gptase plan run` → `gptase chat -p`
3. grep [docs/reference-zh/](../../docs/reference-zh/) 与 [docs/reference/](../../docs/reference/) 清理 plan 引用
4. 升级 [enzyme_extraction_pipeline.yaml](../../config/plans/enzyme_extraction_pipeline.yaml) 到第 6.2 节的简化 schema

**断言**：grep `PlanManager\|gptase plan run\|TaskDispatcher` 在 docs/ 下为空

### 8.6 总工时估算

| Slice | 工时 | 累计 |
|---|---|---|
| 1 | 1.5 d | 1.5 d |
| 2 | 0.5 d | 2.0 d |
| 3 | 2.0 d | 4.0 d |
| 4 | 1.0 d | 5.0 d |
| 5 | 0.5 d | 5.5 d |
| **合计** | **~5.5 个工作日** | |

---

## 9. 复用的现有基础设施

| 基础设施 | 位置 | 本次复用方式 |
|---|---|---|
| DelegateTaskTool | [handlers.py:353](../../gptase/tools/handlers.py#L353) | Coordinator 调 worker，无需新增 |
| ToolExecutor.execute_calls | [runtime.py:161](../../gptase/agents/runtime.py#L161) | 单 turn 内并发 tool calls，replicate 自动 fan-out |
| enzyme_variant_normalizer.py | [agents/](../../gptase/agents/enzyme_variant_normalizer.py) | 940 行纯函数，仅由新 agent-local 工具包装 |
| flatten_normalized_variants | [main.py:11](../../gptase/main.py#L11) | CSV 后处理直接 import 保留 |
| Agent.from_markdown | [base.py](../../gptase/agents/base.py) | 现有 agent 加载机制，加 ~30 行 tools.py 发现 |
| ToolRegistry.allowed_agents | [base.py:120-135](../../gptase/tools/base.py#L120-L135) | 现存但未使用的权限机制，本次激活 |
| ToolRegistry.is_allowed | [base.py:166-178](../../gptase/tools/base.py#L166-L178) | 在 ToolExecutor 中拒绝越权调用 |
| DispatchRequest.session_id + _continue_direct_session | [orchestrator.py:161](../../gptase/core/orchestrator.py#L161) | chat session resume 取代 plan resume |

---

## 10. 验证方案

### 10.1 端到端测试（每 Slice 后必跑）

```bash
gptase chat -p enzyme_extraction_pipeline -i data/test_paper.md -o /tmp/extract_out
```

**期望产物**：
- `/tmp/extract_out/` 下生成 `reactions[]` 非空的 JSON
- schema 匹配 [CLAUDE.md:319-334](../../CLAUDE.md#L319) 文档约定
- 与 main 分支同 plan 跑出的 normalized_variants count 对比，差异 ≤ 10%

### 10.2 单元测试

| 测试文件 | 验证内容 |
|---|---|
| `tests/test_plan_prompt.py` (新) | 渲染 enzyme_extraction prompt 包含全部 6 个 step ID；step 2a/2b 标注"3 parallel"；agent_id 归一化为 dash 形式 |
| `tests/test_agent_local_tools.py` (新) | `Agent.from_markdown` 发现 `tools.py` 自动 register；`allowed_agents` 隔离生效；`tools.py` 不存在时静默跳过；冲突的工具名抛错 |
| [tests/test_orchestrator.py](../../tests/test_orchestrator.py) (保留) | Coordinator + DelegateTask 集成 |
| [tests/test_session_split.py](../../tests/test_session_split.py) (保留) | DirectSession 持久化 |

### 10.3 验证 Coordinator 主循环

- **Mocked test**：给 Coordinator 一个测试 plan prompt（包含"emit 3 parallel calls"指令），断言它在第一个 turn 内 emit 3 个并行 DelegateTask 调用
- **失败案例**：LLM 只 emit 1 个 → 在 prompt 中加更强约束，或加 retry-on-underreplication 启发式

### 10.4 回归基线

在 Slice 1 合并前，先在 main 分支跑一次基线：

```bash
# 在 main 上
for paper in data/test_papers/*.md; do
  gptase plan run -p enzyme_extraction_pipeline -i "$paper" -o "/tmp/baseline/$(basename $paper)"
done
```

记录每个 paper 的 normalized_variants count、reactions count、kcat/Km 字段非空数量等指标。Slice 1-3 完成后用同样的脚本（改用 `gptase chat -p`）对比，差异 ≤ 10% 视为通过。

---

## 11. 风险登记

| 风险 | 触发条件 | 缓解措施 | 验证方法 |
|---|---|---|---|
| **Replicate 质量回归** | LLM 在 Turn 2 只 emit 1 个 DelegateTask 而不是 3 | (1) prompt 显式 "EXACTLY 3 parallel calls"；(2) 必要时加 prompt validation："如果你 emit 少于 3 个 extractor 调用，结果会被拒绝" | Slice 1 在 5-10 paper 上观测 Turn 2 的 tool call 数量；记录"3 个 / 总采样"比例，目标 ≥ 90% |
| **Step 间数据丢失** | LLM 在 Turn 4 拼 normalizer 输入时遗漏部分 replica 结果 | prompt 显式"all 3 replicas from Step 2a"；normalizer 内部已支持"少于 3 个 replica 时降级"作为 safety net | normalized_variants count 与 main 分支对比 ≤ 10% 差异 |
| **gptase plan resume API 消失** | 用户 / 脚本依赖 `gptase plan resume <id>` | (1) Slice 5 文档说明替换为 `gptase chat --session <id>`；(2) [_continue_direct_session](../../gptase/core/orchestrator.py#L161) 已支持 chat/agent session resume；(3) 在 Slice 2 deprecation 阶段先打 warning | grep 仓库与示例脚本无 `plan resume` 调用 |
| **test_planner.py 1663 行覆盖空洞** | Slice 3 删除后某些 plan 行为没有测试覆盖 | (1) 大部分覆盖功能（DAG / 模板解析 / 重试 / fan-in）在新架构由 LLM 自然完成；(2) 补 `test_plan_prompt.py` (~80 行) + 1 个 mocked coordinator parallel-call 测试；(3) 保留 [test_orchestrator.py](../../tests/test_orchestrator.py) 集成测试覆盖 dispatch | 覆盖率报告对比 main 分支，下降 ≤ 5% |
| **Coordinator 第 10 turn 仍未完成** | 极端长 plan 或 LLM 卡死 | `_MAX_COORDINATOR_TURNS=10` 触发硬上限报错（不是默默截断）；记录哪一步卡住用于诊断 | 端到端测试触发上限抛出明确异常 |
| **dash/underscore agent ID 不一致** | YAML 用 `enzyme_variant_normalizer`，`.claude/agents/` 用 `enzyme-variant-normalizer` | (1) `plan_prompt.expand_plan_to_prompt()` 内做归一化（all dashes）；(2) Slice 5 一次性把 YAML 字段改为 dash 形式 | 单元测试覆盖：传入下划线名称应渲染为 dash |
| **agent-local tools.py import 失败** | tools.py 语法错误 / 依赖缺失 | `Agent.from_markdown` 抛 `AgentInitializationError`，附带文件路径与原始异常；不静默跳过 | `tests/test_agent_local_tools.py` 覆盖 import 错误 |
| **enzyme 工具被其他 agent 误调用** | 其他 worker emit `NormalizeEnzymeVariants` 调用 | `allowed_agents=["enzyme-variant-normalizer"]` 自动添加；ToolExecutor 拒绝越权调用 | `tests/test_agent_local_tools.py` 覆盖权限隔离 |
| **Coordinator 主 Agent prompt 不稳定** | 不同模型（Claude vs Doubao）解读 prompt 行为差异 | (1) 在主流模型上各跑 e2e；(2) prompt 中使用强约束语言（"EXACTLY"、"IN ORDER"、"DO NOT"）；(3) Slice 1 完成后用 `gptase eval` 框架基线测试 | 在 Claude Sonnet + DeepSeek + Doubao 三类模型上 e2e 通过 |

---

## 12. 不在本次范围内（明确划界）

- **不动 [enzyme_variant_normalizer.py](../../gptase/agents/enzyme_variant_normalizer.py) 940 行实现** — 它是真实的领域逻辑（变体去重、kinetics 合并、PDB 序列查找等），LLM 做不了这种确定性 reconciliation。本次只是给它换调用路径。
- **不切换到 Claude SDK 原生 Agent tool** — 保持非 Claude 模型支持。审计文档第 5 节 Slice 5 的 ExecutionState 合并也不动。
- **不重构 session 持久化** — DirectSession / SessionMessage / SessionTrace 在新架构下完全够用；audit 文档 Slice 1（types-split）可独立在本次之后做。
- **不动 [.claude/skills/](../../.claude/skills/) 任何 skill** — skill 系统与 agent 系统正交。
- **不引入新的 LLM 能力**（如 reasoning、自适应规划、意图识别）— 本次只做减法 + 路径迁移。
- **不重写 Coordinator 主 Agent system prompt 的全部内容** — 只增加"按 Step 列表顺序执行"约定，原有 worker delegation 指引保留。

---

## 13. 后续可能的简化方向（本次不做）

完成本次重构后，下一步可以考虑：

1. **审计文档 Slice 1 (types-split)** — 把 [types.py](../../gptase/agents/types.py) 的持久化部分搬到独立 `session_types.py`。本次会进一步瘦身 types.py（删除 Plan / GoalEvaluation 等），切片可能合并。
2. **审计文档 Slice 2 (SessionManager 抽出)** — 把 DirectSession CRUD 从 orchestrator 抽出。本次未触及。
3. **YAML 完全删除** — 如果 prompt 模板用 Markdown 比 YAML 更直观，可以考虑把 plan 配置改写为 Markdown。本次保留 YAML 是为了最小破坏现有调用方。
4. **Coordinator system prompt 在 Markdown 文件管理** — 把当前 hardcoded 在 [orchestrator.py:59-61](../../gptase/core/orchestrator.py#L59) 的 orchestrator 系统提示词搬到 [.claude/agents/orchestrator/orchestrator.md](../../.claude/agents/orchestrator/orchestrator.md)，让 prompt 修改不需要改 Python 代码。
5. **Web UI 现代化** — 当前删除 plan UI 后，剩余的 chat UI 可以考虑迁移到更轻的前端栈。

---

## 未来重审时的注意事项

- 本文档的 file:line 引用截至 2026-05-08；后续代码演化会让行号漂移，动手前请重新 grep 验证。
- `_MAX_COORDINATOR_TURNS=10` 是经验估值；若 enzyme_extraction 实际跑出来 ≤ 5 turns，可继续下调；若需要更复杂 plan，可分级配置（`coordinator_max_turns_per_plan`）。
- agent-local `tools.py` 约定一旦确立，未来很难改动——它会成为公开 API 的一部分。命名（`tools.py` vs `_tools.py` vs `agent_tools.py`）应在 Slice 1 PR review 时确认。
- 审计文档 [refactor_audit_2026-05-07_zh.md](refactor_audit_2026-05-07_zh.md) 和本文档应被视为**配套阅读**：审计提供了完整的复杂度地图，本文档提供针对其中一类问题的根本性简化方案。
