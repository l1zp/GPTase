# Deep Research Methodology

This reference supports the main skill with a practical method for iterative research. The main idea is simple: each search round should change the next one.

## Research Loop

For every round, do these in order:

1. Search in parallel across the source types that matter.
2. Read enough to extract real claims, not just headlines.
3. Update the working evidence map.
4. Decide whether another round is needed, and why.

If the next round looks the same as the previous one, the planning step was not specific enough.

## Frame The Question

Before round 1, define:
- the main question
- 3-6 subquestions
- what would count as a strong answer
- what could make the answer misleading

Useful framing dimensions:
- technical capability
- cost or operational tradeoffs
- time sensitivity
- adoption or real-world usage
- limitations, risks, and failure modes
- disagreement between source communities

## Round 1: Build Coverage

The first round should create breadth, not certainty.

Target outputs:
- a preliminary source map
- early patterns
- candidate disagreements
- a list of missing evidence

Recommended search mix:
- one broad overview query
- one terminology or implementation query
- one recency-focused query
- one official or documentation query
- one critical or comparison query
- one academic or technical query if the topic warrants it

## Evidence Map

Maintain a lightweight internal structure:

- `subquestion`
- `current answer`
- `source types seen`
- `confidence`
- `gaps`
- `conflicts`

This does not need to be shown verbatim to the user, but it should drive the next round.

## How To Plan The Next Round

Every additional round should be triggered by something specific from the current evidence.

### Gap-driven follow-up

Use when a subquestion still lacks enough evidence.

Examples:
- "We found feature claims but not pricing evidence."
- "We found vendor statements but no independent benchmarking."

### Conflict-driven follow-up

Use when sources disagree in a meaningful way.

Examples:
- vendor docs say feature maturity is production-ready, but community reports describe instability
- two market reports disagree on adoption or growth

Follow-up goal:
- identify why they differ
- compare dates, incentives, methodology, and scope

### Recency-driven follow-up

Use when the answer could have changed recently.

Examples:
- pricing
- product capabilities
- regulations
- company or model releases

Follow-up goal:
- verify the latest state with recent and preferably primary sources

### Counterevidence-driven follow-up

Use when the current case is too one-sided.

Examples:
- only success stories found
- only official materials found
- recommendation is forming before limitations were checked

Follow-up goal:
- search for failures, criticisms, alternatives, and boundary conditions

### Depth-driven follow-up

Use when the direction is clear but the explanation is still shallow.

Examples:
- "We know tool A is favored, but not why it wins in this user's setting."
- "We know the trend exists, but not which mechanism is causing it."

## Stop Rules

The loop can stop only when:
- all major subquestions have at least some credible evidence coverage
- important disagreements are either resolved or clearly described
- a counterevidence round has been done for `deep` mode and, when relevant, for `standard`
- the last round mainly sharpened the picture rather than changing the whole story

The loop must continue when:
- you still have a major blind spot
- one source family dominates the answer
- the conclusion still feels like a stitched-together summary rather than synthesis
- the user's decision hinges on a point that remains weakly evidenced

## Writing From The Evidence

When synthesizing:
- move from evidence to conclusion, not the other way around
- separate "what sources say" from "what this implies"
- explain why conflicting evidence was weighted differently
- keep unresolved uncertainty visible

Good synthesis sounds like:
"Recent vendor docs and release notes support X [2][4], but independent practitioner reports describe operational limits under scale [7][8]. That makes X plausible for small teams, but less certain for larger deployments."

## Research Process Section

The final report should include a concise process log. A useful pattern is:

- `Round 1:` what you searched for and what it established
- `Round 2:` what gaps or conflicts it targeted
- `Round 3:` what changed after targeted follow-up
- `Remaining uncertainty:` what is still open

This section should prove that the report came from iterative research, not from a single search pass.
