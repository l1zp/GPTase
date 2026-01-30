# Vision Image Analyzer 使用指南

## 功能概述

`vision_image_analyzer.py` 是一个使用 Qwen3-VL 多模态大模型分析科学图表的工具，支持：

1. **图片内容理解** - 识别图表类型、提取关键信息
2. **表格数据提取** - 自动识别表格并输出 CSV 格式
3. **结构化分析** - 提取酶变体名称、动力学参数、PDB ID 等
4. **思考模式** - 启用模型推理能力进行深度分析

## 快速开始

### 安装依赖

```bash
pip install openai
```

### 配置 API

**方式 1: 环境变量（推荐）**
```bash
export QWEN_VL_API_KEY="your-api-key"
export QWEN_VL_BASE_URL="https://llmapi.paratera.com/v1/"
python examples/vision_image_analyzer.py
```

**方式 2: 修改脚本**
编辑 `examples/vision_image_analyzer.py`，直接设置：
```python
api_key = "sk-your-key-here"
base_url = "https://llmapi.paratera.com/v1/"
```

## 使用方法

### 基础用法

```bash
# 使用默认配置（分析前 3 张相关图片）
python examples/vision_image_analyzer.py

# 修改分析数量
# 编辑脚本中的 max_images 参数
max_images = 5  # 分析 5 张图片
```

### 输入数据格式

CSV 文件应包含以下列：
- `image_path`: Markdown 格式的图片路径（如 `![](images/abc.jpg)`）
- `is_relevant`: 是否相关（true/false）
- `caption`: 图表标题
- `topics`: 相关主题
- `description`: 描述信息

示例：
```csv
image_number,image_path,is_relevant,caption,topics
1,![](images/fig1.jpg),true,"Fig. 1 | Enzyme kinetics",kinetics|enzymes
2,![](images/fig2.jpg),true,"Fig. 2 | Structure analysis",crystallography
```

## 输出结果

### 1. JSON 分析结果

保存到 `data/image_analysis_results.json`，包含：
- `image_path`: 图片路径
- `prompt`: 使用的提示词
- `content`: 模型的完整分析
- `model`: 使用的模型
- `usage`: Token 使用统计

### 2. CSV 表格数据（如果提取到）

保存到 `data/image_analysis_extracted_tables.csv`，格式：
```csv
# Image 6: images/fig2_panel_a.jpg
Variant,kcat (s^-1),KM (mM),kcat/KM (M^-1s^-1),Tm (°C)
Des27,1.2 ± 0.1,0.5 ± 0.05,2400 ± 200,55.3
Des27.7,3.5 ± 0.2,0.3 ± 0.03,11667 ± 500,60.1

# Image 9: images/fig3_panel_c.jpg
Condition,Bound (%),Unbound (%),Reactive (%)
Des27,15,75,10
Des27.7,35,50,24
```

## 提示词结构

工具使用英文提示词，包含以下部分：

### 基础分析要求
1. **Figure Type** - 图表类型（流程图、数据图、结构图、表格等）
2. **Main Content** - 主要内容和关键要素
3. **Data Information** - 数据信息（数值、趋势）
4. **Experimental Methods** - 实验方法和技术细节
5. **Conclusions** - 结论和关键发现
6. **Enzyme Variants** - 酶变体名称
7. **Kinetic Parameters** - 动力学参数（kcat, KM, kcat/KM, Tm, Vmax）
8. **PDB IDs** - 蛋白质结构数据库 ID

### 表格数据提取

对于表格或数据图表，模型会：
- 自动识别表格结构
- 提取所有数据行
- 保留数值和单位（如 `1.5 ± 0.2`、`n.d.`、`n.c.`）
- 输出为标准 CSV 格式

示例输出：
```csv
Variant,kcat (s^-1),KM (mM),kcat/KM (M^-1s^-1),Tm (°C)
Des27,1.2,0.5,2400,55
Des27.7,3.5,0.3,11667,60
```

## 实际应用场景

### 1. 酶动力学数据提取

输入：包含酶动力学图表的论文图片
输出：结构化的动力学参数（kcat, KM, kcat/KM, Tm）

### 2. 突变表格解析

输入：酶突变效应表格
输出：每个突变体的活性变化数据

### 3. 结构对比分析

输入：蛋白质结构对比图
输出：PDB ID、r.m.s.d. 值、关键残基变化

### 4. 实验流程理解

输入：实验设计流程图
输出：实验步骤、技术方法、关键发现

## 配置选项

### 脚本参数

```python
# CSV 文件路径
csv_path = "data/analysis/listov2025_structure_analysis_images.csv"

# 图片基础目录
base_dir = Path("data/listov2025")

# 分析数量限制
max_images = 3

# 是否只分析相关图片
relevant_only = True
```

### 模型配置

在 `config/llm_config.qwen_vl.example.json` 中：

```json
{
  "model_name": "Qwen3-VL-235B-A22B-Thinking",
  "api_key": "your-api-key",
  "temperature": 1.0,
  "max_tokens": 16384,
  "enable_thinking": true,
  "provider_config": {
    "stream": true,
    "extra_body": {
      "enable_thinking": true
    }
  }
}
```

## 性能优化

### Token 使用控制

- 每张图片约使用 2000-3000 tokens
- 调整 `max_images` 控制总消耗
- 表格图片可能使用更多 tokens

### 批量处理建议

```python
# 分批处理大量图片
batch_size = 10
for i in range(0, len(images), batch_size):
    batch = images[i:i+batch_size]
    # 处理当前批次
```

## 故障排除

### 常见问题

**1. API 连接失败**
```
Error: Connection timeout
解决：检查 base_url 和网络连接
```

**2. 图片文件未找到**
```
Error: Image file not found
解决：检查 base_dir 和图片路径是否正确
```

**3. 未提取到 CSV 数据**
```
Statistics: 3/3 images analyzed successfully
           0 tables extracted in CSV format
原因：图片不是表格类型，或模型未识别出表格结构
```

**4. Token 不足**
```
Error: Maximum tokens exceeded
解决：增加 max_tokens 配置或缩短提示词
```

## 扩展开发

### 添加自定义提示词

编辑 `analyze_scientific_figure_prompt()` 函数：

```python
def analyze_scientific_figure_prompt(image_info: Dict[str, Any]) -> str:
    prompt_parts = [
        "Custom analysis prompt here...",
    ]
    return "\n".join(prompt_parts)
```

### 添加新的输出格式

编辑 `main()` 函数，添加自定义处理：

```python
# 自定义数据处理
if custom_condition:
    save_to_custom_format(result)
```

## 示例输出

### 分析结果示例

```json
{
  "image_path": "data/listov2025/images/fig2.jpg",
  "prompt": "Please analyze this scientific figure...",
  "content": "1. **Figure Type**\nStructural diagram...\n\n2. **Main Content**\n...",
  "model": "Qwen3-VL-235B-A22B-Thinking",
  "usage": {
    "prompt_tokens": 505,
    "completion_tokens": 2130,
    "total_tokens": 2635
  }
}
```

### CSV 提取示例

```csv
# Image 14: images/fig4.jpg
Variant,Mutations,Tm (°C),kcat/KM (M^-1s^-1)
Des27.7,8,60.1,11667
Des27.7-Δ136,7,58.5,8500
Des27.7-Δ216,7,57.2,7200
```

## 技术细节

### 模型能力

- **Qwen3-VL-235B-A22B-Thinking**: 多模态视觉语言大模型
- 支持 JPG、PNG 等常见图片格式
- Base64 编码传输图片数据
- 思考模式提供更深入的分析

### API 兼容性

- 使用 OpenAI 兼容的 API 接口
- 支持 streaming 和非 streaming 模式
- 标准 chat completion 格式

## 相关文档

- [CSV Export Guide](CSV_EXPORT_GUIDE.md) - CSV 导出工具使用
- [Enzyme Extraction Workflow](ENZYME_EXTRACTION_WORKFLOW.md) - 酶提取工作流
- [Technical Features](TECHNICAL_FEATURES.md) - 技术特性说明

## 更新日志

### v1.0 (2025-01-30)
- 初始版本
- 支持图片内容分析
- 支持表格数据提取
- 英文提示词
- CSV 格式输出
