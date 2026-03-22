# Research Continuation

Use this reference when the research task is long enough that it may need to be resumed later or handed to another agent. The goal is to preserve research state, not to promise unlimited report generation.

## What To Preserve

When pausing or handing off, record:
- the user question
- chosen mode: `quick`, `standard`, or `deep`
- subquestions
- rounds completed
- confirmed findings
- unresolved gaps
- active conflicts between sources
- next-round search plan
- citation list or source ledger

## Minimal Continuation State

```json
{
  "research_question": "Example question",
  "mode": "standard",
  "rounds_completed": 2,
  "subquestions": [
    "What does option A do well?",
    "Where does option B fail?"
  ],
  "confirmed": [
    "Official docs confirm feature X",
    "Recent benchmarks agree on lower setup cost"
  ],
  "uncertain": [
    "Independent evidence on long-term reliability is weak"
  ],
  "conflicts": [
    "Vendor claims production readiness, but user reports describe instability under scale"
  ],
  "next_round": [
    "Search for independent reliability reports from the last 12 months",
    "Look for failure cases or migration postmortems"
  ],
  "sources": [
    "[1] ...",
    "[2] ..."
  ]
}
```

## How To Resume

When resuming:

1. Read the saved state before searching again.
2. Review only enough prior material to understand the current evidence picture.
3. Continue with the `next_round` plan, unless new user input changes priorities.
4. After the resumed round, update the same state fields:
   - what is now confirmed
   - what remains uncertain
   - what conflicts remain
   - what the next round should search

## Continuation Quality Rule

Resuming should feel like a continuation of the same investigation, not a fresh start with similar keywords. If the resumed search plan cannot be traced back to previously recorded gaps or conflicts, the continuation state is not detailed enough.
