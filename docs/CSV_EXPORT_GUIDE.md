# CSV 导出工具使用指南

## 功能概述

`json_to_csv.py` 是一个统一的 CSV 导出工具，支持两种模式：

1. **反应数据导出** - 将酶反应提取结果转换为 CSV
2. **图片信息导出** - 将文档结构分析中的图片信息转换为 CSV

## 使用方法

### 模式选择

```bash
# 自动检测模式（推荐）
python pipelines/json_to_csv.py -i data/analysis/listov2025_structure_analysis.json
python pipelines/json_to_csv.py -i data/extraction/listov2025_extraction.json

# 显式指定模式
python pipelines/json_to_csv.py --mode reactions
python pipelines/json_to_csv.py --mode images

# 查看帮助
python pipelines/json_to_csv.py --help
```

### 反应数据导出

```bash
# 默认导出（使用默认输入文件）
python pipelines/json_to_csv.py

# 指定输入输出文件
python pipelines/json_to_csv.py -i data/extraction/listov2025_extraction.json -o reactions.csv

# 启用数据验证
python pipelines/json_to_csv.py --validate

# 包含 PDB IDs
python pipelines/json_to_csv.py --include-pdb-ids

# 显示统计信息
python pipelines/json_to_csv.py --stats
```

### 图片信息导出

```bash
# 自动检测（从 analysis JSON）
python pipelines/json_to_csv.py -i data/analysis/listov2025_structure_analysis.json

# 显式指定图片模式
python pipelines/json_to_csv.py -i data/analysis/listov2025_structure_analysis.json --mode images

# 显示统计信息
python pipelines/json_to_csv.py -i data/analysis/listov2025_structure_analysis.json --mode images --stats

# 指定输出文件
python pipelines/json_to_csv.py -i data/analysis/listov2025_structure_analysis.json -o images.csv --mode images
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-i, --input` | 输入 JSON 文件路径 | `data/extraction/listov2025_extraction.json` |
| `-o, --output` | 输出 CSV 文件路径 | 与输入文件同路径，`.csv` 扩展名 |
| `--mode` | 导出模式：`auto`, `reactions`, `images` | `auto` |
| `--stats` | 显示统计信息 | False |
| `--validate` | 启用数据验证（仅反应模式） | False |
| `--include-pdb-ids` | 包含 PDB IDs 列（仅反应模式） | False |

## 输出格式

### 反应数据 CSV

包含以下字段：
- `enzyme_name` - 酶名称
- `substrates` - 底物
- `products` - 产物
- `mutations` - 突变（用 `|` 分隔）
- `kcat`, `KM`, `kcat_over_KM`, `Tm` - 动力学参数
- `kcat_unit`, `Km_unit`, `Tm_unit` - 单位
- `temperature`, `pH`, `buffer`, `time` - 反应条件
- `yield_percent` - 产率
- `citations` - 引用
- `pdb_ids` (可选) - PDB 编号
- `pdb_is_new` (可选) - PDB 是否为新

### 图片信息 CSV

包含以下字段：
- `image_number` - 图片序号
- `line_number` - 在文档中的行号
- `image_path` - 图片文件路径
- `figure_number` - 图片编号（如 1, 2, 3）
- `caption` - 图片说明文字
- `is_relevant` - 是否与酶反应相关（true/false）
- `topics` - 主题标签（用 `|` 分隔）
- `description` - LLM 生成的图片描述
- `enzyme_variants` - 酶变体（用 `|` 分隔）
- `data_types` - 数据类型（用 `|` 分隔）
- `key_findings` - 关键发现（用 `|` 分隔）

## 自动检测逻辑

脚本会根据 JSON 内容自动检测模式：

```python
if 'reactions' in data:
    mode = 'reactions'
elif 'images' in data and 'sections' in data:
    mode = 'images'
else:
    # 无法检测，需要手动指定 --mode
```

## 统计信息示例

### 反应数据统计

```
Statistics:
   Total reactions: 32
   Reactions with kcat: 17
   Reactions with Km: 17
   Reactions with Tm: 29

   kcat statistics:
      Min: 0.03 s⁻¹
      Max: 30.00 s⁻¹
      Mean: 3.63 s⁻¹
```

### 图片信息统计

```
Image Statistics:
   Total images: 60
   Images with captions: 19
   Images with figure numbers: 9
   Relevant images (LLM): 9

   Top topics:
      - catalytic efficiency: 2
      - kinetic analysis: 2
      - enzyme design workflow: 1
```

## 完整工作流程示例

### 场景 1: 提取酶反应数据

```bash
# Step 1: 运行提取（包含 Phase 1 结构分析）
python examples/reaction_extractor.py

# Step 2: 导出反应数据到 CSV
python pipelines/json_to_csv.py --stats

# Step 3: 查看结果
# Output: data/extraction/listov2025_extraction.csv
```

### 场景 2: 导出图片信息

```bash
# Step 1: 运行提取（Phase 1 已生成结构分析）
# 已完成，文件在: data/analysis/listov2025_structure_analysis.json

# Step 2: 导出图片信息到 CSV
python pipelines/json_to_csv.py -i data/analysis/listov2025_structure_analysis.json --mode images --stats

# Step 3: 查看结果
# Output: data/analysis/listov2025_structure_analysis.csv
```

### 场景 3: 批量处理

```bash
# 导出所有数据
python pipelines/json_to_csv.py --mode reactions -o reactions.csv
python pipelines/json_to_csv.py --mode images -i data/analysis/listov2025_structure_analysis.json -o images.csv

# 或者使用自动检测
python pipelines/json_to_csv.py -i data/extraction/listov2025_extraction.json -o reactions.csv
python pipelines/json_to_csv.py -i data/analysis/listov2025_structure_analysis.json -o images.csv
```

## 注意事项

1. **文件编码**: CSV 文件使用 UTF-8 编码
2. **多值字段**: 使用 `|` 分隔（如 mutations, topics）
3. **空值**: 空字段显示为空字符串
4. **特殊值**:
   - `n.c.` - not calculable（无法计算）
   - `n.d.` - not detected（未检测到）
   - `n.m.` - not mentioned（未提及）

## 故障排除

### 问题：无法检测 JSON 类型

```
Error: Unable to detect JSON type. Please specify --mode
```

**解决方案**: 手动指定模式
```bash
python pipelines/json_to_csv.py --mode reactions
python pipelines/json_to_csv.py --mode images
```

### 问题：模式不匹配警告

```
Warning: Mode 'images' may not match JSON type 'extraction'
```

**解决方案**: 使用自动检测模式或确保输入文件正确
```bash
# 使用自动检测
python pipelines/json_to_csv.py --mode auto

# 或使用正确的输入文件
python pipelines/json_to_csv.py -i data/analysis/listov2025_structure_analysis.json --mode images
```

## 相关文件

- 脚本位置：`pipelines/json_to_csv.py`
- 反应数据输入：`data/extraction/listov2025_extraction.json`
- 结构分析输入：`data/analysis/listov2025_structure_analysis.json`
- 输出 CSV 文件：根据输入文件自动命名
