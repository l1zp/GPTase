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

Agent 名称解析与普通 Agent 加载保持一致，因此当底层目录存在时，
`vision-image-analyzer` 和 `vision_image_analyzer` 会命中同一套 eval 数据。

---

## 目录结构

每个 Agent 只有一个 eval 数据集，直接存放在 `evals/` 下：

```
.claude/agents/{agent_name}/
  {agent_name}.md           # Agent 定义
  evals/
    golden.yaml             # 该 Agent 的期望输出
    input.md                # 输入文件（可选，也可在 golden.yaml 中指定）
    images/                 # 图片（可选）
    output/                 # 缓存输出（可选，由 --save-output 生成）
```

**优点：** Agent 自包含，便于分享和版本控制。

---

## CLI

```bash
# 评估 Agent（使用缓存输出）
gptase eval -a vision-image-analyzer

# 实时运行 Agent 并评估（会调用 LLM API）
gptase eval -a vision-image-analyzer --live

# 保存实时输出到 agent 的 evals 目录
gptase eval -a vision-image-analyzer --live --save-output

# 保存 JSON 报告
gptase eval -a vision-image-analyzer --save report.json

# 连字符和下划线两种写法都支持
gptase eval -a vision_image_analyzer
```

**示例输出：**

```
Agent Evaluation: vision-image-analyzer
============================================================
Agent                          Schema   Facts    Score
------------------------------------------------------------
vision-image-analyzer          [OK]     5/5      1.00
------------------------------------------------------------
Overall: 5/5 key facts passed (1.00)
```

---

## Python API

### `run_eval()`

```python
from gptase.evals import run_eval

result = await run_eval(
    agent_name="vision-image-analyzer",  # 必填
    live=False,                          # 是否实时调用 LLM API
    save_output=False,                   # 是否保存输出
)
# 返回 EvalResult
```

### `EvalRunner`

```python
from gptase.evals import EvalRunner

runner = EvalRunner(agent_name="vision-image-analyzer")

# 评估 Agent
result = await runner.eval_agent(live=False)
```

### `EvalResult`

```python
@dataclass
class EvalResult:
    agent_name: str
    schema_valid: bool        # Schema 结构验证是否通过
    schema_error: str         # 验证失败时的错误信息
    total_facts: int          # golden.yaml 中定义的断言总数
    passed_facts: int         # 通过的断言数
    failure_reason: str       # 机器可判定的失败类型，成功时为空字符串
    failed_facts: List[str]   # 失败原因描述列表

    @property
    def score(self) -> float: ...   # passed_facts / total_facts
```

### 失败原因

当没有可评估的 JSON 输出时，`EvalResult.failure_reason` 会设置为以下值之一：

| `failure_reason` | 含义 |
|---|---|
| `cache_miss` | `evals/output/` 下没有找到缓存 JSON 文件 |
| `live_input_missing` | 实时评估时既没有 `input.md` 也没有图片输入 |
| `live_model_config_missing` | `--config` 指定的配置文件不存在 |
| `agent_init_error` | Agent 定义加载失败，尚未开始执行 |
| `agent_runtime_error` | 实时执行期间 Agent 返回错误结果 |
| `parse_error` | Agent 已执行，但输出无法解析为 JSON |

---

## `golden.yaml` 格式

每个 Agent 的 `golden.yaml` 只包含该 Agent 自己的 spec：

```yaml
# .claude/agents/vision-image-analyzer/evals/golden.yaml

schema: vision_analysis          # 对应 SCHEMA_MAP 中的键
input_file: input.md             # 输入文件（相对于此目录）

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
| `contains_all` | 每个期望值都必须作为子串出现在提取结果中；如果字段解析为列表，则只需出现在任一列表元素的字符串表示中 |
| `contains_any` | 任一期望值只要作为子串出现在提取结果中即可；如果字段解析为列表，则只需出现在任一列表元素的字符串表示中 |

### 字段路径 DSL

```
"statistics.total_variants"                  # 点分路径
"reactions[*].enzyme_name"                   # 通配符：返回所有元素的该字段列表
"reactions[enzyme_name=Des27].kinetics.kcat" # 过滤：找到匹配项后继续取字段
"reactions[0].enzyme_name"                   # 整数下标
```

键名中包含 `/`（如 `kcat/KM`）也可正确解析。

对于列表字段，`contains_all` 和 `contains_any` 会对每个列表元素的字符串表示做子串匹配。
这样更适合 CSV 文本块、自由文本摘要和提取表格单元格这类常见输出。

---

## 已支持的 Schema

| Schema 名称 | 对应 Agent | Pydantic 模型 |
|---|---|---|
| `document_structure` | `document_structure_analyzer` | `DocumentStructureOutput` |
| `enzyme_kinetics` | `enzyme_kinetics_table_extractor` | `EnzymeKineticsOutput` |
| `vision_analysis` | `vision-image-analyzer` / `vision_image_analyzer` | `VisionAnalysisOutput` |
| `enzyme_summary` | `enzyme_extraction_summary` | `EnzymeSummaryOutput` |

---

## 添加新评估

在 Agent 目录下创建 evals 目录：

```bash
# 1. 创建目录
mkdir -p .claude/agents/my-agent/evals

# 2. 创建 golden.yaml
cat > .claude/agents/my-agent/evals/golden.yaml << 'EOF'
schema: my_schema
input_file: input.md
key_facts:
  - { field: "result", condition: "contains", value: "expected" }
EOF

# 3. 放置输入文件
cp /path/to/input.md .claude/agents/my-agent/evals/input.md

# 4. 验证
gptase eval -a my-agent --live
```
