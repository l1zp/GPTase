# Vision Image Analyzer

Detailed documentation for analyzing scientific figures and extracting tabular data using vision models.

## Overview

The Vision Image Analyzer is a tool for analyzing scientific figures and extracting tabular data using vision models (e.g., Qwen3-VL). It supports batch processing of multiple images and outputs structured data in CSV and JSON formats.

## Quick Start

```bash
# Analyze specific image (default: Image 7 / Fig 3a)
python examples/vision_image_analyzer.py

# Analyze different image
python examples/vision_image_analyzer.py --image-number 9

# Analyze all relevant images
python examples/vision_image_analyzer.py --all

# Limit to first 5 images
python examples/vision_image_analyzer.py --all --max-images 5

# Use custom configuration file
python examples/vision_image_analyzer.py --config config/llm_config.qwen_vl.example.json

# Specify custom CSV path
python examples/vision_image_analyzer.py --csv-path data/analysis/custom_images.csv
```

## Configuration

### Configuration File

The tool reads configuration from JSON files (default: `config/llm_config.qwen_vl.example.json`):

```json
{
  "model_name": "Qwen3-VL-235B-A22B-Thinking",
  "api_key": "your-api-key",
  "base_url": "https://api.example.com/v1/",
  "temperature": 1,
  "max_tokens": 16384
}
```

### Configuration Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `model_name` | str | Vision model identifier | Yes |
| `api_key` | str | API authentication key | Yes |
| `base_url` | str | API endpoint URL | Yes |
| `temperature` | float | Sampling temperature (0-2) | No |
| `max_tokens` | int | Maximum tokens in response | No |

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--image-number` | Specific image number to analyze | 7 |
| `--all` | Analyze all relevant images | False |
| `--max-images` | Limit number of images to process | None |
| `--config` | Path to configuration file | `config/llm_config.qwen_vl.example.json` |
| `--csv-path` | Path to CSV with image information | `data/analysis/listov2025_images.csv` |

## Input Format

### CSV File Structure

The tool reads image information from a CSV file with the following columns:

```csv
image_number,image_path,description,figure,has_table,contains_kinetics
7,data/papers/listov2025/img/Fig3.png,Fig 3a: Enzyme kinetics,3,1,1
9,data/papers/listov2025/img/Fig4.png,Fig 4: Mutational analysis,4,1,1
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `image_number` | int | Sequential image identifier |
| `image_path` | str | Path to image file (PNG, JPG, etc.) |
| `description` | str | Brief description of figure content |
| `figure` | int | Figure number in paper |
| `has_table` | bool | Whether image contains tabular data |
| `contains_kinetics` | bool | Whether image contains kinetic data |

## Output Format

### JSON Output

File: `data/image_analysis_results.json`

```json
{
  "analyses": [
    {
      "image_number": 7,
      "image_path": "data/papers/listov2025/img/Fig3.png",
      "description": "Fig 3a: Enzyme kinetics",
      "analysis": {
        "figure_type": "table",
        "table_data": {
          "columns": ["Variant", "kcat (s⁻¹)", "KM (mM)", "kcat/KM (M⁻¹s⁻¹)"],
          "rows": [
            ["WT", "120", "0.5", "240000"],
            ["D27A", "45", "1.2", "37500"]
          ]
        },
        "extracted_values": {...}
      }
    }
  ]
}
```

### CSV Output

File: `data/image_analysis_extracted_tables.csv`

```csv
image_number,figure,variant,kcat,KM,kcat_over_KM
7,3,WT,120,0.5,240000
7,3,D27A,45,1.2,37500
```

## Prompt Engineering

The tool uses specialized prompts for scientific figure analysis:

### Automatic Figure Type Detection

The tool automatically detects:
- **Tables**: Structured data in rows/columns
- **Plots**: Line graphs, bar charts, scatter plots
- **Diagrams**: Schematics, workflows, mechanisms
- **Mixed figures**: Combination of multiple types

### Data Extraction Strategy

**For Tables:**
1. Identify all columns and headers
2. Extract all numerical values
3. Preserve units and annotations
4. Handle merged cells and multi-row headers

**For Plots:**
1. Identify axes and labels
2. Extract data points if visible
3. Describe trends and patterns
4. Note any annotations or legends

**For Diagrams:**
1. Describe overall structure
2. Identify key components
3. Explain relationships
4. Note any labels or annotations

### Enzyme Kinetics Support

Specialized support for enzyme kinetics data:
- Variants and substitutions
- Kinetic parameters (kcat, KM, kcat/KM, Tm, Vmax)
- Mutations and modifications
- Experimental conditions

**Example Prompt:**
```
Analyze this scientific figure and extract all tabular data.

If this is an enzyme kinetics table:
- Extract ALL variants (every row)
- Include all kinetic parameters (kcat, KM, kcat/KM, Tm, Vmax)
- Note units for each parameter
- Preserve uncertainty values (±, n.c., n.d.)

Output format: CSV with clear column headers.
```

## Advanced Usage

### Custom Prompt Templates

Modify the prompt in `examples/vision_image_analyzer.py`:

```python
custom_prompt = """
Analyze this figure and extract:
1. Figure type (table/plot/diagram)
2. All numerical data
3. Labels and annotations
4. Any relationships or patterns

Output in structured CSV format.
"""

result = await analyzer.analyze_image(
    image_path,
    prompt=custom_prompt
)
```

### Batch Processing with Filtering

```bash
# Analyze only figures with tables
python examples/vision_image_analyzer.py --all --filter has_table==1

# Analyze only kinetic data figures
python examples/vision_image_analyzer.py --all --filter contains_kinetics==1
```

### Integration with Other Tools

```python
from src.tools.vision_tool import VisionTool
from src.utils import default_manager

manager = default_manager()
analyzer = VisionImageAnalyzerTool(model_manager=manager)

# Analyze single image
result = await analyzer.execute(
    image_path="data/papers/img/Fig3.png",
    extract_tables=True
)

# Access extracted data
table_data = result.data.get("table_data")
```

## Performance Considerations

### Image Size

- **Optimal**: 1024x1024 to 2048x2048 pixels
- **Maximum**: 4096x4096 pixels (model-dependent)
- **Recommendation**: Resize large images before processing

### Processing Time

Per-image processing time varies:
- **Simple tables**: 2-5 seconds
- **Complex figures**: 5-15 seconds
- **Multi-panel figures**: 10-30 seconds

### Token Usage

Vision models typically consume:
- **Base tokens**: ~1000 tokens per image
- **Response tokens**: 500-2000 tokens depending on complexity
- **Total**: 1500-3000 tokens per image

## Best Practices

### Image Preparation

1. **High quality**: Use high-resolution scans or screenshots
2. **Clean background**: Remove noise and artifacts if possible
3. **Clear text**: Ensure text is readable and not rotated
4. **Proper cropping**: Crop to include only relevant figure content

### CSV File Organization

1. **Sequential numbering**: Use consecutive image_number values
2. **Accurate paths**: Verify all image_path values are correct
3. **Descriptive labels**: Use clear, specific descriptions
4. **Consistent formatting**: Use standard date/number formats

### Result Validation

1. **Check outputs**: Review JSON and CSV files for completeness
2. **Verify units**: Ensure units are correctly extracted
3. **Compare with source**: Cross-check extracted data with original figure
4. **Handle errors**: Review any error messages or warnings

## Troubleshooting

### Issue: Image not found

**Error**: `FileNotFoundError: image_path`

**Solution**:
```bash
# Verify image file exists
ls -la data/papers/listov2025/img/Fig3.png

# Check CSV path is correct
head -5 data/analysis/listov2025_images.csv

# Use absolute paths if needed
python examples/vision_image_analyzer.py --csv-path /full/path/to/images.csv
```

### Issue: API authentication error

**Error**: `AuthenticationError: Invalid API key`

**Solution**:
```bash
# Check API key in config
cat config/llm_config.qwen_vl.example.json

# Set API key via environment variable
export API_KEY="your-actual-api-key"

# Verify key format (no extra spaces, quotes, etc.)
```

### Issue: Poor extraction quality

**Possible causes**:
1. Low image resolution
2. Complex table layout
3. Handwritten or unclear text

**Solution**:
1. Pre-process images (increase resolution, enhance contrast)
2. Use custom prompts for specific figure types
3. Manually verify and correct extracted data
4. Consider manual annotation for complex figures

### Issue: Token limit exceeded

**Error**: `TokenLimitError: Maximum tokens exceeded`

**Solution**:
```json
// Increase max_tokens in config
{
  "max_tokens": 32768  // Increase from 16384
}
```

Or split analysis into multiple calls.

## Examples

### Example 1: Analyze Single Figure

```bash
python examples/vision_image_analyzer.py --image-number 7
```

Output:
```
[INFO] Analyzing image 7: data/papers/listov2025/img/Fig3.png
[INFO] Figure type: Table
[INFO] Extracted 5 variants with kinetic data
[INFO] Results saved to data/image_analysis_results.json
[INFO] CSV saved to data/image_analysis_extracted_tables.csv
```

### Example 2: Batch Process All Figures

```bash
python examples/vision_image_analyzer.py --all --max-images 10
```

Output:
```
[INFO] Processing 10 images from data/analysis/listov2025_images.csv
[INFO] [1/10] Analyzing image 7... Table (5 variants)
[INFO] [2/10] Analyzing image 9... Plot (kinetics comparison)
[INFO] [3/10] Analyzing image 12... Diagram (mechanism)
...
[INFO] Complete! Processed 10 images in 87.3 seconds
[INFO] Total variants extracted: 47
[INFO] Results saved to data/image_analysis_results.json
```

### Example 3: Custom Configuration

```bash
python examples/vision_image_analyzer.py \
  --config config/llm_config.custom.json \
  --csv-path data/analysis/custom_images.csv \
  --all
```

## Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Main project documentation
- [docs/features/enzyme_extraction.md](../features/enzyme_extraction.md) - Enzyme data extraction
- [examples/vision_image_analyzer.py](../../examples/vision_image_analyzer.py) - Implementation
