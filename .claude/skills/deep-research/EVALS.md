# Deep-Research Skill Evaluation Framework

This document describes the evaluation framework for testing the deep-research skill.

## Overview

The evaluation framework allows systematic testing of the deep-research skill against baseline performance to measure improvements.

## Directory Structure

```
evals/
├── evals.json      # Test cases with prompts and assertions
├── README.md       # This file
└── results/        # Evaluation results (created during runs)
```

## Test Cases

| ID | Name | Type | Description |
|----|------|------|-------------|
| 1 | comparison-query | Comparison | Compare PostgreSQL vs Supabase for a startup |
| 2 | trend-analysis | Trends | AI agent framework trends in 2025 |
| 3 | technical-decision | Decision | Best approach for real-time dashboard |

## Assertions

Each test case has multiple assertions that are automatically checked:

| Assertion Type | Description | Example |
|----------------|-------------|---------|
| `word_count` | Minimum word count threshold | `min_words: 2000` |
| `citation_count` | Minimum number of sources | `min_sources: 10` |
| `sections_present` | Required sections must exist | `required_sections: ["Executive Summary", ...]` |
| `content_check` | No forbidden patterns | `forbidden_patterns: ["TBD", "TODO"]` |
| `bibliography_check` | All citations have entries | `check_type: "citation_bibliography_match"` |
| `source_recency` | Percentage of recent sources | `recency_threshold: 0.5` |
| `keyword_presence` | Required keywords covered | `required_keywords: ["multi-agent", ...]` |

## Running Evaluations

### Quick Validation Test

Test the validation script with existing fixtures:

```bash
cd /Users/bytedance/Code/GPTase/.claude/skills/deep-research

# Should pass
python scripts/validate_report.py --report tests/fixtures/valid_report.md

# Should fail
python scripts/validate_report.py --report tests/fixtures/invalid_report.md
```

### JSON Output

For programmatic use:

```bash
python scripts/validate_report.py --report report.md --json
```

### Auto-Fix Mode

Attempt to automatically fix common issues:

```bash
python scripts/validate_report.py --report report.md --fix
```

## Expected Results by Mode

| Mode | Word Count | Sources | Duration |
|------|------------|---------|----------|
| Quick | 2,000+ | 10+ | 2-5 min |
| Standard | 4,000+ | 15+ | 5-10 min |
| Deep | 6,000+ | 20+ | 10-20 min |
| UltraDeep | 10,000+ | 30+ | 20-45 min |

## Adding New Test Cases

1. Add entry to `evals.json`:
```json
{
  "id": 4,
  "name": "your-test-name",
  "prompt": "The user prompt to test",
  "expected_output": "Description of expected output",
  "files": [],
  "assertions": [
    {"name": "word_count", "type": "word_count", "min_words": 2000}
  ]
}
```

2. Define relevant assertions
3. Run evaluation to verify

## Integration with skill-creator

For full benchmark testing using the skill-creator framework:

1. Create workspace directory
2. Spawn agents with skill for test prompts
3. Spawn baseline agents without skill
4. Compare outputs using eval-viewer

See skill-creator documentation for details.
