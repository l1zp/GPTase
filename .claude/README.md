# Claude Code Skills & Hooks

Automated workflows and hooks for GPTase development.

## Skills

Skills are reusable prompts that run with a single `/command`.

### /docs - Batch Documentation Updates

Updates documentation for features and modules in batch.

**Usage:**
```
/docs
Update documentation for the enzyme_kinetics_extractor agent
```

**What it does:**
- Finds all related .md files
- Identifies inconsistencies with current code
- Proposes structured update plan
- Updates all docs in a focused batch
- Verifies code examples

**When to use:** After changing agent APIs, tool parameters, or workflow behavior

### /refactor - Scope-Safe Refactoring

Clarifies architectural scope before reorganization work.

**Usage:**
```
/refactor
Restructure the enzyme tools
```

**What it does:**
- Asks for scope clarification (domain-specific vs generic)
- Confirms understanding before proceeding
- Identifies architectural boundaries
- Uses appropriate patterns (MCP vs framework)

**When to use:** Before any code reorganization, tool restructuring, or architectural changes

## Hooks

Hooks automatically run shell commands at specific events.

### After Edit Hook

Automatically formats Python files after edits:
- Runs `isort` to sort imports
- Runs `yapf` to format code

**Benefit:** Maintains consistent code style without manual formatting

## Why These Exist

Based on usage analysis of 545 sessions:
- **146 documentation updates** → /docs skill prevents scattered doc updates
- **146 reorganization efforts** → /refactor skill prevents scope misunderstandings
- **203 commits** → hooks ensure consistent formatting across changes

## Customization

Edit skill files in `.claude/skills/*/SKILL.md` to customize workflows.
Edit `.claude/settings.json` to modify hooks.
