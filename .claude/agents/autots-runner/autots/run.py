"""Generic autoTS driver — YAML-in, run-dir-out.

Usage:

    python .claude/agents/autots-runner/autots/run.py \\
        --reaction .claude/agents/autots-runner/autots/cases/kemp/reaction.yaml \\
        --profile 7VUU_core \\
        --profiles .claude/agents/autots-runner/autots/cases/kemp/profiles.yaml \\
        --brief .claude/agents/autots-runner/autots/cases/kemp/brief.md

The harness knows nothing about specific reactions. ``--reaction`` points
at a YAML file describing the reaction coordinates, atom roles, mutation
recipes, and scoring rules; ``reaction_spec.load_reaction`` compiles that
into a :class:`Reaction` whose methods drive the loop below.

When ``--profiles`` / ``--brief`` are omitted they default to the files
sitting next to the reaction YAML (``profiles.yaml`` / ``brief.md`` in the
same directory).
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from autots_types import EvaluationRecord  # noqa: E402
from autots_types import TSState  # noqa: E402
from diagnostics import diagnose  # noqa: E402
from diagnostics import write_ts_guess  # noqa: E402
from profiles import load_profile  # noqa: E402
from propose import propose_via_llm  # noqa: E402
from reaction_spec import load_reaction  # noqa: E402
from reporting import checkpoint_record  # noqa: E402
from reporting import write_summary  # noqa: E402
from theozyme import submit_theozyme  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reaction",
                        required=True,
                        help="Path to reaction.yaml (the DSL spec)")
    parser.add_argument("--profile",
                        required=True,
                        help="Profile ID from profiles.yaml")
    parser.add_argument("--profiles",
                        default=None,
                        help="profiles.yaml path (defaults to reaction sibling)")
    parser.add_argument("--brief",
                        default=None,
                        help="brief.md path (defaults to reaction sibling)")
    parser.add_argument("--max-rounds", type=int, default=20)
    parser.add_argument("--cheap-only", action="store_true")
    parser.add_argument("--run-dir",
                        default=None,
                        help="Optional explicit output directory")
    args = parser.parse_args(argv)
    reaction_path = Path(args.reaction).resolve()
    if args.profiles is None:
        args.profiles = str(reaction_path.parent / "profiles.yaml")
    if args.brief is None:
        args.brief = str(reaction_path.parent / "brief.md")
    args.reaction = str(reaction_path)
    return args


async def run(args: argparse.Namespace) -> int:
    reaction = load_reaction(args.reaction)
    profile = load_profile(args.profile, args.profiles, reaction.params_cls)
    brief_text = Path(args.brief).read_text()
    timestamp = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir = (Path(args.run_dir).resolve() if args.run_dir else profile.output_root
               / timestamp)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "autots_log.jsonl"

    history: list[EvaluationRecord] = []
    params = profile.initial_guess
    params_source = "seed"

    def _diagnose(result, guess):
        return diagnose(result,
                        guess,
                        profile,
                        compute_case_metrics=reaction.compute_case_metrics,
                        classify_single_imag=reaction.classify_single_imag)

    try:
        for round_index in range(args.max_rounds):
            round_dir = run_dir / f"round_{round_index:02d}"
            round_dir.mkdir(parents=True, exist_ok=True)
            guess = reaction.mutate_ts_guess(profile, params)
            guess_path = round_dir / "ts_guess.xyz"
            write_ts_guess(guess_path, guess)

            cheap_result = submit_theozyme(guess_path, profile, profile.cheap_mode)
            (round_dir / "ts_opt_result_cheap.json").write_text(
                json.dumps(cheap_result, indent=2, ensure_ascii=False))
            cheap_metrics = _diagnose(cheap_result, guess)
            cheap_record = EvaluationRecord(round_index=round_index,
                                            phase="cheap",
                                            params=params,
                                            guess_path=guess_path,
                                            result_path=round_dir
                                            / "ts_opt_result_cheap.json",
                                            state=cheap_metrics.state,
                                            metrics=cheap_metrics,
                                            proposal_source=params_source)
            history.append(cheap_record)
            checkpoint_record(log_path, cheap_record)
            latest = cheap_record

            if not args.cheap_only and cheap_metrics.state >= TSState.SINGLE_IMAG_AMBIG:
                full_result = submit_theozyme(guess_path, profile, profile.full_mode)
                (round_dir / "ts_opt_result_full.json").write_text(
                    json.dumps(full_result, indent=2, ensure_ascii=False))
                full_metrics = _diagnose(full_result, guess)
                full_record = EvaluationRecord(round_index=round_index,
                                               phase="full",
                                               params=params,
                                               guess_path=guess_path,
                                               result_path=round_dir
                                               / "ts_opt_result_full.json",
                                               state=full_metrics.state,
                                               metrics=full_metrics,
                                               proposal_source=params_source)
                history.append(full_record)
                checkpoint_record(log_path, full_record)
                latest = full_record

            if latest.state == TSState.VALID:
                break

            params, params_source = await propose_via_llm(history, brief_text, profile,
                                                          reaction.params_cls)
    except KeyboardInterrupt:
        write_summary(run_dir, history)
        return 130

    write_summary(run_dir, history)
    return 0 if history and max(r.state for r in history) == TSState.VALID else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
