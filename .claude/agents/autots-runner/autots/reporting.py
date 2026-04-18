"""Append-only checkpoint log and end-of-run summary."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import shutil
from typing import Any

from autots_types import EvaluationRecord
from autots_types import TSState


def checkpoint_record(log_path: Path, record: EvaluationRecord) -> None:
    payload = {
        "round_index": record.round_index,
        "phase": record.phase,
        "proposal_source": record.proposal_source,
        "params": asdict(record.params),
        "state": record.state.name,
        "metrics": record.metrics.to_dict(),
        "guess_path": str(record.guess_path),
        "result_path": str(record.result_path),
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _record_sort_key(record: EvaluationRecord) -> tuple[Any, ...]:
    imag_count = len(record.metrics.imag_freqs_cm1)
    max_abs_imag = record.metrics.max_abs_imag_cm1 if imag_count else float("inf")
    energy = (record.metrics.energy_hartree
              if record.metrics.energy_hartree is not None else float("inf"))
    if record.state == TSState.MULTI_IMAG:
        return (-int(record.state), max_abs_imag, imag_count, energy,
                record.round_index, record.phase)
    return (-int(record.state), energy, imag_count, max_abs_imag, record.round_index,
            record.phase)


def _format_params(params: Any) -> str:
    try:
        data = asdict(params)
    except TypeError:
        return repr(params)
    return ", ".join(f"{key}={value}" for key, value in data.items())


def _format_case_metrics(metrics: dict[str, float]) -> str:
    if not metrics:
        return "-"
    return ", ".join(f"{key}={value:.3f}" for key, value in metrics.items())


def write_summary(run_dir: Path, history: list[EvaluationRecord]) -> None:
    summary_path = run_dir / "summary.md"
    if not history:
        summary_path.write_text("# autoTS summary\n\nNo rounds were executed.\n")
        return
    ranked = sorted(history, key=_record_sort_key)
    lines = [
        "# autoTS summary",
        "",
        f"- Total evaluations: {len(history)}",
        f"- Best state: {ranked[0].state.name}",
        "",
        "| rank | round | phase | state | imags | energy_hartree | case_metrics | params |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rank, record in enumerate(ranked[:3], start=1):
        imags = ", ".join(f"{value:.2f}"
                          for value in record.metrics.imag_freqs_cm1) or "-"
        energy = (f"{record.metrics.energy_hartree:.6f}"
                  if record.metrics.energy_hartree is not None else "-")
        lines.append(
            f"| {rank} | {record.round_index} | {record.phase} | {record.state.name} | "
            f"{imags} | {energy} | {_format_case_metrics(record.metrics.case_metrics)} | "
            f"{_format_params(record.params)} |")
    summary_path.write_text("\n".join(lines) + "\n")
    best_guess = ranked[0].guess_path
    if best_guess.exists():
        shutil.copyfile(best_guess, run_dir / "best_ts_guess.xyz")
