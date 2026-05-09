#!/usr/bin/env python3
"""Model comparison tool for a plan workflow.

This script provides two modes:
1. Run mode: Execute a plan with specified model(s) and save results
2. Compare mode: Compare results from multiple model runs

Usage:
    # Run the plan with a specific model
    python scripts/compare_models.py run --model glm5
    python scripts/compare_models.py run --model deepseek
    python scripts/compare_models.py run --all

    # Compare existing results
    python scripts/compare_models.py compare
    python scripts/compare_models.py compare --baseline kimi

    # Run and compare in one command
    python scripts/compare_models.py run --all --compare
"""

import argparse
import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# Available model configurations
MODEL_CONFIGS = {
    "kimi": "config/llm_config.template.json",
    "glm5": "config/llm_config.glm5.json",
    "minimax": "config/llm_config.minimax.json",
    "deepseek": "config/llm_config.deepseek.json",
}

# Default input file
DEFAULT_INPUT = "data/input/documents/test_enzyme.md"


# =============================================================================
# Plan execution
# =============================================================================
async def run_plan_with_model(
    model_name: str,
    config_path: str,
    input_file: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Run a plan with a specific model configuration.

    Args:
        model_name: Name of the model for logging.
        config_path: Path to the model config file.
        input_file: Path to input file (default: test_enzyme.md).
        output_dir: Output directory path.

    Returns:
        Dictionary with results and timing info.
    """
    from gptase.core.orchestrator import AgentOrchestrator
    from gptase.utils.config import FrameworkConfig
    from gptase.utils.config import load_template_config
    from gptase.utils.paths import get_paths

    # Set environment variable for config before importing
    os.environ["GPTASE_LLM_CONFIG"] = str(Path(config_path).resolve())

    # Get model name from config
    config_data = load_template_config()
    actual_model = config_data.get("model_name", model_name)

    print(f"\n{'='*60}")
    print(f"[INFO] Running plan with {model_name}")
    print(f"[INFO] Config: {config_path}")
    print(f"[INFO] Model: {actual_model}")
    print(f"{'='*60}\n")

    # Resolve input file
    if input_file:
        input_path = Path(input_file)
    else:
        paths = get_paths()
        input_path = (paths.project_root / "data" / "input" / "documents"
                      / "test_enzyme.md")

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    text = input_path.read_text(encoding="utf-8")

    # Create output directory
    if output_dir:
        out_dir = Path(output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Extract short model name
        model_short = actual_model.lower().replace("-", "_").replace("/", "_")[:20]
        out_dir = Path(f"data/extraction/{model_short}_{timestamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    plan_id = "enzyme_extraction_pipeline"

    print(f"[INFO] Input: {input_path}")
    print(f"[INFO] Output: {out_dir}")
    print(f"[INFO] Plan: {plan_id}")

    # Run plan
    orchestrator = AgentOrchestrator(FrameworkConfig())
    start_time = time.time()

    try:
        result = await orchestrator.dispatch({
            "query": f"Execute draft plan {plan_id}",
            "plan_id": plan_id,
            "input_data": {
                "text": text
            },
            "document_path": str(input_path),
            "auto_execute": True,
            "auto_replan": False,
        })
    except Exception as e:
        result = {"status": "error", "error": str(e)}
        logger.error(f"Plan execution failed: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            import traceback
            traceback.print_exc()
    finally:
        await orchestrator.close()

    end_time = time.time()
    duration = end_time - start_time

    # Prepare result
    result["model_name"] = model_name
    result["actual_model"] = actual_model
    result["config_path"] = str(config_path)
    result["duration_seconds"] = round(duration, 2)
    result["timestamp"] = datetime.now().isoformat()
    result["input_file"] = str(input_path)

    # Save results
    results_file = out_dir / "results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    # Save test summary
    summary = {
        "test_info": {
            "model": actual_model,
            "config_file": str(config_path),
            "input_file": str(input_path),
            "timestamp": result["timestamp"],
        },
        "timing": {
            "total_seconds": result["duration_seconds"],
        },
        "results": {
            "status": result.get("status"),
            "task_count": len(result.get("task_results", {})),
        },
    }

    summary_file = out_dir / "test_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    # Print summary
    print(f"\n[INFO] Completed in {duration:.2f}s")
    print(f"[INFO] Status: {result.get('status')}")
    print(f"[INFO] Results: {results_file}")

    return result


# =============================================================================
# Result Parsing
# =============================================================================


def extract_reactions(result: dict) -> list:
    """Extract reactions list from result.

    Handles multiple result formats:
    - Dict format: task_results.<task>.parsed_output.reactions
    - Legacy dict/list formats from older comparison outputs
    """
    task_results = result.get("task_results", {})
    if isinstance(task_results, dict):
        for task_result in task_results.values():
            if not isinstance(task_result, dict):
                continue
            parsed_output = task_result.get("parsed_output")
            if isinstance(parsed_output, dict) and isinstance(
                    parsed_output.get("reactions"), list):
                return parsed_output["reactions"]

    step_results = result.get("step_results", {})

    # Legacy dict format
    if isinstance(step_results, dict):
        step2a = step_results.get("2a", {})
        if isinstance(step2a, dict):
            # Direct reactions key
            if "reactions" in step2a:
                return step2a["reactions"]

            # Parse content as JSON
            content = step2a.get("content", "")
            if content:
                reactions = parse_json_content(content, "reactions")
                if reactions:
                    return reactions

            # Check outputs/result keys
            for key in ["outputs", "result"]:
                if key in step2a:
                    data = step2a[key]
                    if isinstance(data, dict) and "reactions" in data:
                        return data["reactions"]

    # Legacy list format
    elif isinstance(step_results, list):
        for step in step_results:
            if step.get("step_id") in ("2a", "2"):
                outputs = step.get("outputs", {})
                return outputs.get("reactions", [])

    return []


def parse_json_content(content: str, key: str = None) -> Any:
    """Parse JSON from content string.

    Handles formats:
    - Plain JSON: {...}
    - Markdown code block: ```json\\n{...}\\n```
    - Mixed content with JSON inside
    """
    if not content:
        return None

    content = content.strip()

    # Try markdown code block first
    if "```json" in content:
        import re

        # Extract content between ```json and ```
        match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
        if match:
            json_content = match.group(1)
            try:
                parsed = json.loads(json_content)
                return parsed.get(key) if key else parsed
            except json.JSONDecodeError:
                pass

        # Fallback: find JSON object after ```json
        json_start = content.find("```json")
        if json_start != -1:
            rest = content[json_start + 7:].strip()
            # Find the start of JSON object
            brace_start = rest.find("{")
            if brace_start != -1:
                json_str = rest[brace_start:]
                # Find matching closing brace
                brace_count = 0
                end_pos = 0
                for i, c in enumerate(json_str):
                    if c == "{":
                        brace_count += 1
                    elif c == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break
                if end_pos > 0:
                    try:
                        parsed = json.loads(json_str[:end_pos])
                        return parsed.get(key) if key else parsed
                    except json.JSONDecodeError:
                        pass

    # Try direct JSON
    if content.startswith("{") or content.startswith("["):
        try:
            parsed = json.loads(content)
            return parsed.get(key) if key else parsed
        except json.JSONDecodeError:
            pass

    # Try to find JSON object anywhere in content
    brace_start = content.find("{")
    if brace_start != -1:
        json_str = content[brace_start:]
        brace_count = 0
        end_pos = 0
        for i, c in enumerate(json_str):
            if c == "{":
                brace_count += 1
            elif c == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i + 1
                    break
        if end_pos > 0:
            try:
                parsed = json.loads(json_str[:end_pos])
                return parsed.get(key) if key else parsed
            except json.JSONDecodeError:
                pass

    return None


def compute_param_coverage(reactions: list) -> dict:
    """Compute parameter coverage for reactions."""
    if not reactions:
        return {}

    total = len(reactions)
    params = ["kcat", "Km", "kcat/Km", "Tm", "Vmax"]
    counts = {p: 0 for p in params}

    for r in reactions:
        kinetics = r.get("kinetics", {})
        for param in params:
            if kinetics.get(param) is not None:
                counts[param] += 1

    return {
        p: {
            "count": c,
            "total": total,
            "coverage": f"{c}/{total} ({c/total*100:.1f}%)"
        }
        for p, c in counts.items() if c > 0
    }


def get_variant_names(reactions: list) -> set:
    """Extract variant names from reactions."""
    return {r.get("enzyme_name") for r in reactions if r.get("enzyme_name")}


# =============================================================================
# Comparison
# =============================================================================


def compare_two_models(baseline: dict, test: dict) -> dict:
    """Compare two model results.

    Args:
        baseline: Baseline result (usually Kimi-K2).
        test: Test result to compare.

    Returns:
        Comparison dictionary.
    """
    comparison = {
        "baseline_model": baseline.get("model_name", "baseline"),
        "test_model": test.get("model_name", "test"),
        "timestamp": datetime.now().isoformat(),
    }

    # Execution info
    comparison["baseline_status"] = baseline.get("status")
    comparison["test_status"] = test.get("status")
    comparison["baseline_duration"] = baseline.get("duration_seconds")
    comparison["test_duration"] = test.get("duration_seconds")

    if baseline.get("duration_seconds") and test.get("duration_seconds"):
        comparison["duration_diff"] = round(
            test["duration_seconds"] - baseline["duration_seconds"], 2)
        comparison["duration_ratio"] = round(
            test["duration_seconds"] / baseline["duration_seconds"], 2)

    # Extract reactions
    baseline_reactions = extract_reactions(baseline)
    test_reactions = extract_reactions(test)

    comparison["baseline_variant_count"] = len(baseline_reactions)
    comparison["test_variant_count"] = len(test_reactions)

    # Parameter coverage
    comparison["baseline_param_coverage"] = compute_param_coverage(baseline_reactions)
    comparison["test_param_coverage"] = compute_param_coverage(test_reactions)

    # Variant comparison
    baseline_names = get_variant_names(baseline_reactions)
    test_names = get_variant_names(test_reactions)

    comparison["common_variants"] = sorted(baseline_names & test_names)
    comparison["missing_variants"] = sorted(baseline_names - test_names)
    comparison["extra_variants"] = sorted(test_names - baseline_names)

    # Value comparison
    comparison["kinetic_comparison"] = compare_kinetic_values(
        baseline_reactions, test_reactions)

    return comparison


def compare_kinetic_values(baseline_reactions: list, test_reactions: list) -> list:
    """Compare kinetic values between two reaction lists."""
    baseline_by_name = {
        r["enzyme_name"]: r
        for r in baseline_reactions if "enzyme_name" in r
    }
    test_by_name = {r["enzyme_name"]: r for r in test_reactions if "enzyme_name" in r}

    common = set(baseline_by_name.keys()) & set(test_by_name.keys())
    params = ["kcat", "Km", "kcat/Km", "Tm", "Vmax"]

    comparisons = []
    mismatches = []

    for name in sorted(common):
        b_k = baseline_by_name[name].get("kinetics", {})
        t_k = test_by_name[name].get("kinetics", {})

        variant_comp = {"enzyme_name": name, "params": {}}

        for param in params:
            b_val = b_k.get(param)
            t_val = t_k.get(param)

            if b_val is not None and t_val is not None:
                try:
                    b_float = float(str(b_val).replace(">", "").replace("<", ""))
                    t_float = float(str(t_val).replace(">", "").replace("<", ""))

                    diff = round(t_float - b_float, 4)
                    ratio = round(t_float / b_float, 4) if b_float != 0 else None

                    # Check if values match (within 1% tolerance)
                    match = abs(diff) < 0.01 * max(abs(b_float), 1)
                    match_str = "[OK]" if match else "[DIFF]"

                    variant_comp["params"][param] = {
                        "baseline": b_val,
                        "test": t_val,
                        "diff": diff,
                        "ratio": ratio,
                        "match": match_str,
                    }

                    if not match:
                        mismatches.append({
                            "variant": name,
                            "param": param,
                            "baseline": b_float,
                            "test": t_float,
                            "diff": diff,
                        })

                except (ValueError, TypeError):
                    variant_comp["params"][param] = {
                        "baseline": b_val,
                        "test": t_val,
                        "match": "[ERROR]",
                    }
            elif b_val is not None or t_val is not None:
                variant_comp["params"][param] = {
                    "baseline": b_val,
                    "test": t_val,
                    "match": "[MISSING]",
                }

        comparisons.append(variant_comp)

    return {"comparisons": comparisons, "mismatches": mismatches}


def find_result_files() -> Dict[str, Path]:
    """Find all result files in data/extraction directory."""
    extraction_dir = Path("data/extraction")
    if not extraction_dir.exists():
        return {}

    results = {}
    for subdir in extraction_dir.iterdir():
        if not subdir.is_dir():
            continue

        # Look for results.json
        result_file = subdir / "results.json"
        if result_file.exists():
            # Use directory name as key
            results[subdir.name] = result_file

    return results


def compare_all_results(baseline_name: Optional[str] = None) -> None:
    """Compare all available results.

    Args:
        baseline_name: Name of baseline model (default: use most recent kimi result).
    """
    result_files = find_result_files()

    if not result_files:
        print("[ERROR] No result files found in data/extraction/")
        return

    print(f"[INFO] Found {len(result_files)} result directories:")
    for name in sorted(result_files.keys()):
        print(f"  - {name}")

    # Load all results
    results = {}
    for name, path in result_files.items():
        try:
            with open(path) as f:
                results[name] = json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load {name}: {e}")

    # Determine baseline
    if baseline_name:
        baseline_key = None
        for key in results:
            if baseline_name.lower() in key.lower():
                baseline_key = key
                break
        if not baseline_key:
            print(f"[ERROR] Baseline '{baseline_name}' not found")
            return
    else:
        # Use first kimi result, or first available
        baseline_key = None
        for key in sorted(results.keys(), reverse=True):
            if "kimi" in key.lower():
                baseline_key = key
                break
        if not baseline_key:
            baseline_key = sorted(results.keys())[0]

    baseline = results[baseline_key]
    print(f"\n[INFO] Using baseline: {baseline_key}")

    # Compare each result against baseline
    print("\n" + "=" * 80)
    print("MODEL COMPARISON REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Summary table
    print("SUMMARY")
    print("-" * 80)
    print(
        f"{'Model':<25} | {'Status':<10} | {'Time':<10} | {'Variants':<10} | {'Coverage':<20}"
    )
    print("-" * 80)

    for name, result in sorted(results.items()):
        status = result.get("status", "unknown")
        duration = result.get("duration_seconds", 0)
        reactions = extract_reactions(result)
        variant_count = len(reactions)
        coverage = compute_param_coverage(reactions)
        kcat_cov = coverage.get("kcat", {}).get("coverage", "N/A")

        marker = "*" if name == baseline_key else " "
        print(
            f"{marker} {name:<23} | {status:<10} | {duration:<10.1f} | {variant_count:<10} | {kcat_cov:<20}"
        )

    # Detailed comparisons
    for name, result in sorted(results.items()):
        if name == baseline_key:
            continue

        print(f"\n{'='*80}")
        print(f"COMPARISON: {name} vs {baseline_key}")
        print("=" * 80)

        comparison = compare_two_models(baseline, result)

        print(f"Status: {comparison['test_status']}")
        print(
            f"Duration: {comparison['test_duration']}s (baseline: {comparison['baseline_duration']}s)"
        )

        if comparison.get("duration_diff"):
            diff = comparison["duration_diff"]
            ratio = comparison["duration_ratio"]
            print(f"  Diff: {diff:+.1f}s ({ratio:.2f}x)")

        print(f"\nVariants:")
        print(f"  Baseline: {comparison['baseline_variant_count']}")
        print(f"  Test: {comparison['test_variant_count']}")
        print(f"  Common: {len(comparison['common_variants'])}")

        if comparison["missing_variants"]:
            print(f"  Missing: {comparison['missing_variants'][:5]}")
        if comparison["extra_variants"]:
            print(f"  Extra: {comparison['extra_variants'][:5]}")

        # Mismatches
        kinetic = comparison.get("kinetic_comparison", {})
        mismatches = kinetic.get("mismatches", [])

        if mismatches:
            print(f"\nValue Mismatches: {len(mismatches)}")
            for m in mismatches[:10]:
                print(
                    f"  {m['variant']:<20} {m['param']:<10}: "
                    f"baseline={m['baseline']:<10} test={m['test']:<10} diff={m['diff']:+.4f}"
                )
        else:
            print("\n[OK] All kinetic values match!")

        # Save comparison
        output_dir = Path("data/extraction/comparison")
        output_dir.mkdir(parents=True, exist_ok=True)
        comparison_file = output_dir / f"comparison_{name}_vs_{baseline_key}.json"
        with open(comparison_file, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False, default=str)
        print(f"\nComparison saved to: {comparison_file}")


# =============================================================================
# CLI
# =============================================================================


async def run_command(args):
    """Handle 'run' command."""
    if args.all:
        models = list(MODEL_CONFIGS.keys())
    elif args.model:
        models = [args.model]
    else:
        print("[ERROR] Specify --model or --all")
        return 1

    results = {}
    for model in models:
        config_path = MODEL_CONFIGS.get(model)
        if not config_path:
            print(f"[WARNING] Unknown model: {model}")
            continue

        if not Path(config_path).exists():
            print(f"[WARNING] Config not found: {config_path}")
            continue

        try:
            result = await run_plan_with_model(
                model_name=model,
                config_path=config_path,
                input_file=args.input,
                output_dir=args.output,
            )
            results[model] = result
        except Exception as e:
            print(f"[ERROR] Failed to run {model}: {e}")
            results[model] = {"status": "error", "error": str(e)}

    # Compare if requested
    if args.compare and len(results) > 1:
        print("\n" + "=" * 60)
        print("COMPARISON")
        print("=" * 60)
        compare_all_results(baseline_name=args.baseline)

    return 0


def compare_command(args):
    """Handle 'compare' command."""
    compare_all_results(baseline_name=args.baseline)


def main():
    parser = argparse.ArgumentParser(
        description="Model comparison tool for a plan workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run the plan with model(s)")
    run_parser.add_argument(
        "--model",
        "-m",
        choices=list(MODEL_CONFIGS.keys()),
        help="Model to test",
    )
    run_parser.add_argument("--all", "-a", action="store_true", help="Test all models")
    run_parser.add_argument(
        "--input",
        "-i",
        help="Input file path",
    )
    run_parser.add_argument(
        "--output",
        "-o",
        help="Output directory",
    )
    run_parser.add_argument(
        "--compare",
        "-c",
        action="store_true",
        help="Compare results after running",
    )
    run_parser.add_argument(
        "--baseline",
        "-b",
        help="Baseline model name for comparison",
    )
    run_parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare existing results")
    compare_parser.add_argument(
        "--baseline",
        "-b",
        help="Baseline model name",
    )

    args = parser.parse_args()

    if args.command == "run":
        if args.debug:
            logging.basicConfig(level=logging.DEBUG)
        return asyncio.run(run_command(args))
    elif args.command == "compare":
        compare_command(args)
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
