#!/bin/bash
# Run all 3 deep-research eval cases sequentially using gptase eval CLI.
# Each run temporarily swaps input.md, then restores it.

set -e
EVALS_DIR=".claude/agents/deep-research/evals"
ORIGINAL="$EVALS_DIR/input.md"
BACKUP="$EVALS_DIR/input.md.bak"

run_case() {
    local num=$1
    local input_file="$EVALS_DIR/input_${num}.md"
    echo ""
    echo "=============================="
    echo "Case $num: $(head -1 $input_file)"
    echo "=============================="
    cp "$ORIGINAL" "$BACKUP"
    cp "$input_file" "$ORIGINAL"
    conda run -n llm gptase eval -a deep-research --live --save-output
    cp "$BACKUP" "$ORIGINAL"
    rm -f "$BACKUP"
}

echo "Running case 1 (input.md — directed evolution vs rational design)..."
conda run -n llm gptase eval -a deep-research --live --save-output

run_case 2
run_case 3

echo ""
echo "All 3 cases done."
ls -lh "$EVALS_DIR/output/"
