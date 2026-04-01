# Deep-Research Skill Evaluations

This directory contains the evaluation cases for the iterative `deep-research` skill.

## What These Evals Test

The current eval set is designed to catch the two main failure modes of research skills:

- early stopping after one shallow search round
- writing a polished summary without enough evidence, counterevidence, or search iteration

The evals therefore focus on:
- whether the report structure matches the skill contract
- whether the report shows multiple research rounds
- whether gaps, conflicts, or uncertainties are surfaced
- whether the final recommendation is evidence-backed rather than generic

## Eval Cases

| ID | Name | What it stresses |
|----|------|------------------|
| 1 | comparison-decision | Multi-criteria technical comparison with failure modes |
| 2 | trend-landscape | Landscape/trend research with noisy or contradictory evidence |
| 3 | high-stakes-recommendation | Recommendation quality under operational tradeoffs |

## Running Validation

Use the validator against a generated Markdown report:

```bash
python scripts/validate_report.py --report tests/fixtures/valid_report.md
```

For full skill benchmarking, use the `skill-creator` workflow:
- snapshot the old skill as baseline
- run the same prompts with old and new versions
- generate the review viewer
- compare pass rates, outputs, and timing

## Assertion Philosophy

These evals no longer optimize for long reports. They optimize for better research behavior.

Preferred assertions include:
- required report sections
- evidence of multiple search rounds
- counterevidence or uncertainty handling
- enough cited sources to support synthesis

Word count should be treated as a weak signal at most. A shorter report that shows genuine iterative research is better than a longer report that only pads content.
