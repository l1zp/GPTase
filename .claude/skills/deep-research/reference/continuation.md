# Auto-Continuation Protocol

This document describes the unlimited-length report generation system for the deep-research skill.

## Overview

The deep-research skill supports unlimited report length through progressive file assembly and auto-continuation. This allows reports exceeding 20,000 words to be generated across multiple agent invocations.

## Token Limits

Claude Code default limit: 32,000 output tokens (approximately 24,000 words total per skill execution). This is a HARD LIMIT.

**Realistic report sizes per mode:**
- Quick mode: 2,000-4,000 words (well under limit)
- Standard mode: 4,000-8,000 words (comfortably under limit)
- Deep mode: 8,000-15,000 words (achievable with care)
- UltraDeep mode: 15,000-20,000 words (at limit, monitor closely)

## Progressive File Assembly

### Strategy

Generate and write each section individually using Write/Edit tools. This allows the file to grow without any single tool call exceeding limits.

**Pattern:** Generate section content → Use Write/Edit tool → Move to next section

Each Write/Edit call contains ONE section (maximum 2,000 words per call).

### Section Generation Loop

1. **Executive Summary** (200-400 words)
   - Tool: Write(file, content=frontmatter + Executive Summary)
   - Track citations used

2. **Introduction** (400-800 words)
   - Tool: Edit(file, append Introduction section)

3. **Findings** (600-2,000 words each)
   - Each finding = one Edit tool call
   - Track citations per finding

4. **Synthesis & Insights**
   - Generate novel insights beyond source material

5. **Limitations & Caveats**
   - Counterevidence, gaps, uncertainties

6. **Recommendations**
   - Immediate actions, next steps, research needs

7. **Bibliography (CRITICAL)**
   - COMPLETE bibliography with EVERY citation
   - NO ranges ([1-50]), NO placeholders
   - Verify against citations_used list

8. **Methodology Appendix**
   - Research process, verification approach

## Auto-Continuation Decision Point

After generating sections, check word count:

**If total output <= 18,000 words:** Complete normally
- Generate complete bibliography
- Run validation
- Done

**If total output will exceed 18,000 words:** Auto-Continuation Protocol

### Step 1: Save Continuation State

Create file: `~/.claude/research_output/continuation_state_[report_id].json`

```json
{
  "version": "2.1.1",
  "report_id": "[unique_id]",
  "file_path": "[absolute_path_to_report.md]",
  "mode": "[quick|standard|deep|ultradeep]",
  "progress": {
    "sections_completed": ["executive_summary", "introduction", "finding_1", ...],
    "total_planned_sections": 15,
    "word_count_so_far": 16500,
    "continuation_count": 1
  },
  "citations": {
    "used": [1, 2, 3, ..., 45],
    "next_number": 46,
    "bibliography_entries": [
      "[1] Full citation entry",
      "[2] Full citation entry"
    ]
  },
  "research_context": {
    "research_question": "[original question]",
    "key_themes": ["theme1", "theme2", "theme3"],
    "main_findings_summary": [
      "Finding 1: [100-word summary]",
      "Finding 2: [100-word summary]"
    ],
    "narrative_arc": "middle"
  },
  "quality_metrics": {
    "avg_words_per_finding": 1500,
    "citation_density": 3.2,
    "prose_vs_bullets_ratio": "85% prose",
    "writing_style": "technical-precise-data-driven"
  },
  "next_sections": [
    {"id": 10, "type": "finding", "title": "Finding 8", "target_words": 1500},
    {"id": 11, "type": "synthesis", "title": "Synthesis", "target_words": 1000}
  ]
}
```

### Step 2: Spawn Continuation Agent

Use Task tool with general-purpose agent:

```
Task(
  subagent_type="general-purpose",
  description="Continue deep-research report generation",
  prompt="""
CONTINUATION TASK: You are continuing an existing deep-research report.

CRITICAL INSTRUCTIONS:
1. Read continuation state file: ~/.claude/research_output/continuation_state_[report_id].json
2. Read existing report to understand context: [file_path from state]
3. Read LAST 3 completed sections to understand flow and style
4. Load research context: themes, narrative arc, writing style from state
5. Continue citation numbering from state.citations.next_number
6. Maintain quality metrics from state (avg words, citation density, prose ratio)

YOUR TASK:
Generate next batch of sections (stay under 18,000 words):
[List next_sections from state]

Use Write/Edit tools to append to existing file: [file_path]

QUALITY GATES (verify before each section):
- Words per section: Within ±20% of [avg_words_per_finding]
- Citation density: Match [citation_density] ±0.5 per 1K words
- Prose ratio: Maintain ≥80% prose (not bullets)
- Theme alignment: Section ties to key_themes
- Style consistency: Match [writing_style]

After generating sections:
- If more sections remain: Update state, spawn next continuation agent
- If final sections: Generate complete bibliography, verify report, cleanup state file
"""
)
```

### Step 3: Report Continuation Status

Tell user:
```
Report Generation: Part 1 Complete (N sections, X words)
Auto-continuing via spawned agent...
   Next batch: [section list]
   Progress: [X%] complete
```

## Continuation Agent Quality Protocol

When continuation agent starts:

**Context Loading (CRITICAL):**
1. Read continuation_state.json → Load ALL context
2. Read existing report file → Review last 3 sections
3. Extract patterns:
   - Sentence structure complexity
   - Technical terminology used
   - Citation placement patterns
   - Paragraph transition style

**Pre-Generation Checklist:**
- [ ] Loaded research context (themes, question, narrative arc)
- [ ] Reviewed previous sections for flow
- [ ] Loaded citation numbering (start from N+1)
- [ ] Loaded quality targets (words, density, style)
- [ ] Understand where in narrative arc (beginning/middle/end)

**Per-Section Generation:**
1. Generate section content
2. Quality checks:
   - Word count: Within target ±20%
   - Citation density: Matches established rate
   - Prose ratio: ≥80% prose
   - Theme connection: Ties to key_themes
   - Style match: Consistent with quality_metrics.writing_style
3. If ANY check fails: Regenerate section
4. If passes: Write to file, update state

**Handoff Decision:**
- Calculate: Current word count + remaining sections × avg_words_per_section
- If total < 18K: Generate all remaining sections + finish
- If total > 18K: Generate partial batch, update state, spawn next agent

## Final Agent Responsibilities

- Generate final content sections
- Generate COMPLETE bibliography using ALL citations from state.citations.bibliography_entries
- Read entire assembled report
- Run validation: `python scripts/validate_report.py --report [path]`
- Delete continuation_state.json (cleanup)
- Report complete to user with metrics
