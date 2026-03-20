# Eval API

> [首页](../README.md) → [API](.) → Eval

**相关文件：** `gptase/evals/__init__.py`, `gptase/evals/assertions.py`, `gptase/evals/runner.py`, `gptase/evals/report.py`, `gptase/evals/schemas.py`

---

## 概述

Eval 框架用于评估 Agent 输出质量，分三个层次：

| 层次 | 内容 | 实现 |
|---|---|---|
| **Schema 验证** | 输出 JSON 结构是否正确 | Pydantic 模型（`schemas.py`） |
| **关键事实断言** | 重要数值是否存在且正确 | `golden.yaml` + `assertions.py` |
| **完整性度量** | 预期实体召回率 | `length_gte` / `contains_all` 条件 |

不使用 LLM-as-judge，避免额外 API 消耗和非确定性。

---

## CLI

```bash
# 列出所有可用的评估论文
gptase eval --list

# 对所有 Agent 运行评估（使用缓存输出，无 API 消耗）
gptase eval -p listov2025

# 仅评估单个 Agent
gptase eval -p listov2025 -a enzyme_kinetics_extractor

# 实时运行 Agent（会调用 LLM API）
gptase eval -p listov2025 --live

# 指定自定义缓存目录
gptase eval -p listov2025 --cache-dir data/output/listov2025/enzyme_extraction_pipeline_20260319_232337

# 保存 JSON 报告
gptase eval -p listov2025 --save report.json
```

**示例输出：**

```
Agent Evaluation: listov2025
============================================================
Agent                          Schema   Facts    Score
------------------------------------------------------------
document_structure_analyzer    [OK]     3/3      1.00
enzyme_kinetics_extractor      [OK]     5/5      1.00
vision_image_analyzer          [OK]     1/1      1.00
enzyme_extraction_summary      [OK]     2/2      1.00
------------------------------------------------------------
Overall: 11/11 key facts passed (1.00)
```

---

## Python API

### `run_eval()`

```python
from gptase.evals import run_eval

results = await run_eval(
    paper_id="listov2025",     # 必填：data/evals/ 下的子目录名
    agent_name=None,           # 可选：只评估单个 Agent
    live=False,                # 是否实时调用 LLM API
    cache_dir=None,            # 自定义缓存目录路径
)
# 返回 List[EvalResult]
```

### `EvalRunner`

```python
from gptase.evals import EvalRunner

runner = EvalRunner(
    paper_id="listov2025",
    cache_dir=None,   # None 时自动找 data/output/{paper_id}/ 下最新的目录
)

# 评估所有 Agent
results = await runner.eval_all(live=False)

# 评估单个 Agent
result = await runner.eval_agent("enzyme_kinetics_extractor", live=False)
```

### `EvalResult`

```python
@dataclass
class EvalResult:
    agent_name: str
    paper_id: str
    schema_valid: bool        # Schema 结构验证是否通过
    schema_error: str         # 验证失败时的错误信息
    total_facts: int          # golden.yaml 中定义的断言总数
    passed_facts: int         # 通过的断言数
    failed_facts: List[str]   # 失败原因描述列表

    @property
    def score(self) -> float: ...   # passed_facts / total_facts
```

---

## 数据目录

```
data/evals/
  {paper_id}/
    golden.yaml          # 人工标注的期望值

data/output/
  {paper_id}/
    {plan_id}_{timestamp}/        # Pipeline 运行输出（缓存来源）
      document_structure_analyzer/
        1_parsed.json
      enzyme_kinetics_extractor/
        2a_parsed.json
      vision_image_analyzer/
        2b_parsed.json
      enzyme_extraction_summary/
        3_parsed.json
```

---

## `golden.yaml` 格式

```yaml
paper_id: listov2025
input_file: data/input/listov2025/listov2025.md       # 实时运行时使用
input_images_dir: data/input/listov2025/images        # 实时运行时使用

agents:
  enzyme_kinetics_extractor:
    schema: enzyme_kinetics          # 对应 SCHEMA_MAP 中的键
    key_facts:
      - { field: "reactions", condition: "length_gte", value: 25 }
      - { field: "reactions[*].enzyme_name", condition: "contains_all",
          values: ["Des27", "Des27.7"] }
      - { field: "reactions[enzyme_name=Des27].kinetics.kcat/KM",
          condition: "approx_eq", value: 131, tolerance: 0.15 }
```

### 支持的条件

| 条件 | 语义 |
|---|---|
| `length_gte` | `len(field) >= value` |
| `gte` | `field >= value` |
| `approx_eq` | `abs(actual - expected) / expected <= tolerance`（默认 0.15） |
| `contains` | `value in str(field)` |
| `contains_all` | values 中所有元素均存在于列表中 |
| `contains_any` | values 中至少一个元素存在于列表中 |

### 字段路径 DSL

```
"statistics.total_variants"                  # 点分路径
"reactions[*].enzyme_name"                   # 通配符：返回所有元素的该字段列表
"reactions[enzyme_name=Des27].kinetics.kcat" # 过滤：找到匹配项后继续取字段
"reactions[0].enzyme_name"                   # 整数下标
```

键名中包含 `/`（如 `kcat/KM`）也可正确解析。

---

## 已支持的 Schema

| Schema 名称 | 对应 Agent | Pydantic 模型 |
|---|---|---|
| `document_structure` | `document_structure_analyzer` | `DocumentStructureOutput` |
| `enzyme_kinetics` | `enzyme_kinetics_extractor` | `EnzymeKineticsOutput` |
| `vision_analysis` | `vision_image_analyzer` | `VisionAnalysisOutput` |
| `enzyme_summary` | `enzyme_extraction_summary` | `EnzymeSummaryOutput` |

---

## 添加新论文

只需创建一个文件，无需改动代码：

```bash
# 1. 创建 golden 文件
mkdir -p data/evals/<paper_id>
vim data/evals/<paper_id>/golden.yaml

# 2. 放置输入文件（实时运行时需要）
mkdir -p data/input/<paper_id>/images

# 3. 验证
gptase eval --list              # 应显示新论文
gptase eval -p <paper_id>       # 使用缓存运行
```

`gptase eval --list` 自动发现 `data/evals/` 下所有包含 `golden.yaml` 的子目录。
