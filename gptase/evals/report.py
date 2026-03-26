"""Console and JSON report generation for eval results."""

import json
from pathlib import Path
from typing import List

from gptase.evals.assertions import EvalResult

_COL_AGENT = 30
_COL_SCHEMA = 8
_COL_FACTS = 8
_COL_SCORE = 6
_SEPARATOR = "-" * 60
_HEADER = "=" * 60


def print_eval_report(results: List[EvalResult]) -> None:
    """Print a formatted evaluation table to stdout.

    Example output:
        Agent Evaluation: listov2025
        ============================================================
        Agent                          Schema   Facts   Score
        ------------------------------------------------------------
        document_structure_analyzer    [OK]     3/3     1.00
        enzyme_kinetics_extractor      [OK]     5/6     0.83
        ...
        ------------------------------------------------------------
        Overall: 8/9 key facts passed (0.89)

        [WARNING] enzyme_kinetics_extractor: reactions[*].enzyme_name ...
    """
    if not results:
        print("No results to report.")
        return

    agent_name = results[0].agent_name
    print(f"\nAgent Evaluation: {agent_name}")
    print(_HEADER)
    print(
        f"{'Agent':<{_COL_AGENT}} {'Schema':<{_COL_SCHEMA}} {'Facts':<{_COL_FACTS}} {'Score':<{_COL_SCORE}}"
    )
    print(_SEPARATOR)

    total_passed = 0
    total_facts = 0

    for r in results:
        schema_str = "[OK]" if r.schema_valid else "[FAIL]"
        facts_str = f"{r.passed_facts}/{r.total_facts}"
        score_str = f"{r.score:.2f}"
        print(
            f"{r.agent_name:<{_COL_AGENT}} {schema_str:<{_COL_SCHEMA}} {facts_str:<{_COL_FACTS}} {score_str:<{_COL_SCORE}}"
        )
        total_passed += r.passed_facts
        total_facts += r.total_facts

    print(_SEPARATOR)

    overall_score = total_passed / total_facts if total_facts > 0 else 1.0
    print(
        f"Overall: {total_passed}/{total_facts} key facts passed ({overall_score:.2f})")

    # Print failure details
    all_failures = []
    for r in results:
        if not r.schema_valid and r.schema_error:
            prefix = (f"[WARNING] {r.agent_name}: {r.failure_reason} -- "
                      if r.failure_reason else
                      f"[WARNING] {r.agent_name}: schema validation failed -- ")
            all_failures.append(prefix + r.schema_error)
        all_failures.extend(f"[WARNING] {msg}" for msg in r.failed_facts)

    if all_failures:
        print()
        for msg in all_failures:
            print(msg)

    print()


def save_eval_report(results: List[EvalResult], output_path: str) -> None:
    """Save evaluation results as a JSON report.

    Args:
        results: List of EvalResult objects.
        output_path: File path to write (will be created/overwritten).
    """
    total_passed = sum(r.passed_facts for r in results)
    total_facts = sum(r.total_facts for r in results)
    overall_score = total_passed / total_facts if total_facts > 0 else 1.0

    report = {
        "agent_name":
        results[0].agent_name if results else "",
        "overall": {
            "total_facts": total_facts,
            "passed_facts": total_passed,
            "score": round(overall_score, 4),
        },
        "agents": [{
            "agent_name": r.agent_name,
            "schema_valid": r.schema_valid,
            "schema_error": r.schema_error,
            "failure_reason": r.failure_reason,
            "total_facts": r.total_facts,
            "passed_facts": r.passed_facts,
            "score": round(r.score, 4),
            "failed_facts": r.failed_facts,
        } for r in results],
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
