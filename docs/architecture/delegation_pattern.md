# Delegation Pattern for Specialized Agents

## Overview

The GPTase framework uses a **delegation pattern** for specialized agents to separate orchestration from business logic. This pattern promotes code reusability, testability, and maintainability.

### Core Principle

```
MarkdownAgent (Configurable via config/agents/*.md)
    ↓ delegates to
Tool (Business Logic + Optional LLM Calls)
    ↓ calls
ModelManager (LLM Operations)
```

## Architecture Components

### 1. Agent Layer (`config/agents/*.md`)

**Purpose**: Metadata-driven agents that coordinate workflows.

**Responsibilities**:
- Defining agent identity and system prompts
- Binding specific tools to the agent
- Specifying model roles and parameters
- Guiding the LLM on task processing and output format

**Characteristics**:
- Pure configuration (Markdown format)
- No code required for most agents
- Processed by the generic `MarkdownAgent` class

**Example (`config/agents/my_agent.md`)**:
```markdown
<!--
@agent_id: my_agent
@tools: my_tool
@model_role: general
-->
# My Agent
## System Prompt
You are a specialized expert...
## Task Processing
1. Use my_tool to process data
...
```

---

### 2. Tool Layer (`src/tools/`)

**Purpose**: Encapsulate business logic and specialized data processing.

**Responsibilities**:
- Implementation of complex algorithms
- External database lookups
- File system operations
- Specific LLM prompts for internal tool logic
- Session tracking via TrackingMixin

**Characteristics**:
- Inherits from `BaseTool`
- Returns `ToolResult` objects
- Registered in the global `ToolRegistry`

**Example**:
```python
class MyTool(BaseTool):
    def __init__(self):
        super().__init__(name="my_tool", description="...")

    async def execute(self, **kwargs) -> ToolResult:
        # Implement logic
        return ToolResult.success(data)
```

---

### 3. TrackingMixin (`src/tools/tracking_mixin.py`)

**Purpose**: Provide session tracking capabilities for tools that make internal LLM calls.

**Responsibilities**:
- Store tracking parameters (agent_id, session_id, step_id)
- Format tracking parameters for ModelManager calls

---

## Benefits of the New Architecture

### 1. **Zero-Code Agents**
Most new agents can be created by simply writing a Markdown file. No Python coding is required unless a new low-level capability (Tool) is needed.

### 2. **Separation of Concerns**
- **Prompts**: Managed in Markdown (for agents) or within specific tool files (for tool-internal logic).
- **Orchestration**: Managed by `AgentOrchestrator` and the execution SOPs.
- **Logic**: Contained in pure Python Tools.

### 3. **High Reusability**
Tools like `pdb_lookup` or `calculator` are written once and used by any number of agents via simple configuration.

---

## How to Create New Agents

### Step 1: Write the Agent Definition
Create `config/agents/your_agent.md`. Define its tools, model role, and instructions.

### Step 2: (Optional) Define a New Tool
If your agent needs a capability not already in `src/tools/`, create a new Tool class in `src/tools/` and register it in `src/agents/orchestrator.py`.

### Step 3: Use the Agent
The `AgentOrchestrator` will automatically discover your agent if its ID is added to the `AGENT_IDS` list.

```python
result = await orchestrator.execute_task({
    "agent": "your_agent",
    "description": "Do something specialized"
})
```
