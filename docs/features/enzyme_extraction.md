# 酶动力学提取

从科学文献中提取酶反应数据的专用 SOP 流水线。

## 流水线架构

```
输入：科学文献（Markdown / HTML / Text）
                │
                ▼
    ┌─────────────────────────────┐
    │  Phase 1：文档结构分析       │
    │  - 提取并分类表格            │
    │  - 定位关键段落              │
    │  - token 用量减少 60-80%     │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │  Phase 2：靶向 LLM 提取     │
    │  - 酶变体、动力学参数        │
    │  - 实验条件、PDB ID          │
    └─────────────────────────────┘
```

## 快速使用

```bash
# 通过 SOP 运行（推荐）
gptase sop -p enzyme_extraction_pipeline -i data/paper.md -o output/

# 批处理
for file in data/papers/*.md; do
    gptase sop -p enzyme_extraction_pipeline -i "$file" -o output/
done

# 视觉图表分析
gptase run -d "分析此图表" -a vision-image-analyzer
```

## 输出格式

### JSON 结构

```json
{
  "reactions": [
    {
      "source_file": "paper.md",
      "enzyme_name": "Des27",
      "substrates": ["5-nitrobenzisoxazole"],
      "products": ["2-nitrophenol"],
      "conditions": {
        "temperature": "25 °C",
        "pH": "7.3",
        "buffer": "20 mM HEPES"
      },
      "kinetics": {
        "Km": null,          "Km_unit": "mM",
        "kcat": null,        "kcat_unit": "s^-1",
        "kcat_over_KM": 130, "kcat_over_KM_unit": "M^-1s^-1",
        "Tm": null,          "Tm_unit": "°C"
      },
      "yield_percent": null,
      "citations": [],
      "pdb_ids": []
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `enzyme_name` | str | 酶变体名称 |
| `substrates` / `products` | List[str] | 底物和产物 |
| `conditions` | object | 温度、pH、缓冲液、时间 |
| `kinetics` | object | Km, kcat, kcat/KM, Tm 及单位 |
| `pdb_ids` | List[str] | PDB 结构 ID |

特殊值：`"n.c."` = not calculable，`"n.d."` = not detected，存为 `null`。

## 涉及 Agent

| Agent | 用途 |
|---|---|
| `document-structure-analyzer` | Phase 1：结构分析、表格分类 |
| `enzyme-kinetics-extractor` | Phase 2：参数提取 |
| `vision-image-analyzer` | 从科学图表中提取数据 |

详见 [SOP API →](../reference-zh/api/sop.md) | [Agent API →](../reference-zh/api/agent.md)
