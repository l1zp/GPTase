#!/usr/bin/env python3
"""
Vision Image Analyzer - Analyze image content using Qwen3-VL model

This example demonstrates how to:
1. Read image information from CSV files
2. Use OpenAI-compatible API to call Qwen3-VL model
3. Enable thinking mode for deep analysis
4. Process local image files (JPG, PNG, etc.)
5. Extract tabular data and output in CSV format
"""

import argparse
import base64
import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import openai
except ImportError:
    print("请先安装 openai 包: pip install openai")
    exit(1)


def encode_image_to_base64(image_path: str) -> str:
    """Encode local image file to base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def extract_image_path_from_markdown(markdown_path: str) -> str:
    """Extract actual path from Markdown image path format

    Example: ![](images/abc.jpg) -> images/abc.jpg
    """
    if markdown_path.startswith("![]("):
        return markdown_path[4:-1]  # Remove ![]( and )
    return markdown_path


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file.

    Args:
        config_path: Path to configuration JSON file

    Returns:
        Configuration dictionary
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_images_from_csv(csv_path: str,
                         relevant_only: bool = True) -> List[Dict[str, Any]]:
    """Load image information from CSV file

    Args:
        csv_path: Path to CSV file
        relevant_only: Whether to only load relevant images (is_relevant=True)

    Returns:
        List of image information dictionaries
    """
    images = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 过滤：只处理相关图片
            if relevant_only and row.get("is_relevant", "false").lower() != "true":
                continue

            # 提取图片路径
            image_markdown = row.get("image_path", "")
            if not image_markdown or image_markdown == "![]()":
                continue

            actual_path = extract_image_path_from_markdown(image_markdown)

            images.append({
                "image_number": row.get("image_number", ""),
                "figure_number": row.get("figure_number", ""),
                "caption": row.get("caption", ""),
                "image_path": actual_path,
                "topics": row.get("topics", ""),
                "description": row.get("description", ""),
            })

    return images


def analyze_image_with_vision(
    client: openai.OpenAI,
    image_path: str,
    prompt:
    str = "Please describe this image in detail, including all text, charts, data, and other information.",
    model: str = "Qwen3-VL-235B-A22B-Thinking",
) -> Dict[str, Any]:
    """Analyze image using vision model

    Args:
        client: OpenAI client instance
        image_path: Path to image file
        prompt: Analysis prompt
        model: Model name

    Returns:
        Dictionary containing analysis results
    """
    # Check if file exists
    if not os.path.exists(image_path):
        return {
            "error": f"Image file not found: {image_path}",
            "image_path": image_path,
        }

    # Encode image
    base64_image = encode_image_to_base64(image_path)

    # Build request
    messages = [{
        "role":
        "user",
        "content": [{
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            }
        }, {
            "type": "text",
            "text": prompt
        }]
    }]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )

        result = {
            "image_path": image_path,
            "prompt": prompt,
            "content": response.choices[0].message.content,
            "model": model,
            "usage": {
                "prompt_tokens":
                response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens":
                response.usage.completion_tokens if response.usage else 0,
                "total_tokens":
                response.usage.total_tokens if response.usage else 0,
            } if response.usage else {}
        }

        return result

    except Exception as e:
        return {
            "error": str(e),
            "image_path": image_path,
        }


def analyze_scientific_figure_prompt(image_info: Dict[str, Any]) -> str:
    """Generate analysis prompt for scientific figures

    Args:
        image_info: Dictionary containing image information

    Returns:
        Analysis prompt string
    """
    prompt_parts = [
        "Please analyze this scientific figure in detail and extract the following information:",
    ]

    # Add caption if available
    if image_info.get("caption"):
        prompt_parts.append(f"\nFigure Caption:\n{image_info['caption']}")

    # Add topics if available
    if image_info.get("topics"):
        prompt_parts.append(f"\nRelated Topics:\n{image_info['topics']}")

    prompt_parts.extend([
        "\nPlease extract and provide structured output for:",
        "1. **Figure Type** (e.g., flowchart, data plot, structural diagram, table, etc.)",
        "2. **Main Content and Key Elements**",
        "3. **Data Information** (if the figure contains data tables or plots, extract ALL numerical values)",
        "4. **Experimental Methods or Technical Details**",
        "5. **Conclusions or Key Findings**",
        "6. **Enzyme Variant Names** (if mentioned)",
        "7. **Kinetic Parameters** (if available, such as kcat, KM, kcat/KM, Tm, Vmax, etc.)",
        "8. **PDB IDs** (if mentioned)",
        "",
        "**IMPORTANT - For table or data chart images:**",
        "- If the figure is a TABLE or contains TABULAR DATA, you MUST output the data in CSV format",
        "- Format the CSV as a code block with ```csv ... ```",
        "- Include column headers and all data rows",
        "- Preserve numerical values with units (e.g., '1.5 ± 0.2', 'n.d.', 'n.c.')",
        "- If the table contains enzyme variants and kinetic parameters, ensure each variant is a separate row",
        "",
        "Example CSV format for enzyme kinetics:",
        "```csv",
        "Variant,kcat (s^-1),KM (mM),kcat/KM (M^-1s^-1),Tm (°C)",
        "Des27,1.2,0.5,2400,55",
        "Des27.7,3.5,0.3,11667,60",
        "```",
        "",
        "**For tables with amino acid substitutions:**",
        "- Include columns for EACH mutation position shown in the table",
        "- Use single-letter amino acid codes (e.g., H, F, L, W, V)",
        "- Example format: Variant,Position54,Position92,Position115,Position136,Position183,Position216,Position236,kcat/KM,OtherMetric",
    ])

    return "\n".join(prompt_parts)


def extract_csv_from_content(content: str) -> Optional[str]:
    """Extract CSV data from markdown code blocks

    Args:
        content: Analysis content that may contain CSV in code blocks

    Returns:
        CSV string if found, None otherwise
    """
    import re

    # Look for CSV code blocks: ```csv ... ```
    pattern = r'```csv\s*\n(.*?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)

    if matches:
        return matches[0]  # Return first CSV block found
    return None


def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Vision Image Analyzer - Analyze images using Qwen3-VL model',
        epilog='Examples:\n'
        '  # Use default config file\n'
        '  python vision_image_analyzer.py\n'
        '  # Specify custom config file\n'
        '  python vision_image_analyzer.py --config config/llm_config.qwen_vl.example.json\n'
        '  # Analyze specific image\n'
        '  python vision_image_analyzer.py --image-number 7\n'
        '  # Analyze all relevant images\n'
        '  python vision_image_analyzer.py --all',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--config',
        type=str,
        default='config/llm_config.qwen_vl.example.json',
        help=
        'Path to LLM configuration JSON file (default: config/llm_config.qwen_vl.example.json)'
    )
    parser.add_argument('--image-number',
                        type=int,
                        default=None,
                        help='Specific image number to analyze (default: 7 for Fig 3a)')
    parser.add_argument('--all',
                        action='store_true',
                        help='Analyze all relevant images')
    parser.add_argument('--max-images',
                        type=int,
                        default=None,
                        help='Maximum number of images to analyze')
    parser.add_argument(
        '--csv-path',
        type=str,
        default='data/analysis/listov2025_structure_analysis_images.csv',
        help='Path to CSV file with image information')
    parser.add_argument('--relevant-only',
                        action='store_true',
                        default=False,
                        help='Only process images marked as relevant')

    args = parser.parse_args()

    # Load configuration from file
    print(f"Loading configuration from {args.config}...")
    try:
        config = load_config_from_file(args.config)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {args.config}")
        print("Please create a configuration file or use --config to specify one.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration file: {e}")
        exit(1)

    # Extract API configuration
    api_key = config.get('api_key') or os.environ.get('API_KEY')
    base_url = config.get('base_url') or os.environ.get('QWEN_VL_BASE_URL')
    model_name = config.get('model_name', 'Qwen3-VL-235B-A22B-Thinking')

    if not api_key:
        print("Error: API key not found in config file or environment")
        exit(1)

    # Initialize OpenAI client
    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    print(f"Using model: {model_name}\n")

    # CSV file path
    csv_path = args.csv_path

    # Base directory (for resolving relative paths)
    base_dir = Path("data/listov2025")

    # Load image information
    print(f"Loading image information from {csv_path}...")
    images = load_images_from_csv(csv_path, relevant_only=args.relevant_only)
    print(f"Found {len(images)} total images\n")

    # Determine which images to analyze
    results = []
    csv_data = []

    if args.all:
        # Analyze all images
        images_to_analyze = images
        if args.max_images:
            images_to_analyze = images_to_analyze[:args.max_images]
        print(f"Analyzing {len(images_to_analyze)} images...\n")
    elif args.image_number:
        # Analyze specific image
        target_image_number = str(args.image_number)
        images_to_analyze = [
            img for img in images if img["image_number"] == target_image_number
        ]
        if not images_to_analyze:
            print(f"[ERROR] Image #{args.image_number} not found")
            return
        print(f"Analyzing image #{args.image_number}...\n")
    else:
        # Default: Analyze Image 7 (Fig 3a)
        target_image_number = "7"
        images_to_analyze = [
            img for img in images if img["image_number"] == target_image_number
        ]
        if not images_to_analyze:
            print(f"[ERROR] Image #7 not found (default image)")
            return
        print(f"Analyzing image #7 (Fig 3a) by default...\n")

    for i, image_info in enumerate(images_to_analyze, 1):
        image_number = image_info["image_number"]
        image_rel_path = image_info["image_path"]
        image_full_path = base_dir / image_rel_path

        print(
            f"[{i}/{len(images_to_analyze)}] Analyzing image #{image_number}: {image_rel_path}"
        )

        # Generate scientific figure analysis prompt
        prompt = analyze_scientific_figure_prompt(image_info)

        # Call model for analysis
        result = analyze_image_with_vision(client=client,
                                           image_path=str(image_full_path),
                                           prompt=prompt,
                                           model=model_name)

        if "error" in result:
            print(f"  [ERROR] {result['error']}\n")
        else:
            print(f"  [OK] Success")
            print(f"     Tokens used: {result['usage'].get('total_tokens', 0)}")

            # Extract CSV if present
            csv_content = extract_csv_from_content(result["content"])
            if csv_content:
                print(f"     [CSV] Table data extracted")
                csv_data.append({
                    "image_number": image_number,
                    "image_path": image_rel_path,
                    "csv_data": csv_content
                })

            print(f"     Preview: {result['content'][:150]}...\n")

        results.append(result)

    # Save analysis results
    output_path = "data/image_analysis_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nAnalysis complete! Results saved to: {output_path}")

    # Save extracted CSV data
    if csv_data:
        csv_output_path = "data/image_analysis_extracted_tables.csv"
        with open(csv_output_path, "w", encoding="utf-8") as f:
            for item in csv_data:
                f.write(f"# Image {item['image_number']}: {item['image_path']}\n")
                f.write(item["csv_data"])
                f.write("\n\n")
        print(f"Extracted CSV data saved to: {csv_output_path}")

    # Print statistics
    success_count = sum(1 for r in results if "error" not in r)
    csv_count = len(csv_data)
    print(f"\nStatistics: {success_count}/{len(results)} images analyzed successfully")
    print(f"           {csv_count} tables extracted in CSV format")


if __name__ == "__main__":
    main()
