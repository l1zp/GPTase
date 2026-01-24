#!/usr/bin/env python3
"""
Main pipeline runner for enzyme extraction data analysis.

This script orchestrates the complete analysis pipeline:
Step 1: JSON to CSV conversion
Step 2: Add variant information
Step 3+: Future analysis steps

Usage:
    # Run complete pipeline
    python pipelines/run_analysis.py --input data/extraction/listov2025_extraction.json

    # Run specific steps
    python pipelines/run_analysis.py --steps 1 --input data/extraction/listov2025_extraction.json
    python pipelines/run_analysis.py --steps 2 --input data/extraction/listov2025_extraction.csv

    # Run with statistics
    python pipelines/run_analysis.py --input data/extraction/listov2025_extraction.json --stats
"""

import argparse
import sys
from pathlib import Path
from importlib import import_module

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import pipeline steps
json_to_csv = import_module('pipelines.json_to_csv')
add_variant_info = import_module('pipelines.add_variant_info')
add_mutation_details = import_module('pipelines.add_mutation_details')
add_ec_numbers = import_module('pipelines.add_ec_numbers')

step1_main = json_to_csv.main
step2_main = add_variant_info.main
step3_main = add_mutation_details.main
step4_main = add_ec_numbers.main


def parse_step_args(args_str: str) -> list:
    """Parse step argument string."""
    if args_str.lower() == 'all':
        return [1, 2, 3, 4]
    return [int(s.strip()) for s in args_str.split(',')]


def run_pipeline(input_path: str, steps: list, show_stats: bool = False, validate: bool = False):
    """
    Run the specified pipeline steps.

    Args:
        input_path: Path to input file (JSON for step 1, CSV for step 2)
        steps: List of step numbers to run
        show_stats: Whether to show statistics for each step
        validate: Whether to enable data validation in Step 1
    """
    print("=" * 60)
    print("🧪 Enzyme Extraction Data Analysis Pipeline")
    print("=" * 60)

    current_input = input_path

    for step in sorted(steps):
        print(f"\n{'=' * 60}")
        print(f"Step {step}: {get_step_name(step)}")
        print('=' * 60)

        try:
            if step == 1:
                # Step 1: JSON to CSV
                output = str(Path(current_input).with_suffix('.csv'))
                cmd_args = ['-i', current_input, '-o', output]
                if show_stats:
                    cmd_args.append('--stats')
                if validate:
                    cmd_args.append('--validate')

                # Simulate command line args
                old_argv = sys.argv
                sys.argv = ['json_to_csv.py'] + cmd_args
                step1_main()
                sys.argv = old_argv

                current_input = output

            elif step == 2:
                # Step 2: Add variant info
                if not current_input.endswith('.csv'):
                    print(f"⚠️  Step 2 requires CSV input, got: {current_input}")
                    print(f"   Looking for CSV version of {current_input}...")
                    csv_path = str(Path(current_input).with_suffix('.csv'))
                    if Path(csv_path).exists():
                        current_input = csv_path
                        print(f"   Found: {csv_path}")
                    else:
                        print("❌ CSV file not found. Run Step 1 first.")
                        sys.exit(1)

                output = str(Path(current_input).stem) + '_with_variants.csv'
                cmd_args = ['-i', current_input, '-o', output]

                old_argv = sys.argv
                sys.argv = ['add_variant_info.py'] + cmd_args
                step2_main()
                sys.argv = old_argv

                current_input = output

            elif step == 3:
                # Step 3: Add mutation details
                if not current_input.endswith('_with_variants.csv'):
                    print(f"⚠️  Step 3 requires CSV with variants from Step 2")
                    # Try to find the variants file
                    expected_path = str(Path(current_input).stem) + '_with_variants.csv'
                    if Path(expected_path).exists():
                        current_input = expected_path
                        print(f"   Found: {expected_path}")
                    else:
                        print("❌ Variants CSV file not found. Run Step 2 first.")
                        sys.exit(1)

                output = str(Path(current_input).stem) + '_with_mutations.csv'
                cmd_args = ['-i', current_input, '-o', output]

                old_argv = sys.argv
                sys.argv = ['add_mutation_details.py'] + cmd_args
                step3_main()
                sys.argv = old_argv

                current_input = output

            elif step == 4:
                # Step 4: Add EC numbers from PDB IDs
                if not current_input.endswith('_with_mutations.csv'):
                    print(f"⚠️  Step 4 requires CSV with mutations from Step 3")
                    # Try to find the mutations file
                    expected_path = str(Path(current_input).stem) + '_with_mutations.csv'
                    if Path(expected_path).exists():
                        current_input = expected_path
                        print(f"   Found: {expected_path}")
                    else:
                        print("❌ Mutations CSV file not found. Run Step 3 first.")
                        sys.exit(1)

                output = str(Path(current_input).stem) + '_with_ec.csv'
                cmd_args = ['-i', current_input, '-o', output]

                old_argv = sys.argv
                sys.argv = ['add_ec_numbers.py'] + cmd_args
                step4_main()
                sys.argv = old_argv

                current_input = output

            else:
                print(f"⚠️  Unknown step: {step}")
                continue

        except Exception as e:
            print(f"❌ Error in Step {step}: {e}")
            sys.exit(1)

    print(f"\n{'=' * 60}")
    print("✅ Pipeline Complete!")
    print('=' * 60)
    print(f"\n📁 Final output: {current_input}")


def get_step_name(step: int) -> str:
    """Get human-readable step name."""
    step_names = {
        1: "JSON to CSV Conversion",
        2: "Add Variant Information",
        3: "Add Mutation Details",
        4: "Add EC Numbers from PDB IDs",
    }
    return step_names.get(step, f"Unknown Step {step}")


def main():
    parser = argparse.ArgumentParser(
        description='Run enzyme extraction data analysis pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline
  python pipelines/run_analysis.py --input data/extraction/listov2025_extraction.json

  # Run Step 1 only
  python pipelines/run_analysis.py --steps 1 --input data/extraction/listov2025_extraction.json

  # Run Step 2 only (requires CSV input)
  python pipelines/run_analysis.py --steps 2 --input data/extraction/listov2025_extraction.csv

  # Run complete pipeline with statistics
  python pipelines/run_analysis.py --input data/extraction/listov2025_extraction.json --stats
        """
    )

    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Input file path (JSON for step 1, CSV for step 2)'
    )
    parser.add_argument(
        '--steps',
        type=str,
        default='all',
        help='Steps to run: "all", "1", "2", or "1,2" (default: all)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics for each step'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Enable data validation in Step 1 (checks for outliers, impossible values, missing units)'
    )

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {args.input}")
        sys.exit(1)

    # Parse steps
    try:
        steps = parse_step_args(args.steps)
    except ValueError:
        print(f"❌ Error: Invalid steps format: {args.steps}")
        print("   Use 'all', '1', '2', or '1,2'")
        sys.exit(1)

    # Run pipeline
    run_pipeline(args.input, steps, args.stats, args.validate)


if __name__ == '__main__':
    main()
