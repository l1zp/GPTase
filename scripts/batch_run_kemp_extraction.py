#!/usr/bin/env python3
"""Batch-run the enzyme extraction plan for paper folders."""

import argparse
from pathlib import Path
import sys

from gptase.utils.kemp_batch import DEFAULT_PLAN_ID
from gptase.utils.kemp_batch import discover_batch_jobs
from gptase.utils.kemp_batch import format_jobs
from gptase.utils.kemp_batch import run_batch_jobs


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Batch-run enzyme extraction for all paper folders.")
    parser.add_argument("--papers-dir",
                        default="papers",
                        help="Directory containing per-paper subdirectories")
    parser.add_argument("--output-root",
                        default="output/kemp",
                        help="Base output directory")
    parser.add_argument("--plan", default=DEFAULT_PLAN_ID, help="Plan ID to execute")
    parser.add_argument("--conda-env",
                        default=None,
                        help="Optional conda environment used to run gptase")
    parser.add_argument("--dry-run",
                        action="store_true",
                        help="Print discovered jobs without executing them")
    parser.add_argument("--fail-fast",
                        action="store_true",
                        help="Stop after the first failed job")
    parser.add_argument("--no-skip-existing",
                        action="store_true",
                        help="Re-run jobs even if result file already exists")
    return parser.parse_args()


def main() -> int:
    """Program entry point."""
    args = parse_args()
    papers_dir = Path(args.papers_dir).resolve()
    output_root = Path(args.output_root).resolve()

    jobs = discover_batch_jobs(papers_dir, output_root)
    if not jobs:
        print(f"[WARNING] No eligible paper folders found under {papers_dir}")
        return 1

    print(f"[INFO] Found {len(jobs)} jobs")
    print(format_jobs(jobs))
    return run_batch_jobs(
        jobs,
        plan_id=args.plan,
        conda_env=args.conda_env,
        dry_run=args.dry_run,
        fail_fast=args.fail_fast,
        skip_existing=not args.no_skip_existing,
    )


if __name__ == "__main__":
    sys.exit(main())
