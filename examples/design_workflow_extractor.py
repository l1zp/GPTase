"""Demonstration of enzyme design workflow extraction using LLM.

This script extracts enzyme design steps and workflows from scientific literature,
including design objectives, methodology steps, key parameters, and validation approaches.

This version uses the EnzymeDesignExtractorAgent directly (delegation pattern).
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Ensure project root is on sys.path to import local modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.agents.specialized.enzyme_design_extractor_agent import \
    EnzymeDesignExtractorAgent
from src.core.paths import get_paths
from src.memory.manager import MemoryManager
from src.tools.implementations import DocumentLoaderTool
from src.tools.registry import ToolRegistry
from src.utils import default_manager


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract enzyme design workflows from markdown documents")
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help="Input markdown file path (default: data/input/documents/listov2025.md)")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: data/extraction/{input_stem}_design.json)"
    )
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    """Run enzyme design extraction using LLM and print results."""
    # Initialize manager using default configuration
    manager = default_manager()
    print("Successfully initialized default Model.")

    # Get standardized paths
    paths = get_paths()

    try:
        # Determine input file path
        if args.input:
            target_file = paths.resolve_input_path(args.input)
        else:
            # Default to listov2025.md in documents directory
            target_file = paths.get_document_path("listov2025")

        if not target_file.exists():
            print(f"Error: Input file not found: {target_file}")
            return

        # Determine output file path
        if args.output:
            output_file = paths.resolve_output_path(args.output)
        else:
            # Default to extraction directory with input filename stem
            output_stem = f"{target_file.stem}_design"
            output_file = paths.get_extraction_path(output_stem)

        print(f"Processing file: {target_file}")

        # Initialize tool registry and memory manager
        tool_registry = ToolRegistry()
        tool_registry.register_tools([DocumentLoaderTool()])
        memory_manager = MemoryManager()

        # Create EnzymeDesignExtractorAgent
        agent = EnzymeDesignExtractorAgent(
            agent_id="design_extractor",
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=manager,
        )

        # Load document content
        loader = DocumentLoaderTool()
        load_result = await loader.execute(path=str(target_file))

        if load_result.status == "error":
            print(f"Error loading document: {load_result.error}")
            return

        document_text = load_result.data.get("content", "")

        # Extract design workflow
        print("\nExtracting enzyme design workflow...")
        result = await agent.process_task({
            "text": document_text,
            "source_file": str(target_file)
        })

        # Display and save results
        if result.get("status") == "success":
            data = result.get("data", {})

            print(f"\n[OK] Design extraction completed successfully!")

            # Display design objectives
            objectives = data.get("design_objectives", [])
            if objectives:
                print(f"\n[Design Objectives] ({len(objectives)}):")
                for obj in objectives:
                    print(f"  - {obj}")
            else:
                print(f"\n[INFO] No design objectives found.")

            # Display design steps
            design_steps = data.get("design_steps", [])
            if design_steps:
                print(f"\n[Design Steps] ({len(design_steps)}):")
                for step in design_steps:
                    step_id = step.get("step_id", "?")
                    category = step.get("category", "General")
                    desc = step.get("description", "N/A")
                    techniques = step.get("techniques", [])

                    # Truncate description if too long
                    if len(desc) > 100:
                        desc = desc[:97] + "..."

                    print(f"  [Step {step_id}] {category}")
                    print(f"    Description: {desc}")
                    if techniques:
                        print(f"    Techniques: {', '.join(techniques[:3])}"
                              + (f" ..." if len(techniques) > 3 else ""))
            else:
                print(f"\n[INFO] No design steps found.")

            # Display key constraints
            constraints = data.get("key_constraints", [])
            if constraints:
                print(f"\n[Key Constraints] ({len(constraints)}):")
                for constraint in constraints:
                    print(f"  - {constraint}")

            # Display optimization cycles
            opt_cycles = data.get("optimization_cycles", [])
            if opt_cycles:
                print(f"\n[Optimization Cycles] ({len(opt_cycles)}):")
                for cycle in opt_cycles:
                    cycle_id = cycle.get("cycle_id", "?")
                    method = cycle.get("method", "Unknown")
                    rounds = cycle.get("rounds")
                    rounds_str = f" ({rounds} rounds)" if rounds else ""
                    print(f"  [Cycle {cycle_id}] {method}{rounds_str}")
                    improvements = cycle.get("improvements", [])
                    if improvements:
                        for imp in improvements[:2]:
                            print(f"    - {imp}")
                        if len(improvements) > 2:
                            print(f"    ... and {len(improvements) - 2} more")

            # Display validation approach
            validation = data.get("validation_approach")
            if validation:
                print(f"\n[Validation Approach]:")
                print(f"  {validation[:200]}"
                      + (f"..." if len(validation) > 200 else ""))

            # Display experimental conditions
            exp_conditions = data.get("experimental_conditions", {})
            if exp_conditions and any(exp_conditions.values()):
                print(f"\n[Experimental Conditions]:")
                for key, value in exp_conditions.items():
                    if value:
                        print(f"  {key}: {value}")

            # Display results
            results = data.get("results", {})
            if results and any(results.values()):
                print(f"\n[Results]:")
                final_variants = results.get("final_variants", [])
                if final_variants:
                    print(f"  Final variants: {', '.join(final_variants[:5])}"
                          + (f" ..." if len(final_variants) > 5 else ""))
                metrics = results.get("performance_metrics", {})
                if metrics:
                    print(f"  Performance metrics:")
                    for key, value in list(metrics.items())[:3]:
                        print(f"    {key}: {value}")

            # Display Chinese annotations
            annotations = data.get("annotations_zh")
            if annotations:
                print(f"\n[Chinese Annotations]:")
                print(f"  {annotations[:300]}"
                      + (f"..." if len(annotations) > 300 else ""))

            # Save results to JSON file
            print(f"\n[INFO] Saving results to: {output_file}")
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            print(f"[OK] Design extraction results saved successfully!")

            # Display session ID if tracking is enabled
            session_id = result.get("data", {}).get("session_id")
            if session_id and session_id != "tracking_disabled":
                print(f"\n[Session] ID: {session_id}")
                print(f"[INFO] View extraction details in the web UI:")
                print(f"  Run: streamlit run src/webui/app.py")
                print(f"  Navigate to: Agent Sessions")

        else:
            error_msg = result.get("data", {}).get("error", "Unknown error")
            print(f"\n[ERROR] Design extraction failed: {error_msg}")

    except Exception as e:
        print(f"\n[ERROR] Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up resources - close database connection
        await manager.shutdown()
        print("\n[INFO] Cleaned up resources.")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
