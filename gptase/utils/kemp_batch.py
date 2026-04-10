"""Helpers for batch-running the enzyme extraction plan over paper folders."""

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import time
from typing import Iterable, List, Optional, Sequence

DEFAULT_PLAN_ID = "enzyme_extraction_pipeline"
DEFAULT_RESULT_FILE = f"{DEFAULT_PLAN_ID}_result.json"


@dataclass(frozen=True)
class BatchJob:
    """Represents one paper folder to process."""

    name: str
    input_path: Path
    output_path: Path

    @property
    def result_file(self) -> Path:
        """Return the expected harness result file for this batch job."""
        return self.output_path / DEFAULT_RESULT_FILE


def discover_batch_jobs(papers_dir: Path, output_root: Path) -> List[BatchJob]:
    """Discover batch jobs from immediate child directories under ``papers_dir``."""
    jobs: List[BatchJob] = []

    if not papers_dir.exists():
        raise FileNotFoundError(f"Papers directory not found: {papers_dir}")

    for paper_dir in sorted(path for path in papers_dir.iterdir() if path.is_dir()):
        input_path = _select_input_file(paper_dir)
        if input_path is None:
            continue
        jobs.append(
            BatchJob(
                name=paper_dir.name,
                input_path=input_path,
                output_path=output_root / paper_dir.name,
            ))

    return jobs


def _select_input_file(paper_dir: Path) -> Optional[Path]:
    """Prefer ``full.md`` and fall back to a single ``*_origin.pdf`` file."""
    markdown_path = paper_dir / "full.md"
    if markdown_path.exists():
        return markdown_path

    pdf_candidates = sorted(paper_dir.glob("*_origin.pdf"))
    if not pdf_candidates:
        return None
    return pdf_candidates[0]


def build_plan_command(job: BatchJob,
                       plan_id: str = DEFAULT_PLAN_ID,
                       conda_env: Optional[str] = None) -> List[str]:
    """Build the CLI command for a single extraction job."""
    if conda_env:
        runner = ["conda", "run", "-n", conda_env, "python", "-m", "gptase.main"]
    else:
        runner = [sys.executable, "-m", "gptase.main"]

    return runner + [
        "plan",
        "run",
        "-p",
        plan_id,
        "-i",
        str(job.input_path),
        "-o",
        str(job.output_path),
    ]


def _wait_for_process(command: Sequence[str],
                      result_file: Path,
                      success_grace_period: int = 20,
                      poll_interval: float = 2.0) -> int:
    """Wait for a job process, but treat late hang-after-success as success."""
    process = subprocess.Popen(command)
    result_seen_at: Optional[float] = None

    while True:
        return_code = process.poll()
        if return_code is not None:
            return return_code

        if result_file.exists():
            if result_seen_at is None:
                result_seen_at = time.monotonic()
            elif time.monotonic() - result_seen_at >= success_grace_period:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                print(f"[WARNING] Result file exists at {result_file}; "
                      f"terminated hanging process after "
                      f"{success_grace_period}s grace period")
                return 0

        time.sleep(poll_interval)


def run_batch_jobs(jobs: Sequence[BatchJob],
                   plan_id: str = DEFAULT_PLAN_ID,
                   conda_env: Optional[str] = None,
                   dry_run: bool = False,
                   fail_fast: bool = False,
                   skip_existing: bool = True) -> int:
    """Run all jobs and return ``0`` on success or ``1`` if any job fails."""
    exit_code = 0

    for index, job in enumerate(jobs, start=1):
        command = build_plan_command(job, plan_id=plan_id, conda_env=conda_env)
        print(f"[INFO] ({index}/{len(jobs)}) {job.name}")
        print(f"[INFO] Input : {job.input_path}")
        print(f"[INFO] Output: {job.output_path}")
        print(f"[INFO] Command: {' '.join(command)}")

        if dry_run:
            continue

        if skip_existing and job.result_file.exists():
            print(
                f"[INFO] Skipping {job.name}; result already exists at {job.result_file}"
            )
            continue

        job.output_path.mkdir(parents=True, exist_ok=True)
        return_code = _wait_for_process(command, job.result_file)
        if return_code != 0:
            exit_code = 1
            print(f"[ERROR] Job failed for {job.name} with exit code "
                  f"{return_code}")
            if fail_fast:
                return exit_code

    return exit_code


def format_jobs(jobs: Iterable[BatchJob]) -> str:
    """Return a simple human-readable listing for dry runs."""
    lines = []
    for job in jobs:
        lines.append(f"{job.name}: {job.input_path} -> {job.output_path}")
    return "\n".join(lines)
