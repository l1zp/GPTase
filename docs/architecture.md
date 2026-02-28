# Architecture Overview

## Agent-Tool Delegation Pattern

GPTase uses a **delegation pattern** that separates configuration from business logic:

```
Markdown Agent Definition (config/agents/*.md)
    ↓ parsed by
MarkdownAgent (generic runtime)
    ↓ delegates to
Tool (business logic, src/tools/)
    ↓ calls
Model (LLM, src/models/)
```

### Agent Layer — Zero-Code Configuration

Agents are defined as Markdown files with HTML comment metadata. No Python code required.

```markdown
<!--
@agent_id: my_agent
@tools: my_tool
@model_role: general
@temperature: 0.0
-->
## System Prompt
You are a specialized expert...
## Task Processing
1. Use my_tool to process data
```

The `AgentOrchestrator` automatically discovers agents in `config/agents/` via the `AGENT_IDS` list.

### Tool Layer — Business Logic

Tools inherit from `BaseTool` and encapsulate all computation:

```python
class MyTool(BaseTool):
    def __init__(self):
        super().__init__(name="my_tool", description="...")

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.success(data)
```

### Benefits

- **Zero-code agents** — new agents = new `.md` file
- **Separation of concerns** — prompts in Markdown, logic in Python
- **Reusability** — tools shared across agents via configuration

---

## Planner — 5-Phase Workflow

For complex tasks, the **Planner Agent** provides a 5-phase interactive planning system:

| Phase | Goal | Output |
|-------|------|--------|
| 1. Understanding | Clarify requirements | Questions & suggestions |
| 2. Design | Create workflow | Steps, agents, risks |
| 3. Review | User validation | Approval / modifications |
| 4. Final Plan | Generate executable JSON | `data/plans/{plan_id}.json` |
| 5. Exit | Confirm before execution | Ready-to-execute flag |

### Usage

```bash
# Interactive planning demo
python examples/enzyme_design_planner_demo.py data/listov2025/listov2025.md

# Auto-approve (testing)
python examples/enzyme_design_planner_demo.py data/listov2025/listov2025.md --auto
```

### Programmatic API

```python
result = await orchestrator.execute_task({
    "id": "my_task",
    "description": "Extract enzyme kinetics from paper",
    "use_planner": True,
    "phase": 1,
    "user_input": ""
})
```

Plans are saved to `data/plans/{plan_id}.json` and executed by the **Executor Agent** (`config/agents/executor.md`) with `{{stepN.path}}` variable interpolation.

---

## SOP (Standard Operating Procedure)

Pre-defined pipelines in `config/sops/`:

```json
{
  "plan_id": "enzyme_extraction_pipeline",
  "workflow": [
    {"step_id": 1, "agent": "document_structure_analyzer", "inputs": {...}},
    {"step_id": 2, "agent": "enzyme_kinetics_extractor", "inputs": {"text": "{{step1.output}}"}},
    {"step_id": 3, "agent": "enzyme_extraction_summary", "inputs": {"data": "{{step2.output}}"}}
  ]
}
```

Run via: `python examples/reaction_extractor.py -i data/paper.md`
