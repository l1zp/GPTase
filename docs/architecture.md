# Architecture Overview

## Agent-Tool Delegation Pattern

GPTase uses a **delegation pattern** that separates configuration from business logic:

```
Markdown Agent Definition (config/agents/*.md)
    ↓ parsed by
MarkdownAgent (generic runtime)
    ↓ delegates to
Agent (unified execution with multimodal support)
    ↓ calls
Model (LLM with vision support)
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

The `AgentOrchestrator` automatically discovers agents in `config/agents/`.

### Multimodal Support

The agent system supports multimodal messages (text + images):

```python
# Automatic image detection in MarkdownAgent
task = {
    "description": "Analyze this figure",
    "image_paths": ["figure.png"],  # Triggers multimodal handling
}
result = await agent.process_task(task)

# Direct multimodal API
from gptase.agents.agent import Agent
agent = Agent(system_prompt="You are a vision analyst.")
result = await agent.run_with_images(
    task="Extract data from this figure",
    image_paths=["figure1.png", "figure2.png"],
)
```

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
- **Multimodal support** — automatic image encoding and processing
- **Separation of concerns** — prompts in Markdown, logic in Python
- **Reusability** — tools shared across agents via configuration

---

## Unified Agent Class

The `Agent` class provides dual execution paths:

| Model Type | Execution Path | Features |
|------------|----------------|----------|
| Claude models | Claude Agent SDK | Built-in tools (bash, text_editor) |
| Other models | Custom LLM loop | Multimodal support, streaming |

```python
from gptase.agents.agent import Agent

agent = Agent(
    system_prompt="You are a helpful assistant.",
    skills=["skills/academic-pdf-reader/SKILL.md"],
    model_config=model_config,
)

# Text task
result = await agent.run("Analyze this paper")

# Multimodal task
result = await agent.run_with_images(
    task="Analyze these figures",
    image_paths=["fig1.png", "fig2.png"],
)
```

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
