# Planner Feature Documentation

## Overview

The Planner feature implements a 5-phase planning system for complex enzyme design workflow planning. The planner generates plans and waits for user confirmation before execution, similar to opencode's plan mode.

## Use Cases

- **Complex Task Planning**: Break down complex enzyme design tasks into manageable steps
- **Multi-Agent Coordination**: Orchestrate multiple specialized agents in a workflow
- **Interactive Planning**: Refine plans through iterative user feedback
- **Resource Estimation**: Assess time, resources, and risks before execution
- **Validation**: Ensure plans are complete and executable before running

## Architecture

```
User Request
    ↓
PlannerAgent (Markdown-based, config/agents/planner.md)
    ↓
PlanningTool (Business logic, src/tools/planner_tool.py)
    ↓
PlanStorage (data/plans/{plan_id}.json)
    ↓ [User Confirmation]
ExecutorAgent (Markdown-based, config/agents/executor.md)
    ↓
ExecutorTool (Business logic, src/tools/executor_tool.py)
    ↓
Execution (existing enzyme design agents)
```

## 5-Phase Planning Workflow

### Phase 1: Initial Understanding

**Goal**: Understand task requirements and gather context.

**Activities**:
- Analyze task description
- Identify primary objectives and success criteria
- Ask clarifying questions about constraints, resources, and expectations
- Provide suggestions for potential approaches

**Output**:
```json
{
  "understanding": "Analysis of what needs to be done",
  "questions": [
    "What specific parameters are needed?",
    "What constraints exist?",
    "What documents are available?",
    "What outputs are expected?"
  ],
  "suggestions": [
    "Suggested approach",
    "Recommended tools/agents"
  ]
}
```

### Phase 2: Design Approach

**Goal**: Create detailed implementation strategy.

**Activities**:
- Design multi-step workflow
- Assign appropriate agents to each step
- Specify inputs, outputs, and dependencies
- Identify risks and mitigation strategies
- Estimate duration and resource requirements

**Output**:
```json
{
  "approach": "High-level implementation strategy",
  "steps": [
    {
      "step_number": 1,
      "description": "What this step does",
      "agent": "enzyme_kinetics_extractor",
      "action": "extract_kinetics",
      "inputs": {"document_path": "path/to/doc.md"},
      "expected_outputs": "Description of outputs"
    }
  ],
  "risks": ["Risk 1", "Risk 2"],
  "mitigations": ["Mitigation 1", "Mitigation 2"],
  "estimated_duration_hours": 4
}
```

### Phase 3: Review and Validation

**Goal**: Present plan and collect user feedback.

**Activities**:
- Present plan in clear, human-readable format
- Address user concerns and feedback
- Incorporate suggested modifications
- Validate plan completeness and feasibility

**Output**:
```json
{
  "plan_summary": "Clear summary of the plan",
  "approved": true,
  "concerns": ["Any concerns identified"],
  "modifications": ["Changes needed if not approved"]
}
```

### Phase 4: Final Plan Generation

**Goal**: Generate executable workflow JSON.

**Activities**:
- Create executable workflow specification
- Validate all steps are properly configured
- Ensure agent availability and action compatibility
- Save plan to persistent storage

**Output**:
```json
{
  "workflow": [
    {
      "agent": "enzyme_kinetics_extractor",
      "action": "extract_kinetics",
      "inputs": {"document_path": "data/papers/paper1.md"},
      "description": "Extract kinetic parameters"
    }
  ],
  "plan_path": "data/plans/plan_20250204_123456.json",
  "total_steps": 3
}
```

**Plan File Structure**:
```json
{
  "plan_id": "plan_20250204_123456",
  "task": {
    "description": "Design thermostable lipase variant",
    "objectives": ["Increase Tm by 10°C", "Maintain kcat/KM"]
  },
  "workflow": [
    {
      "step_id": 1,
      "agent": "enzyme_design_extractor",
      "action": "extract_design_workflow",
      "inputs": {"document_path": "data/listov2025.md"},
      "outputs": {"workflow_data": "..."}
    }
  ],
  "phases": {
    "phase_1": {"status": "completed", "understanding": "...", "completed_at": "..."},
    "phase_2": {"status": "completed", "approach": "...", "steps": [...]},
    "phase_3": {"status": "completed", "approved": true},
    "phase_4": {"status": "completed", "workflow": [...]},
    "phase_5": {"status": "completed", "ready_to_execute": true}
  },
  "status": "awaiting_approval",
  "metadata": {
    "created_at": "2025-02-04T12:34:56",
    "estimated_duration_hours": 4
  }
}
```

### Phase 5: Exit and Approval

**Goal**: Request final confirmation before execution.

**Activities**:
- Present complete plan summary
- Warn about potential issues
- Request final user confirmation
- Set plan status for execution

**Output**:
```json
{
  "ready_to_execute": true,
  "next_steps": [
    "Step 1: Execute workflow step 1",
    "Step 2: Execute workflow step 2"
  ],
  "warnings": ["Any warnings or cautions"]
}
```

## Available Agents for Enzyme Design

| Agent | Description | Actions |
|-------|-------------|---------|
| `enzyme_kinetics_extractor` | Extract kinetic parameters | `extract_kinetics`, `extract_mutations`, `extract_conditions` |
| `enzyme_design_extractor` | Extract design workflows | `extract_design_workflow`, `extract_optimization_cycles` |
| `vision_image_analyzer` | Analyze figures and tables | `analyze_figure`, `extract_table_data` |
| `enzyme_extraction_summary` | Generate summaries | `generate_summary`, `analyze_performance` |

## Usage

### Interactive Planning

```python
from src.agents.orchestrator import AgentOrchestrator
from src.core.config import FrameworkConfig

async def plan_enzyme_analysis():
    config = FrameworkConfig()
    orchestrator = AgentOrchestrator(config)

    # Start planning
    task = {
        "id": "my_task",
        "description": "Extract enzyme kinetics from data/papers/lipase_study.md",
        "use_planner": True,
        "phase": 1,
        "user_input": ""
    }

    result = await orchestrator.execute_task(task)
    plan_id = result["plan_id"]

    # Continue with user input
    task["plan_id"] = plan_id
    task["phase"] = 2
    task["user_input"] = "The objectives are to extract Km, kcat, and Tm values"

    result = await orchestrator.execute_task(task)

    # Continue through phases 3-5...
```

### Direct Execution

```python
# Execute an approved plan
task = {
    "id": "my_task",
    "plan_id": "plan_20250204_123456"
}

result = await orchestrator.execute_task(task)
```

### Command Line Demo

```bash
# Enzyme design planning demo (recommended)
python examples/enzyme_design_planner_demo.py data/listov2025/listov2025.md

# Auto-approve mode (for testing)
python examples/enzyme_design_planner_demo.py data/listov2025/listov2025.md --auto
```

## Configuration

### Planner Agent Configuration

Located in `config/agents/planner.md`:

```markdown
@agent_id: planner
@capabilities: requirement_analysis, workflow_design, resource_estimation
@requires_model: true
@model_role: planning
@temperature: 0.1
```

### Executor Agent Configuration

Located in `config/agents/executor.md`:

```markdown
@agent_id: executor
@capabilities: plan_execution, agent_orchestration, result_aggregation
@requires_model: false
@model_role: general
```

## Enzyme Design Integration

### Example: Complete Enzyme Analysis Workflow

```python
# This creates a plan for:
# 1. Extract design workflow
# 2. Extract kinetic parameters
# 3. Analyze figures
# 4. Generate summary report

task = {
    "id": "enzyme_analysis_001",
    "description": """
    Analyze enzyme design paper at data/listov2025.md.

    Objectives:
    - Extract complete design workflow
    - Extract kinetic parameters for all variants
    - Analyze figures for additional data
    - Generate comprehensive summary report
    """,
    "use_planner": True,
    "phase": 1,
    "user_input": ""
}

result = await orchestrator.execute_task(task)
```

The planner will create a workflow similar to:

```json
{
  "workflow": [
    {
      "step_id": 1,
      "agent": "enzyme_design_extractor",
      "action": "extract_design_workflow",
      "inputs": {"document_path": "data/listov2025.md"}
    },
    {
      "step_id": 2,
      "agent": "enzyme_kinetics_extractor",
      "action": "extract_kinetics",
      "inputs": {"document_path": "data/listov2025.md"}
    },
    {
      "step_id": 3,
      "agent": "vision_image_analyzer",
      "action": "analyze_figure",
      "inputs": {"document_path": "data/listov2025.md", "figure_number": "all"}
    },
    {
      "step_id": 4,
      "agent": "enzyme_extraction_summary",
      "action": "generate_summary",
      "inputs": {"extraction_path": "data/output/listov2025/extraction.json"}
    }
  ]
}
```

## Error Handling

### Planning Errors

```python
result = await orchestrator.execute_task(task)

if result["status"] == "error":
    error = result.get("data", {}).get("error")
    print(f"Planning failed: {error}")
    # Handle error, possibly retry or modify task
```

### Execution Errors

```python
result = await orchestrator.execute_task({"plan_id": plan_id})

summary = result.get("execution_summary", {})
if summary.get("failed_steps", 0) > 0:
    print(f"Partial execution: {summary['completed_steps']}/{summary['total_steps']} completed")
    # Check step_results for details
```

## Best Practices

1. **Provide Clear Task Descriptions**: Include objectives, constraints, and expected outputs
2. **Answer Questions Thoroughly**: Phase 1 questions help create better plans
3. **Review Carefully**: Phase 3 is your chance to catch issues before execution
4. **Start Small**: Test planning with simple tasks before complex workflows
5. **Check Plan Files**: Review `data/plans/{plan_id}.json` to understand the structure
6. **Use Auto-Approve for Testing**: The `--auto` flag is useful for CI/CD pipelines

## Troubleshooting

### Planner Not Available

```
Failed to initialize agent planner: ...
```

**Solution**: Ensure `config/agents/planner.md` exists and is valid.

### Plan Not Found

```
Plan not found: data/plans/plan_20250204_123456.json
```

**Solution**: Check that Phase 4 completed successfully and plan was saved.

### Execution Fails at Step

```
Step 2 failed: Image file not found
```

**Solution**: Check step results for specific errors, fix inputs, and re-execute.

## API Reference

### PlannerAgent

```python
class PlannerAgent(BaseAgent):
    """Agent for 5-phase planning workflow."""

    async def process_task(
        self,
        task: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process planning task.

        Args:
            task: Must contain task_description or plan_id, phase, and user_input
        """
```

### ExecutorAgent

```python
class ExecutorAgent(BaseAgent):
    """Agent for executing finalized plans."""

    async def process_task(
        self,
        task: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        step_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process execution task.

        Args:
            task: Must contain plan_id
        """
```

### PlanningTool

```python
class PlanningTool(TrackingMixin, BaseTool):
    """Tool for 5-phase planning workflow."""

    async def execute(
        self,
        task_description: str = "",
        plan_id: str = "",
        phase: int = 1,
        user_input: str = "",
    ) -> ToolResult:
        """Execute planning workflow."""
```

### ExecutorTool

```python
class ExecutorTool(TrackingMixin, BaseTool):
    """Tool for executing finalized plans."""

    async def execute(self, plan_id: str) -> ToolResult:
        """Execute a finalized plan."""
```

## See Also

- [Enzyme Extraction Feature](./enzyme_extraction.md)
- [Agent Orchestrator](../architecture/delegation_pattern.md)
- [Markdown Agent System](../architecture/markdown_agents.md)
