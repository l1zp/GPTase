---
name: deep-research
description: |
  Use this skill for research tasks that need multiple sources, explicit citation tracking, and iterative follow-up search rounds. Consult it whenever the user asks for a comparison, trend analysis, state-of-the-art review, literature or market landscape, or a recommendation that must be defended with evidence from several perspectives.

  This skill is especially important when the first search pass will not be enough: use it when you need to identify gaps or contradictions from early findings, then plan additional search rounds based on those gaps before writing conclusions.

  Do not use it for simple factual lookups, one-page summaries, debugging, coding tasks, or questions that can be answered well with one or two direct searches.
---

# Deep Research

## Purpose

Produce a citation-backed Markdown research report by running a multi-round research loop:

1. frame the question,
2. search in parallel,
3. identify gaps and contradictions from the current evidence,
4. plan the next search round from those gaps,
5. stop only when the coverage is good enough to defend a conclusion.

The point of this skill is not "find some links quickly." The point is to keep researching until the answer is grounded, balanced, and traceable.

## When To Use This Skill

Use it when the user needs any of the following:
- a comparison of tools, vendors, frameworks, products, or strategies
- a trend or landscape analysis
- a state-of-the-art or literature-style review
- a decision memo or recommendation that needs multiple sources and explicit uncertainty handling
- a research report where claims need citations and counterevidence

Do not use it when:
- a single fact lookup or short browse is enough
- the task is summarizing one provided document
- the task is debugging or implementation work
- the user wants a quick opinion rather than a research-backed answer

## Default Operating Mode

Choose the lightest mode that still supports the user's need:

- `quick`: Fast but still iterative. Minimum 2 research rounds.
- `standard`: Default. Minimum 3 research rounds.
- `deep`: Use for high-stakes or contested questions. Minimum 4 research rounds, including at least 1 round dedicated to counterevidence, failure modes, or opposing views.

If the user asks for depth but gives no further guidance, choose `standard`.

## Workflow

### 1. Frame The Research

Before searching, define:
- the core question to answer
- 3-6 subquestions that must be covered
- what evidence types matter most
  Examples: official docs, peer-reviewed work, vendor pricing, benchmarks, regulations, expert analysis
- what is likely to be controversial, stale, or easy to overclaim

State scope briefly in your own working notes. The first round is for building an evidence map, not for pretending you already know the answer.

### 2. Run The Research Loop

Each round must contain all four steps:

1. Search and read in parallel.
2. Summarize what this round established.
3. Identify what is still weak, missing, contradictory, or outdated.
4. Design the next round from those unresolved items.

Do not stop after one round just because you have enough material to write something plausible.

Treat disagreement as a first-class research artifact, not as an optional flourish. In comparison, trend, and landscape work, assume that at least some important sources will disagree on definitions, maturity, benchmarks, market sizing, or operational reality. Look for those disagreements on purpose.

### 3. Search In Parallel

In every round, launch multiple searches at once across the relevant source types. Mix source classes where the question demands it:
- broad web or news coverage
- official documentation or company material
- academic or technical sources
- critical or opposing viewpoints

Aim for **3-5 distinct source URLs per round**. A round that reads only 1-2 pages is rarely enough to triangulate a claim across different perspectives. Each distinct URL you read and find useful becomes a numbered citation — do not merge multiple fetched pages into a single citation entry.

Use the first round to get coverage. Use later rounds to close specific gaps. Later rounds should not be generic re-searches with slightly different wording; they should be driven by what previous rounds failed to settle.

### 4. Explicitly Plan The Next Round

After each round, create a short internal research log with:
- `confirmed`: what now looks well supported
- `uncertain`: what still lacks enough support
- `conflicts`: where sources disagree or frame the issue differently
- `next_round`: the exact questions the next round must answer

Do not leave `conflicts` empty just because you found strong sources. Check for at least one of:
- different numbers or timelines across sources
- vendor claims that overstate what critical sources support
- disagreement about terminology or category boundaries
- benchmark results or practitioner reports that point in different directions

If a round truly finds no meaningful conflict, say that explicitly and explain what you checked.

Good next rounds are driven by one of these:
- `gap-driven`: a subquestion still lacks evidence
- `conflict-driven`: sources disagree and need arbitration
- `recency-driven`: the available evidence may be outdated
- `counterevidence-driven`: the current case is one-sided and needs opposing evidence
- `depth-driven`: the conclusion is directionally clear, but the user needs mechanisms, limits, or scale

When a next round is `conflict-driven`, name the conflict concretely.
Good: "Vendor adoption claims say production use is widespread, but practitioner surveys show low scaled deployment. Resolve whether this is a definition mismatch or genuine disagreement."
Bad: "Look for more sources about adoption."

### 5. Stop Only When Coverage Is Good Enough

You may stop the loop only when all of the following are true:
- the core subquestions have usable evidence coverage
- key claims are either triangulated or clearly marked as not fully verifiable
- the most recent round mostly added detail rather than overturning the working conclusion
- counterevidence, limitations, or failure modes have been actively checked
- there is no obvious high-priority gap left unsearched
- any remaining source disagreements have been explained, bounded, or incorporated into the uncertainty section

You must continue the loop if any of the following is true:
- a major conclusion depends on one source or one source type
- important sources disagree and you have not explained why
- a user-important dimension has barely been investigated
- the evidence may be stale for a time-sensitive question
- you are still listing information rather than making a defensible synthesis
- you have fewer than 8 distinct cited sources for `standard` or `deep` mode (fewer than 5 for `quick`). Low source count is a signal of insufficient coverage, not of efficient synthesis. If you reach what feels like a natural stopping point but have fewer sources than the minimum, run one more targeted round to widen the source base — use search queries to find source types you haven't represented yet (independent comparisons, practitioner write-ups, pricing analyses, third-party benchmarks).

## Evidence Standards

- Put citations close to factual claims.
- Distinguish facts from synthesis.
  Good: "Vendor A introduced feature X in 2025 [3]. This suggests the adoption curve is accelerating."
  Bad: "Research shows the market is clearly accelerating."
- Admit uncertainty directly when evidence is thin.
- Seek counterevidence before finalizing recommendations.
- Prefer source diversity over volume padding.
- When sources disagree, say what the disagreement is, why it might exist, and how it affects confidence.
- Prefer arbitration over averaging. Do not flatten incompatible sources into a fake consensus.

## Pre-Report Source Check

Before writing the report, do a quick count of how many distinct cited sources you have accumulated. This is not about padding — it is a sanity check that your research covered enough ground to make the conclusions traceable.

- `standard` or `deep` mode: you need at least **8 distinct sources**
- `quick` mode: you need at least **5 distinct sources**

If you are below the threshold, run one more targeted research round focused on source diversity. Use search queries rather than directly fetching full pages — search result summaries are usually enough to evaluate a source and generate a citation. Look for source types you haven't represented yet:
- **If you've used mostly official docs**: search for independent comparisons, pricing analyses, or practitioner write-ups
- **If you've used mostly blog posts**: add official documentation, pricing pages, or changelog entries
- **If all your sources are from the same 1-2 organizations**: search for third-party coverage, user reviews, or benchmark analyses from independent sources

The goal is not to contradict your conclusion — it's to give the reader enough reference points to trust it. A report with 3-5 sources, even a well-written one, leaves the reader unable to verify the most important claims independently.

## Report Contract

Primary output is a Markdown report following the template in [templates/report_template.md](./templates/report_template.md).
Use the template headings verbatim unless the user explicitly asks for a different format. Do not paraphrase required headings such as `## Conclusion or Recommendation`.

Required sections:
- `## Executive Summary`
- `## Research Question and Scope`
- `## Research Process`
- `## Key Findings`
- `## Counterevidence and Uncertainties`
- `## Conclusion or Recommendation`
- `## Sources`

The `Research Process` section is mandatory because it proves the work was iterative rather than a one-pass browse. Keep it concise, but include:
- number of rounds
- what each round focused on
- what gaps or conflicts triggered the next round
- for any meaningful disagreement, one line on how it was investigated or bounded

Inside `## Research Process`, prefer explicit round subheadings that match the template:
- `### Round 1`
- `### Round 2`
- `### Round 3` and beyond when needed
- `### Remaining Gaps`

For `comparison`, `trend`, `landscape`, and `state-of-the-art` tasks, make the conflict handling visible in the report:
- include at least one explicit source disagreement in `Research Process`, `Key Findings`, or `Counterevidence and Uncertainties`
- explain how that disagreement changed the next search round or reduced confidence in the final conclusion
- if the conclusion depends on choosing one interpretation over another, justify that choice explicitly

For `trend`, `landscape`, and `state-of-the-art` tasks, do not summarize rounds generically.
Inside `## Research Process`, each round should usually include short labeled lines such as:
- `Focus:`
- `Established:`
- `Conflict:` or `Conflicts:`
- `Next round:`

If no meaningful disagreement was found in a round, write `Conflict: none found after checking X and Y`, then still write `Next round:` based on the remaining gap, recency risk, or depth question. Do not omit `Next round:` just because the report can already be written.

Good visible patterns:
- "Conflict: vendor-reported adoption counts include pilots, while survey data counts scaled production only. Next round: find deployment-stage definitions and comparable surveys."
- "Arbitration: we treat production metrics as stronger than marketing-era adoption counts, so adoption claims are reported as mixed rather than settled."

## Sources Format

The `## Sources` section must be validator-friendly and traceable:
- put each source on its own line
- use bracketed numbering that matches in-text citations exactly: `[1] ...`, `[2] ...`, `[3] ...`
- do not switch to `1.` or bullet lists in this section
- do not include uncited bibliography padding just to make the list longer

Good:
- `[1] Organization or author. Title. URL or source detail.`
- `[2] Organization or author. Title. URL or source detail.`

Bad:
- `1. Organization or author...`
- `- Organization or author...`
- `[1-5] Additional sources`

**Do not consolidate multiple fetched pages into one citation.** If you read a vendor's "Permissions Guide" and "Maintenance Guide" as separate pages, those are two citations. Catch-all entries like "[1] Metabase Documentation. All docs." obscure your evidence trail and inflate what each citation actually covers. Each specific page, article, or document you read and found useful earns its own numbered entry.

## Validation

Before delivering, run the report validator when feasible:

```bash
python scripts/validate_report.py --report [path]
```

Use citation verification when the environment and time budget justify it, especially for high-stakes work:

```bash
python scripts/verify_citations.py --report [path]
```

Treat `verify_citations.py` as a stricter optional audit, not as a reason to skip delivery when network conditions make it unreliable.

## Supporting References

Load references only when needed:
- [reference/methodology.md](./reference/methodology.md) for multi-round search strategy and stop rules
- [reference/continuation.md](./reference/continuation.md) for resuming a long research task while preserving search state
- [templates/report_template.md](./templates/report_template.md) for the output structure

Do not load HTML or PDF generation guidance unless the user explicitly asks for those formats.
