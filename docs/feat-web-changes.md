# feat/web 分支改动记录

## 概述

本次改动分两部分：**Web UI 整体重设计**（组件拆分 + API 接入）和**抽取结果可视化工作台**（`PlanWorkspaceExplorer`）。

---

## 一、Web UI 重设计

### 组件结构

原 `App.tsx` 拆分为以下独立组件：

| 组件 | 职责 |
|------|------|
| `SessionList` | 左侧边栏，会话列表 + 搜索 + plan 导航 |
| `MainWorkspace` | 中央工作区，消息流 + 输入框 + 计划审批 |
| `DetailPanel` | 右侧详情面板，执行计划 / 追踪 / 记忆 / 评估四 Tab |
| `AgentSelector` | Agent 选择下拉，支持能力标签展示 |
| `PlanReview` | Draft plan 审批卡片（批准 / 拒绝 / 修改） |
| `PlanWorkspaceExplorer` | 独立页面，抽取结果可视化工作台（`/workspace/plan-explorer`） |

### 数据流

- `App.tsx` 负责所有 API 调用和状态管理，props 向下传递
- API 响应通过 `mapSessionDetail` / `mapMessages` / `mapPlan` 等纯函数映射为前端 `Session` 类型
- WebSocket (`/ws/plan/{session_id}`) 实时推送执行进度

### Bug 修复（Code Review 阶段）

1. **`handleSendMessage` 死代码**：三条 if 已覆盖所有分支，后续 mock 计划逻辑（~80 行）永远不会执行，已删除
2. **`mapMessages` 无意义排序**：所有消息 timestamp 均为 `new Date()`，`sort` 破坏插入顺序，已移除
3. **WebSocket deps 包含 `agents`**：每次 agents 更新触发重连，已从依赖数组移除
4. **`mapEvalMetrics` 显示模型名字符数**：`latest.latest_model.length` 是字符串长度而非有意义指标，改为显示总 Trace 数
5. **`applySessionDetail` 冗余 memory 请求**：每次 WebSocket 推送都请求 memory，改为用 `memoryAgentRef` 记录上次 agentId，仅变化时才请求
6. **`initializeData` 冗余 `setCurrentSessionId`**：两次设置同一值，删除第二次
7. **`toPlan` fallback 顺序不一致**：`progress` vs `runtime_progress` 优先级与 `mapMessages` 不一致，统一为 `runtime_progress` 优先
8. **搜索框无状态**：`SessionList` 搜索输入无 `value`/`onChange`，已接入 `useState` 实现实时过滤
9. **Settings 按钮无事件**：无任何处理逻辑的装饰性按钮，已删除

---

## 二、抽取结果可视化工作台（PlanWorkspaceExplorer）

### 功能

双栏联动界面，用于可视化 `enzyme_extraction_pipeline` 的 Step 2 抽取结果。

当前页面已经调整为“证据-结果对照”模式：

- **左栏**：原文证据（excerpt；仅在可靠时显示原图）
- **右栏**：与该段证据对应的结果表
- 页面顶部支持切换 run，并保持同一套对照布局

这套布局不是按某一个固定 run 路径硬编码，而是按 agent 输出 schema 做专项优化：

- **通用骨架**：所有包含 `extraction_items` 的任务，都会先按锚点分组，再渲染成“左侧证据 + 右侧结果”
- **`enzyme-kinetics-extractor` 专项优化**：
  - 左侧不显示图片，只显示原文证据文本
  - 右侧优先按任务 CSV 中的 `enzyme_name` 匹配行，并渲染成结构化结果表
- **`vision-image-analyzer` 专项优化**：
  - 左侧优先按 `payload.image_number` 对 markdown 中的图片顺序精确映射原图
  - 右侧显示对应的图像分析文本或表格

因此，它是“面向当前两类 agent 输出格式的通用”，不是“只针对当前文件夹结果的临时特判”。

入口：主界面侧边栏底部「抽取结果可视化」链接 → `/workspace/plan-explorer`

### 联动机制

| 操作 | 效果 |
|------|------|
| 右侧点击 task 卡片 | 左侧滚动到该 task 的 anchor 行，黄色高亮 |
| 左侧滚动文档 | 右侧 task 列表自动跟随（IntersectionObserver） |
| 左侧点击文档块 | 右侧选中最近的 task |

### 关键设计决策

- **选择粒度为 task**（表格/图片块），而非单条数据点；右侧一张卡片对应一个抽取任务
- **anchor 行号**取该 task 所有 extraction items 中的最小行号（表格起始位置）
- **过滤空结果**：`payload` 全为 null/空的 items 不展示，对应 task 无有效数据则整体不列出

### Bug 修复

1. **IntersectionObserver deps 包含 `selectedTaskId`**：每次右侧点击都重建 observer，observer 初始化后立刻把选中项覆盖回"当前可见最优块"。修复：用 `selectedTaskIdRef` 传给回调，从 deps 移除 `selectedTaskId`
2. **`isAnchor` 包含 `block.taskId === selectedTaskId` 检查**：block 的 taskId 按中点距离分配，anchor 所在 block 不一定分配到同一 task，导致精确高亮丢失。修复：只按行号 `startLine ≤ anchor_line ≤ endLine` 判断
3. **`loadWorkspace` 触发二次加载**：内部 `setSelectedRunId` 使 effect 重新运行。修复：改为 `setSelectedRunId((prev) => prev ?? ...)` 避免覆盖已有值
4. **开发环境代理端口错误**：Vite 代理目标已改为 `localhost:8765`，与当前本地后端运行端口一致
5. **顶栏 run id 遮挡**：状态栏列宽改为弹性网格，并允许长 run id 自动换行
6. **误导性的任务级原始 CSV 区块**：已移除，仅保留“左侧原文证据 + 右侧对应结果表”
7. **`vision-image-analyzer` 图像错配**：原先按 caption 附近图片猜测，已改为优先按 `image_number` 映射 markdown 图片顺序
8. **`enzyme-kinetics-extractor` 错图展示**：由于锚点常落在覆盖多子图的总 caption 上，已关闭该类任务的图片显示，避免误导

### 当前基线快照

为方便后续 UI 调整后做回归比较，当前工作台页面对应的 API 响应已保存到：

- `docs/snapshots/plan-workspace/listov2025_enzyme_extraction_pipeline_20260326_184929.api.json`
- `docs/snapshots/plan-workspace/listov2025_enzyme_extraction_pipeline_20260326_184929.page.png`

对应页面参数：

- `workspace_root=/Users/ryanxu/CodeBase/feat_web`
- `document_name=listov2025`
- `plan_id=enzyme_extraction_pipeline`
- `run_id=enzyme_extraction_pipeline_20260326_184929`
