# 酶数据提取流程

## 概览

`enzyme_extraction_pipeline` 用于从论文中提取酶动力学相关数据，分为三个阶段：

1. `document-structure-analyzer`
2. 并行提取：
   - `enzyme-kinetics-extractor`（`2a`，并行重复 3 次）
   - `vision-image-analyzer`（`2b`，并行重复 3 次）
3. `enzyme-extraction-summary`

这个流程面向已经转换成 Markdown 的论文输入，例如 `listov2025.md`。

## 流程说明

### Step 1：文档结构分析

Agent：`document-structure-analyzer`

输入：
- `document_path`

输出：
- `sections`
- `tables`
- `images`

作用：
- 判断哪些章节、表格和图片与酶动力学提取相关。
- 为后续文本提取和视觉提取提供结构化引导信息。

### Step 2a：基于文本的动力学提取

Agent：`enzyme-kinetics-extractor`
重复次数：`3`

输入：
- `document_path`
- 来自 `step1.sections` 的 `relevant_sections`
- 来自 `step1.tables` 的 `relevant_tables`

作用：
- 从正文和 Markdown 表格中提取酶变体及其动力学参数。
- 先利用 `step1` 产出的结构元数据缩小范围，再读取局部文本块。

当前优化：
- 不再把整篇论文正文直接作为超大 prompt 传给 extractor。
- 现在输入改为 `document_path`、`relevant_sections` 和 `relevant_tables`。
- 再基于 `step1` 标记出的相关 section 和 table 做定向 `Grep`/`Read`。
- 这样可以显著降低初始 prompt 体积，避免一开始就把整篇论文塞进上下文。
- 在验证运行里，`2a` 的初始 user message 大小已经从大约 `102k` 字符降到大约 `4.4k` 字符。

期望输出：
- `reactions`

### Step 2b：基于图像的视觉提取

Agent：`vision-image-analyzer`
重复次数：`3`

输入：
- 来自 `step1.images` 的 `images`
- `workspace_dir`

作用：
- 直接对论文图片做多模态分析。
- 抽取图表或图片中的表格内容，并生成可聚合的 CSV 结果。

期望输出：
- `analysis_results`
- `extracted_tables`

### Step 3：汇总分析

Agent：`enzyme-extraction-summary`

输入：
- 来自 `step2a.reactions` 的 `text_extraction_data`
- 来自 `step2b.extracted_tables` 的 `vision_extraction_data`

作用：
- 统计变体覆盖率、参数覆盖率和 top performer。
- 基于文本提取和视觉提取结果生成最终结构化总结。

期望输出：
- `summary_report`
- `statistics`
- `top_performers`
- `data_quality_flags`

## 运行时说明

### Checkpoint

Planner 现在会在每个 task 完成后立即保存 checkpoint，而不是等整批并行任务全部结束后再保存。这样长时间运行时，进度显示会更准确。

### Tracking

每次走非 Claude LLM 路径的 agent 调用现在都会记录到 `data/conversations.db`，包括：
- `agent_id`
- `step_id`
- message 大小
- 单次调用 latency

这对排查慢任务、不稳定调用，以及定位到底是哪一个 step 卡住很重要。

### 输出目录结构

每个 task 的结果现在写入各自的子目录：

```text
data/output/<document_name>/<run_id>/
  document-structure-analyzer/1/
  enzyme-kinetics-extractor/2a_r1/
  enzyme-kinetics-extractor/2a_r2/
  enzyme-kinetics-extractor/2a_r3/
  vision-image-analyzer/2b_r1/
  vision-image-analyzer/2b_r2/
  vision-image-analyzer/2b_r3/
  enzyme-extraction-summary/3/
```

这替代了旧的按 agent 平铺输出方式，能把同一个 task 的所有产物放在一起。

## 常见输出文件

例如：

- `document-structure-analyzer/1/1_result.json`
- `document-structure-analyzer/1/1_sections.csv`
- `enzyme-kinetics-extractor/2a_r1/2a_r1_reactions.csv`
- `vision-image-analyzer/2b_r1/2b_r1_analysis_results.csv`
- `vision-image-analyzer/2b_r1/table_4.csv`
- `enzyme-extraction-summary/3/3_parsed.json`

## 实际运行示例

在仓库根目录执行：

```bash
conda run -n llm python -m gptase.main plan \
  -p enzyme_extraction_pipeline \
  -i data/input/listov2025/listov2025.md
```

典型输出目录：

```text
data/output/listov2025/enzyme_extraction_pipeline_<timestamp>/
```

一个完整 run 的典型结构：

```text
data/output/listov2025/enzyme_extraction_pipeline_<timestamp>/
  document-structure-analyzer/1/1_result.json
  enzyme-kinetics-extractor/2a_r1/2a_r1_result.json
  enzyme-kinetics-extractor/2a_r2/2a_r2_result.json
  enzyme-kinetics-extractor/2a_r3/2a_r3_result.json
  vision-image-analyzer/2b_r1/2b_r1_result.json
  vision-image-analyzer/2b_r2/2b_r2_result.json
  vision-image-analyzer/2b_r3/2b_r3_result.json
  enzyme-extraction-summary/3/3_result.json
```

常用运行时检查命令：

```bash
sqlite3 data/conversations.db "select session_id,status,completed_steps,total_steps,updated_at from plan_checkpoints order by updated_at desc limit 5;"
```

```bash
sqlite3 data/conversations.db "select id,agent_id,status,timestamp from conversations order by timestamp desc limit 20;"
```

## 当前瓶颈

在最新优化之后，`2a` 文本提取已经不再被超大初始 prompt 主导。当前这条流程中最重的输入主要还在 `2b` 视觉路径，因为它仍然需要携带较大的多模态图片内容。

另外，`step1` 的 `document-structure-analyzer` 在内部 tool loop 里仍然可能读取较大范围的 markdown 内容，这会带来额外开销；但在当前版本里，它已经不再是并行提取阶段的主要阻塞点。

## 排障建议

### 进度长时间停在 `0/8`

先检查 `document-structure-analyzer` 是否还在进行内部多轮 tool-loop。在第一步完全结束前，checkpoint 可能不会推进到 `1/8`。

### Step 2a 很慢

检查 `data/conversations.db` 里最近的 `enzyme-kinetics-extractor` 记录。优化后的路径应该表现为更小的初始 user message，以及定向的 `Grep`/`Read`，而不是直接加载整篇文档。

### Step 2b 很慢

这比 `2a` 更常见，因为视觉 agent 仍然需要携带较大的多模态图片输入。

### Summary 在模型层完成了，但目录里没有文件

检查 `agent_id='enzyme-extraction-summary'` 的 `conversations` 和 `responses`。如果数据库里已经有 response，但 `enzyme-extraction-summary/3/` 目录还是空的，问题就在结果落盘，而不是模型生成本身。
