---
name: research-planning
description: |
  Plan and execute complex research tasks requiring multi-step, multi-tool collaboration.
  Use this skill whenever the user needs to plan research, conduct literature review, analyze data from multiple sources, or execute multi-step workflows.
  Triggers on: "plan this research", "literature review", "research plan", "multi-step analysis", "help me plan", "create a research proposal", "design a workflow", "propose a plan", "how should I approach this research".
---

# Research Planning

Plan and execute complex research tasks. Use for scenarios requiring multi-step, multi-tool collaboration such as enzymology research, literature review, data analysis, etc.

## Overview

Provides systematic research task planning methodology. Decomposes complex tasks into executable phases, each with clear inputs, outputs, and validation criteria.

## When to Use

- Task involves multiple steps or multiple data sources
- Need to research before executing
- User explicitly requests "planning" or "proposal"

## Planning Phases

### Phase 1: Requirements Analysis

1. **Parse task**: Extract key information from user input
   - Research object (enzyme name, reaction type, gene, etc.)
   - Target output (data table, report, comparative analysis, etc.)
   - Constraints (time range, data source limitations, etc.)

2. **Background research**: Use WebSearch to quickly understand domain status
   - Search 2-3 keywords to get overview
   - Identify available data sources and databases

3. **Output**: Requirements list + Existing data overview

### Phase 2: Solution Design

1. **Determine data sources**: List databases/APIs to query
   - Use API endpoints from `biochem_databases` skill
   - Determine query parameters and filter conditions

2. **Design workflow**: Order execution steps by dependencies

   ```
   Example steps:
   1. Query OpenAlex for related papers
   2. Download PDF and extract data with academic-pdf-reader
   3. Query PDB for protein structures
   4. Query KEGG for metabolic pathways
   5. Integrate data and generate report
   ```

3. **Output**: Execution plan (step list + expected output format)

### Phase 3: Execution

Execute step by step according to plan. After each step:

1. **Validate results**: Check output format and completeness
2. **Record progress**: Update completed steps
3. **Adjust plan**: Modify subsequent steps based on intermediate results

### Phase 4: Summary

1. **Integrate data**: Merge outputs from each step
2. **Quality check**:
   - [ ] All required data obtained?
   - [ ] Data format consistent?
   - [ ] Any missing or contradictory data?
3. **Generate final report**

## Quality Standards

- Each data point should have source attribution
- Numerical data should include units
- Mark uncertainties explicitly
- If a step fails, record reason and try alternative approach

## Common Patterns

### Enzymology Research
```
OpenAlex (papers) -> PDF Reader (extract) -> PDB (structure) -> KEGG (pathway) -> Report
```

### Literature Review
```
OpenAlex (search) -> PDF Reader (analyze each) -> Comparison table -> Review report
```

### Protein Analysis
```
UniProt (sequence) -> PDB (structure) -> ExPASy (enzyme info) -> Rhea (reaction) -> Summary
```
