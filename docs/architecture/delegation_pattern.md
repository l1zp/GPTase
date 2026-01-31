# Delegation Pattern for Specialized Agents

## Overview

The GPTase framework uses a **delegation pattern** for specialized agents to separate orchestration from business logic. This pattern promotes code reusability, testability, and maintainability.

### Core Principle

```
Agent (Lightweight Orchestrator)
    ↓ delegates to
Tool (Business Logic + LLM Calls)
    ↓ calls
ModelManager (LLM Operations)
```

## Architecture Components

### 1. Agent Layer (`src/agents/specialized/`)

**Purpose**: Lightweight orchestrators that coordinate workflows

**Responsibilities**:
- Task parameter extraction and validation
- Tool instantiation with tracking parameters
- Result translation to framework format
- Error handling at the orchestration level

**Characteristics**:
- Thin wrapper classes
- No direct LLM calls
- No business logic
- Minimal state management

**Example**:
```python
class EnzymeKineticsExtractorAgent(BaseAgent):
    async def process_task(self, task, session_id=None, agent_id=None, step_id=None):
        # Extract parameters
        text = task.get("text", "")
        source_file = task.get("source_file", "unknown")

        # Create tool with tracking
        extractor = EnzymeKineticsExtractorTool(
            model_manager=self.model_manager,
            agent_id=agent_id or self.agent_id,
            session_id=session_id,
            step_id=step_id,
        )

        # Delegate to tool
        result = await extractor.execute(text=text, source_file=source_file)

        # Return framework-formatted result
        return {"status": STATUS_SUCCESS, "data": result.data}
```

---

### 2. Tool Layer (`src/tools/`)

**Purpose**: Encapsulate business logic and LLM interactions

**Responsibilities**:
- LLM prompt construction
- Model calls via ModelManager
- Response parsing and validation
- Data processing and transformation
- Session tracking via TrackingMixin

**Characteristics**:
- Inherits from `BaseTool` and `TrackingMixin`
- Contains all business logic
- Manages LLM interactions
- Returns `ToolResult` objects

**Example**:
```python
class EnzymeKineticsExtractorTool(BaseTool, TrackingMixin):
    def __init__(self, model_manager=None, agent_id=None, session_id=None, step_id=None):
        BaseTool.__init__(self, name="enzyme_kinetics_extractor", ...)
        TrackingMixin.__init__(self, agent_id, session_id, step_id)
        self.model_manager = model_manager

    async def execute(self, text: str, source_file: str = "unknown") -> ToolResult:
        # Build messages
        messages = [
            {"role": "system", "content": ENZYME_KINETICS_EXTRACTION_PROMPT},
            {"role": "user", "content": self._build_user_prompt(text, source_file)}
        ]

        # Call LLM with tracking
        resp = await self.model_manager.generate(messages, **self.get_tracking_params())

        # Process and return result
        return ToolResult.success(data)
```

---

### 3. TrackingMixin (`src/tools/tracking_mixin.py`)

**Purpose**: Provide session tracking capabilities for tools

**Responsibilities**:
- Store tracking parameters (agent_id, session_id, step_id)
- Format tracking parameters for ModelManager calls

**Usage**:
```python
class MyTool(BaseTool, TrackingMixin):
    def __init__(self, agent_id=None, session_id=None, step_id=None):
        BaseTool.__init__(self, ...)
        TrackingMixin.__init__(self, agent_id, session_id, step_id)

    async def execute(self, ...):
        # TrackingMixin provides get_tracking_params()
        response = await self.model_manager.generate(
            messages,
            **self.get_tracking_params(),  # {"agent_id": ..., "session_id": ..., "step_id": ...}
        )
```

---

### 4. Prompts (`src/tools/prompts.py`)

**Purpose**: Centralized prompt management

**Benefits**:
- Single source of truth for prompts
- Easy to update and test prompts
- Consistent prompt formatting
- Reusable across multiple tools

**Example**:
```python
# Define prompt template
ENZYME_KINETICS_EXTRACTION_PROMPT = """You are an expert biochemical text parser...
CRITICAL RULES:
0) EXTRACTION PRINCIPLE: ONLY extract information that is EXPLICITLY STATED...
1) COMPREHENSIVE EXTRACTION: Extract EVERY enzyme variant from tables...
"""

# Use in tool
from src.tools.prompts import ENZYME_KINETICS_EXTRACTION_PROMPT

messages = [
    {"role": "system", "content": ENZYME_KINETICS_EXTRACTION_PROMPT},
    {"role": "user", "content": user_text}
]
```

---

## Benefits of Delegation Pattern

### 1. **Separation of Concerns**
- Agents handle orchestration
- Tools handle business logic
- Clear responsibilities

### 2. **Reusability**
- Tools can be used by multiple agents
- Tools can be used independently
- Prompts can be shared

### 3. **Testability**
- Tools can be unit tested in isolation
- Mock tools for agent testing
- Clear interfaces

### 4. **Maintainability**
- Business logic in one place (tools)
- Easy to update prompts
- Clear code structure

### 5. **Trackability**
- Automatic session tracking via TrackingMixin
- Consistent tracking parameters
- Web UI integration

---

## How to Create New Agent-Tool Pairs

### Step 1: Define Your Tool

Create `src/tools/my_tool.py`:

```python
from src.tools.base import BaseTool, ToolResult
from src.tools.tracking_mixin import TrackingMixin

class MyTool(BaseTool, TrackingMixin):
    def __init__(self, model_manager=None, agent_id=None, session_id=None, step_id=None):
        BaseTool.__init__(
            self,
            name="my_tool",
            description="Description of what this tool does",
            timeout=60,
        )
        TrackingMixin.__init__(self, agent_id, session_id, step_id)
        self.model_manager = model_manager

    async def execute(self, param1: str, param2: Optional[str] = None) -> ToolResult:
        try:
            # Your business logic here
            # Build prompts, call LLM, process results

            # Use tracking for LLM calls
            response = await self.model_manager.generate(
                messages,
                **self.get_tracking_params(),
            )

            # Return success
            return ToolResult.success(result_data)

        except Exception as e:
            # Return error
            return ToolResult.error(str(e))

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "..."},
                "param2": {"type": "string", "description": "..."}
            },
            "required": ["param1"]
        }
```

### Step 2: Define Your Prompt (if using LLM)

Add to `src/tools/prompts.py`:

```python
MY_TOOL_PROMPT = """You are an expert in...

Your task is to...

Return ONLY a JSON object with:
{
    "field1": "value1",
    "field2": "value2"
}
"""
```

### Step 3: Create Your Agent

Create `src/agents/specialized/my_agent.py`:

```python
from src.agents.base import BaseAgent
from src.core.constants import STATUS_SUCCESS, STATUS_ERROR
from src.tools.my_tool import MyTool

class MyAgent(BaseAgent):
    AGENT_NAME = "my_agent"

    def __init__(self, agent_id, memory_manager, tool_registry, model_manager):
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
            capabilities=["capability1", "capability2"],
        )
        self.model_manager = model_manager

    async def process_task(self, task, session_id=None, agent_id=None, step_id=None):
        try:
            # Extract parameters
            param1 = task.get("param1", "")
            param2 = task.get("param2")

            # Create tool with tracking
            tool = MyTool(
                model_manager=self.model_manager,
                agent_id=agent_id or self.agent_id,
                session_id=session_id,
                step_id=step_id,
            )

            # Delegate to tool
            result = await tool.execute(param1=param1, param2=param2)

            if result.status == "error":
                return {"status": STATUS_ERROR, "data": {"error": result.error}}

            return {"status": STATUS_SUCCESS, "data": result.data}

        except Exception as e:
            return {"status": STATUS_ERROR, "data": {"error": str(e)}}
```

### Step 4: Use Your Agent

```python
from src.agents.specialized.my_agent import MyAgent
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry
from src.utils import default_manager

manager = default_manager()
memory_manager = MemoryManager()
tool_registry = ToolRegistry()

agent = MyAgent(
    agent_id="my_agent",
    memory_manager=memory_manager,
    tool_registry=tool_registry,
    model_manager=manager,
)

result = await agent.process_task({
    "param1": "value1",
    "param2": "value2",
})
```

---

## Existing Implementations

### Reference Implementations

1. **DocumentStructureAnalyzer** (`src/tools/document_structure_analyzer.py`)
   - Document structure analysis
   - Table and paragraph identification
   - LLM-enhanced content classification

2. **EnzymeKineticsExtractorTool** (`src/tools/enzyme_kinetics_extractor.py`)
   - Enzyme kinetics data extraction
   - Structured JSON output
   - PDB ID extraction

3. **VisionImageAnalyzerTool** (`src/tools/vision_image_analyzer.py`)
   - Vision model integration
   - Scientific figure analysis
   - CSV data extraction

### Corresponding Agents

- `DocumentStructureAnalyzerAgent` → `DocumentStructureAnalyzer`
- `EnzymeKineticsExtractorAgent` → `EnzymeKineticsExtractorTool`
- `VisionImageAnalyzerAgent` → `VisionImageAnalyzerTool`

---

## Best Practices

### 1. Keep Agents Thin

Agents should only:
- Extract task parameters
- Create tools with tracking
- Translate results

Agents should NOT:
- Call LLMs directly
- Contain business logic
- Define prompts

### 2. Use TrackingMixin

Always inherit from `TrackingMixin` in tools that call LLMs:
```python
class MyTool(BaseTool, TrackingMixin):
    ...
```

### 3. Centralize Prompts

Define prompts in `src/tools/prompts.py`, not in tools or agents:
```python
# Good
from src.tools.prompts import MY_PROMPT

# Bad
MY_PROMPT = "..."  # Define in tool file
```

### 4. Return ToolResult

Tools should always return `ToolResult` objects:
```python
# Success
return ToolResult.success(data)

# Error
return ToolResult.error("Error message")
```

### 5. Handle Errors Gracefully

Both agents and tools should handle exceptions:
```python
try:
    result = await tool.execute(...)
    if result.status == "error":
        return {"status": STATUS_ERROR, "data": {"error": result.error}}
    return {"status": STATUS_SUCCESS, "data": result.data}
except Exception as e:
    return {"status": STATUS_ERROR, "data": {"error": str(e)}}
```

---

## Migration Guide

### Migrating from Embedded Logic to Delegation

**Before** (Agent with embedded logic):
```python
class MyAgent(BaseAgent):
    SYSTEM_PROMPT = "..."  # Prompt in agent

    async def process_task(self, task, ...):
        # Business logic in agent
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}, ...]
        resp = await self.model_manager.generate(messages, ...)
        # Processing logic here
```

**After** (Delegation pattern):
```python
# Tool: src/tools/my_tool.py
class MyTool(BaseTool, TrackingMixin):
    async def execute(self, ...):
        from src.tools.prompts import MY_PROMPT
        messages = [{"role": "system", "content": MY_PROMPT}, ...]
        resp = await self.model_manager.generate(messages, **self.get_tracking_params())
        return ToolResult.success(data)

# Agent: src/agents/specialized/my_agent.py
class MyAgent(BaseAgent):
    async def process_task(self, task, ...):
        tool = MyTool(model_manager=self.model_manager, ...)
        result = await tool.execute(...)
        return {"status": STATUS_SUCCESS, "data": result.data}
```

---

## Summary

The delegation pattern provides a clean, maintainable architecture for specialized agents:

- **Agents**: Orchestrate workflow
- **Tools**: Execute business logic
- **Prompts**: Centralized in `src/tools/prompts.py`
- **Tracking**: Automatic via `TrackingMixin`

This pattern is used throughout the GPTase framework for all specialized agents.
