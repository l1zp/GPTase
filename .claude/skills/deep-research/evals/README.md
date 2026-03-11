# Deep-Research Skill Evaluations

This directory contains the evaluation framework for testing the deep-research skill.

## Structure

```
evals/
├── evals.json      # Test cases with prompts and assertions
├── README.md       # This file
└── results/        # Evaluation results (created during runs)
```

## Test Cases

| ID | Name | Description |
|----|------|-------------|
| 1 | comparison-query | Compare PostgreSQL vs Supabase for a startup |
| 2 | trend-analysis | AI agent framework trends in 2025 |
| 3 | technical-decision | Best approach for real-time dashboard |

## Running Evaluations

### Quick Test (Single Eval)

```bash
# Run a single test case manually
cd /Users/bytedance/Code/GPTase/.claude/skills/deep-research
python scripts/validate_report.py --report tests/fixtures/valid_report.md
```

### Full Evaluation (with skill-creator)

1. **Create workspace:**
   ```bash
   mkdir -p deep-research-workspace/iteration-1
   ```

2. **Spawn test agents:**
   - Use the skill-creator workflow to spawn agents with the deep-research skill
   - Spawn baseline agents without the skill
   - Capture outputs and timing data

3. **Review results:**
   ```bash
   python <skill-creator-path>/eval-viewer/generate_review.py \
     deep-research-workspace/iteration-1 \
     --skill-name "deep-research" \
     --benchmark deep-research-workspace/iteration-1/benchmark.json
   ```

## Assertions

Each test case has multiple assertions that are checked:

| Assertion Type | Description |
|----------------|-------------|
| `word_count` | Minimum word count threshold |
| `citation_count` | Minimum number of sources cited |
| `sections_present` | Required sections must exist |
| `content_check` | No forbidden patterns (TBD, TODO) |
| `bibliography_check` | All citations have bibliography entries |
| `source_recency` | Percentage of recent sources |
| `keyword_presence` | Required keywords/topics covered |
| `section_quality` | Quality checks for specific sections |

## Expected Results

For a well-functioning deep-research skill:

- **Quick mode**: 2,000+ words, 10+ sources, 3-5 min
- **Standard mode**: 4,000+ words, 15+ sources, 5-10 min
- **Deep mode**: 6,000+ words, 20+ sources, 10-20 min

## Adding New Test Cases

1. Add a new entry to `evals.json`:
   ```json
   {
     "id": 4,
     "name": "your-test-name",
     "prompt": "The user prompt to test",
     "expected_output": "Description of expected output",
     "files": [],
     "assertions": [...]
   }
   ```

2. Define relevant assertions for your test case

3. Run the evaluation to verify the skill handles it correctly
