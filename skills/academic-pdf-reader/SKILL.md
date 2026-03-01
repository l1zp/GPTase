---
name: academic-pdf-reader
description: 阅读和分析学术 PDF 论文、专利或技术文档。提取结构化内容包括元信息、实验方法、关键数据和图表描述。当需要处理 PDF 文件时自动使用此 skill。
---

# Academic PDF Reader

## Overview

提供从学术 PDF 中提取和分析结构化内容的系统方法。支持论文、专利、技术报告等格式。

## When to Use

- 用户提供了 PDF 文件路径
- 需要从论文中提取实验数据、方法或结论
- 需要分析文档结构（章节、图表、参考文献）

## Workflow

### Step 1: PDF → Markdown 提取

使用 MinerU 进行高质量 PDF 转换（保留表格和公式结构）：

```bash
# 基础提取
mineru -p /path/to/paper.pdf -o /tmp/mineru_output/

# 如果 MinerU 不可用，降级使用 markitdown
markitdown /path/to/paper.pdf > /tmp/paper_output.md
```

### Step 2: 阅读和分析

用 text_editor 打开提取的 Markdown 文件，依次识别：

1. **元信息**：标题、作者、期刊/会议、年份、DOI
2. **摘要和关键词**
3. **章节结构**：按 heading 层级梳理文档大纲
4. **方法部分**：实验条件、材料、步骤
5. **结果部分**：关键数据、表格、图表描述
6. **参考文献**：提取引用列表

### Step 3: 图表处理

如果文档包含重要图表：
- 检查 MinerU 输出目录中的 `images/` 文件夹
- 描述每个图表的内容和关键发现
- 对表格数据进行结构化提取

### Step 4: 结构化输出

按以下格式整理最终输出：

```json
{
  "metadata": {
    "title": "...",
    "authors": ["..."],
    "journal": "...",
    "year": 2024,
    "doi": "..."
  },
  "abstract": "...",
  "sections": ["Introduction", "Methods", "Results", "Discussion"],
  "key_findings": ["..."],
  "methods": {
    "materials": ["..."],
    "procedures": ["..."]
  },
  "data": {
    "tables": [...],
    "figures": [...]
  }
}
```

## Tips

- 对于表格密集的论文，优先使用 MinerU（结构保留更好）
- 对于纯文本论文，markitdown 也足够
- 如果 PDF 是扫描件，MinerU 支持 OCR 模式
- 多栏 PDF 需要注意文本提取顺序
