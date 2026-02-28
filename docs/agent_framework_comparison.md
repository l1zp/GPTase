# Agent Framework Comparison: Deer-Flow vs GPTase

This document provides a detailed comparison between the deer-flow and GPTase agent frameworks, focusing on agent definition patterns, architecture, and design philosophy.

## 1. Core Architecture Differences

| Dimension | Deer-Flow | GPTase |
|-----------|-----------|--------|
| **Framework Foundation** | LangChain/LangGraph + Middleware Chain | Custom BaseAgent + MarkdownAgent |
| **Agent Definition Format** | Python factory functions + Dataclass + YAML | Markdown files + HTML comment metadata |
| **Configuration Driven** | YAML (config.yaml) | JSON (llm_config.json) + Markdown |

## 2. Agent Definition Patterns

### Deer-Flow - Code-Driven Approach

The main agent is created via a factory function:

```python
# backend/src/agents/lead_agent/agent.py
def make_lead_agent(config: RunnableConfig):
    return create_agent(
        model=create_chat_model(name=model_name, thinking_enabled=thinking_enabled),
        tools=get_available_tools(model_name=model_name, subagent_enabled=subagent_enabled),
        middleware=_build_middlewares(config),
        system_prompt=apply_prompt_template(subagent_enabled=subagent_enabled),
        state_schema=ThreadState,
    )
```

Subagents are defined using Python dataclasses:

```python
# backend/src/subagents/config.py
@dataclass
class SubagentConfig:
    name: str
    description: str
    system_prompt: str
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = field(default_factory=lambda: ["task"])
    model: str = "inherit"
    max_turns: int = 50
    timeout_seconds: int = 900
```

Built-in subagents:
- `general-purpose`: For complex multi-step tasks
- `bash`: For command execution

### GPTase - Markdown-Driven Approach

Agents are defined in Markdown files with HTML comment metadata:

```markdown
<!-- config/agents/enzyme_kinetics_extractor.md -->
<!--
@agent_id: enzyme_kinetics_extractor
@capabilities: extract_enzyme_kinetics, parse_reaction_data
@requires_model: true
@model_role: extraction
@temperature: 0.0
@max_tokens: 8192
-->

## Agent Description
This agent is a specialized biochemical data extraction expert...

## System Prompt
You are the world-class Enzyme Kinetics Extraction Expert...

## Task Processing
1. **Analyze**: Identify all tables and text blocks...
2. **Extract**: Generate a structured JSON response...

## Output Format
Return a strict JSON object:
```json
{
  "reactions": [...]
}
```

## Examples
[TASK]
Extract from: "Variant V1 (L12A) showed Km of 0.5 mM..."

[RESPONSE]
{...}
```

### Metadata Markers (GPTase)

| Marker | Purpose |
|--------|---------|
| `@agent_id` | Unique identifier (must match filename) |
| `@capabilities` | Comma-separated list of skills |
| `@requires_model` | `true` or `false` |
| `@model_role` | `general`, `extraction`, `analysis`, `planning` |
| `@temperature` | Float (0.0 - 1.0) |
| `@max_tokens` | Integer limit for responses |

## 3. State Management & Memory

### Deer-Flow

**State Schema (ThreadState):**
```python
class ThreadState(AgentState):
    sandbox: NotRequired[SandboxState | None]
    thread_data: NotRequired[ThreadDataState | None]
    title: NotRequired[str | None]
    artifacts: Annotated[list[str], merge_artifacts]
    todos: NotRequired[list | None]
    uploaded_files: NotRequired[list[dict] | None]
    viewed_images: Annotated[dict[str, ViewedImageData], merge_viewed_images]
```

**Memory System:**
- LLM-driven memory updates via `MemoryUpdater`
- Queue-based with debounce mechanism (default 30s)
- Structured memory format:
  ```json
  {
    "user": {"workContext": {...}, "personalContext": {...}},
    "history": {"recentMonths": {...}, "earlierContext": {...}},
    "facts": [{"id": "", "content": "", "category": "", "confidence": 0.0}]
  }
  ```

### GPTase

- Basic `MemoryManager` with persistent storage
- No built-in memory update automation
- Focus on task-specific context rather than conversational memory

## 4. Middleware vs Direct Hooks

### Deer-Flow - Middleware Chain

11 middlewares in execution order:

1. `ThreadDataMiddleware` - Thread-specific directories
2. `UploadsMiddleware` - File upload handling
3. `SandboxMiddleware` - Sandbox environment management
4. `DanglingToolCallMiddleware` - Patch missing ToolMessages
5. `SummarizationMiddleware` - Token-based summarization
6. `TodoListMiddleware` - Plan mode todo management
7. `TitleMiddleware` - Auto title generation
8. `MemoryMiddleware` - Queue memory updates
9. `ViewImageMiddleware` - Vision model support
10. `SubagentLimitMiddleware` - Truncate parallel calls
11. `ClarificationMiddleware` - Intercept clarification requests

```python
class MyMiddleware(AgentMiddleware):
    async def before_agent(self, state, config):
        # Pre-processing
        pass

    async def after_agent(self, state, config):
        # Post-processing
        pass

    async def awrap_tool_call(self, state, tool_call, config):
        # Intercept tool calls
        pass
```

### GPTase - Direct Tool Integration

No explicit middleware system. Tools inherit from `BaseTool`:

```python
class MyTool(BaseTool):
    def __init__(self):
        super().__init__(name="my_tool", timeout=30)

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.success(data={"result": "value"})
```

## 5. Tool Integration Patterns

### Deer-Flow

**YAML-based tool configuration:**
```yaml
# config.yaml
tools:
  - name: web_search
    group: web
    use: src.community.tavily.tools:web_search_tool
    max_results: 5
```

**Dynamic tool loading:**
```python
def get_available_tools(
    groups: list[str] | None = None,
    include_mcp: bool = True,
    model_name: str | None = None,
    subagent_enabled: bool = False,
) -> list[BaseTool]:
    # Load from config + MCP servers
```

**Tool categories:**
- `BUILTIN_TOOLS`: `present_file_tool`, `ask_clarification_tool`
- `SUBAGENT_TOOLS`: `task_tool`
- `Vision tools`: `view_image_tool` (conditional)
- `MCP tools`: Dynamically loaded from MCP servers

### GPTase

**Registry-based tool management:**
```python
# src/tools/registry.py
class ToolRegistry:
    def register(self, tool: BaseTool) -> None: ...
    async def execute(self, tool_name: str, **kwargs) -> ToolResult: ...
```

**Tool categories:**
- General Tools (`src/tools/`): document.py, system.py, utils.py
- MCP Domain Tools (`src/mcp/tools/`): enzyme_kinetics_tool.py, vision_tool.py
- MCP Databases (`src/mcp/databases/`): PDB, Rhea, KEGG, Expasy, PubChem

## 6. Subagent/Delegation Pattern

### Deer-Flow

**Task tool for delegation:**
```python
@tool("task", parse_docstring=True)
async def task(
    description: str,
    subagent_type: Literal["general-purpose", "bash"],
    run_in_background: bool = False,
) -> str:
    """Launch a new agent to handle complex tasks autonomously."""
```

Features:
- Parallel task execution
- Background task polling
- Progress streaming via `get_stream_writer()`

### GPTase

**SOP/Plan workflow:**
```json
{
  "plan_id": "enzyme_extraction_pipeline",
  "workflow": [
    {"step_id": 1, "agent": "enzyme_kinetics_extractor", "inputs": {...}},
    {"step_id": 2, "agent": "enzyme_design_extractor", "inputs": {"text": "{{step1.output}}"}}
  ]
}
```

**Executor agent** (`executor.md`) handles SOP execution with variable interpolation.

## 7. Skills vs Agent Capabilities

### Deer-Flow - Skills System

Skills defined as Markdown files with YAML front matter:

```markdown
<!-- skills/public/chart-visualization/SKILL.md -->
---
name: chart-visualization
description: This skill should be used when the user wants to visualize data...
dependency:
  nodejs: ">=18.0.0"
---

# Chart Visualization Skill
Instructions for chart creation...
```

**Loading mechanism:**
- Scans `public/` and `custom/` directories
- Parses YAML front matter
- Injects into system prompt dynamically

### GPTase - Capabilities in Agent Definition

Capabilities are defined directly in agent metadata:

```markdown
<!--
@capabilities: extract_enzyme_kinetics, parse_reaction_data, extract_mutations
-->
```

No separate skills layer - agents are the primary capability units.

## 8. Configuration Comparison

### Deer-Flow (YAML)

```yaml
# config.yaml
models:
  default: openai-gpt-4
  openai-gpt-4:
    type: openai
    model: gpt-4-turbo

tools:
  - name: web_search
    use: src.community.tavily.tools:web_search_tool

sandbox:
  provider: local  # or docker, aio

subagents:
  timeout_seconds: 900

memory:
  storage: file
  path: ~/.deer-flow/memory

skills:
  paths:
    - skills/public
    - skills/custom
```

### GPTase (JSON + Markdown)

```json
// config/llm_config.json
{
  "models": {
    "general": {"model": "gpt-4", "provider": "openai"},
    "extraction": {"model": "gpt-4", "temperature": 0.0}
  }
}
```

```markdown
<!-- config/agents/agent_name.md -->
Agent definition with embedded configuration
```

## 9. Architecture Philosophy

| Aspect | Deer-Flow | GPTase |
|--------|-----------|--------|
| **Design Philosophy** | Code-first, strongly typed, middleware composition | Config-first, Markdown-as-docs, declarative |
| **Complexity** | Higher (LangGraph learning curve) | Lower (pure Python + Markdown) |
| **Flexibility** | High (middleware chain composable) | Medium (fixed agent structure) |
| **Readability** | Requires Python + LangChain knowledge | Markdown directly readable |
| **Dependencies** | Heavy LangChain ecosystem | Lightweight, optional dependencies |
| **Extensibility** | Via middleware and subagent dataclasses | Via new Markdown agent files |

## 10. Use Case Recommendations

### Deer-Flow Is Better For:

- General-purpose AI applications requiring complex state management
- Applications needing middleware chains for cross-cutting concerns
- Teams already invested in LangChain/LangGraph ecosystem
- Projects requiring dynamic skill injection and memory management
- Multi-tenant applications with thread-level isolation

### GPTase Is Better For:

- Domain-specific data extraction and analysis tasks
- Scientific computing and biochemical analysis workflows
- Teams preferring low-code, configuration-driven approaches
- Projects requiring quick agent definition iteration
- Specialized pipelines with predefined SOPs
- Environments with minimal dependency requirements

## 11. Migration Considerations

### From GPTase to Deer-Flow

1. Convert Markdown agent definitions to Python dataclasses
2. Wrap tools as LangChain `BaseTool` implementations
3. Convert SOPs to subagent delegation patterns
4. Implement memory via `MemoryMiddleware`

### From Deer-Flow to GPTase

1. Extract subagent configs to Markdown files
2. Simplify middleware logic into tool implementations
3. Convert skills to agent capabilities or separate Markdown configs
4. Replace LangGraph state with simpler memory manager

## 12. Agent Creation Flow Comparison

### 12.1 Overall Architecture

```
Deer-Flow Creation Flow                      GPTase Creation Flow
=======================                      =====================
┌─────────────────┐                          ┌─────────────────┐
│ Python Code     │                          │ Markdown File   │
│ (SubagentConfig)│                          │ (.md)           │
└────────┬────────┘                          └────────┬────────┘
         │                                            │
         ▼                                            ▼
┌─────────────────┐                          ┌─────────────────┐
│ Registry        │                          │ MarkdownParser  │
│ (dict lookup)   │                          │ (regex + sections)
└────────┬────────┘                          └────────┬────────┘
         │                                            │
         ▼                                            ▼
┌─────────────────┐                          ┌─────────────────┐
│ SubagentExecutor│                          │ AgentDefinition │
│ ._create_agent()│                          │ (dataclass)     │
└────────┬────────┘                          └────────┬────────┘
         │                                            │
         ▼                                            ▼
┌─────────────────┐                          ┌─────────────────┐
│ create_agent()  │                          │ MarkdownAgent   │
│ (LangGraph)     │                          │ (BaseAgent)     │
└─────────────────┘                          └─────────────────┘
```

### 12.2 Definition Format Comparison

**Deer-Flow - Python Dataclass:**

```python
# backend/src/subagents/builtins/general_purpose.py
GENERAL_PURPOSE_CONFIG = SubagentConfig(
    name="general-purpose",
    description="A capable agent for complex tasks...",
    system_prompt="""You are a general-purpose subagent...""",
    tools=None,                    # None = inherit all tools from parent
    disallowed_tools=["task"],     # Blacklist of forbidden tools
    model="inherit",               # Inherit parent agent's model
    max_turns=50,                  # Maximum turns
    timeout_seconds=900,           # Timeout in seconds
)
```

**GPTase - Markdown File:**

```markdown
<!-- config/agents/enzyme_kinetics_extractor.md -->
<!--
@agent_id: enzyme_kinetics_extractor
@capabilities: extract_enzyme_kinetics, parse_reaction_data
@requires_model: true
@model_role: extraction
@temperature: 0.0
@max_tokens: 8192
-->

## Agent Description
This agent is a specialized biochemical data extraction expert...

## System Prompt
You are the world-class Enzyme Kinetics Extraction Expert...

## Task Processing
1. **Analyze**: Identify all tables...
2. **Extract**: Generate structured JSON...

## Output Format
Return a strict JSON object...

## Examples
[TASK] Extract from: ...
[RESPONSE] {...}
```

### 12.3 Factory/Creator Comparison

**Deer-Flow - SubagentExecutor:**

```python
# backend/src/subagents/executor.py
class SubagentExecutor:
    def __init__(
        self,
        config: SubagentConfig,
        tools: list[BaseTool],
        parent_model: str | None = None,
        sandbox_state: SandboxState | None = None,  # Inherit parent's sandbox
        thread_data: ThreadDataState | None = None, # Inherit parent's thread data
        trace_id: str | None = None,
    ):
        self.config = config
        self.tools = _filter_tools(tools, config.tools, config.disallowed_tools)

    def _create_agent(self):
        """Dynamically create LangGraph Agent"""
        return create_agent(
            model=create_chat_model(name=model_name, thinking_enabled=False),
            tools=self.tools,
            middleware=[ThreadDataMiddleware(), SandboxMiddleware()],
            system_prompt=self.config.system_prompt,
            state_schema=ThreadState,
        )

    def execute(self, task: str) -> SubagentResult:
        """Synchronous execution"""
        agent = self._create_agent()
        state = self._build_initial_state(task)
        for chunk in agent.stream(state, config=run_config):
            # Stream processing
        return result

    def execute_async(self, task: str) -> str:
        """Async execution, returns task_id"""
        # Use thread pool for scheduling
        _scheduler_pool.submit(run_task)
        return task_id
```

**GPTase - MarkdownAgentFactory:**

```python
# src/agents/markdown_agent.py
class MarkdownAgentFactory:
    def __init__(self, config_dir: Optional[Path] = None):
        self.parser = MarkdownParser(config_dir)
        self._definitions_cache: Dict[str, AgentDefinition] = {}

    def load_definition(self, agent_id: str) -> AgentDefinition:
        """Load definition from Markdown file"""
        md_file = self.parser.config_dir / f"{agent_id}.md"
        definition, tool_defs = self.parser.parse_file(md_file)
        return definition

    def create_agent(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager: Optional[Model] = None,
    ) -> 'MarkdownAgent':
        """Create agent instance"""
        definition = self.load_definition(agent_id)

        # Register inline tool definitions
        tool_defs = self._tool_defs_cache.get(agent_id, {})
        if tool_defs:
            self._register_inline_tools(tool_defs, tool_registry)

        return MarkdownAgent(
            definition=definition,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
        )
```

### 12.4 Agent Instance Comparison

**Deer-Flow (LangGraph-based):**

```python
# Dynamically created, rebuilt on each execution
agent = create_agent(
    model=create_chat_model(...),
    tools=filtered_tools,
    middleware=[...],             # Middleware chain
    system_prompt=config.system_prompt,
    state_schema=ThreadState,     # State schema
)
```

**GPTase (BaseAgent-based):**

```python
class MarkdownAgent(BaseAgent):
    def __init__(
        self,
        definition: AgentDefinition,
        memory_manager,
        tool_registry,
        model_manager: Optional[Model] = None,
    ):
        super().__init__(
            agent_id=definition.agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=definition.capabilities,
        )
        self.definition = definition
        self.model_manager = model_manager

    async def process_task(self, task: Dict) -> Dict:
        if self.definition.requires_model:
            return await self._process_llm_task(task)
        return await self._process_simple_task(task)
```

### 12.5 Key Differences Summary

| Dimension | Deer-Flow | GPTase |
|-----------|-----------|--------|
| **Definition Format** | Python Dataclass (code) | Markdown File (config) |
| **Creation Timing** | Dynamically created per execution | Factory creates instance once |
| **Framework Dependency** | LangGraph `create_agent()` | Custom `BaseAgent` |
| **State Passing** | Explicit `sandbox_state`, `thread_data` | Managed via `memory_manager` |
| **Tool Inheritance** | `tools=None` inherits all + `disallowed_tools` blacklist | `@tools` explicit list |
| **Model Inheritance** | `model="inherit"` inherits parent | `@model_role` specifies role, resolved by `model_manager` |
| **Execution Mode** | Sync/Async, background task pool | Single async execution |
| **Middleware** | Each subagent has independent middleware chain | No middleware system |
| **Readability** | Need to read Python code | Markdown directly readable |
| **Extension Method** | New Python file + register to `BUILTIN_SUBAGENTS` | New `.md` file in `config/agents/` |

### 12.6 Execution Flow Comparison

**Deer-Flow:**
```
User Request -> Lead Agent -> task_tool -> SubagentExecutor
             -> create_agent() -> LangGraph Runtime -> Stream return
```

**GPTase:**
```
User Request -> SOP/Executor Agent -> MarkdownAgentFactory.create_agent()
             -> MarkdownAgent.process_task() -> LLM call -> Return result
```

### 12.7 Steps to Extend New Agent

**Deer-Flow:**
```python
# 1. Create configuration file
# backend/src/subagents/builtins/my_agent.py
MY_AGENT_CONFIG = SubagentConfig(
    name="my-agent",
    description="...",
    system_prompt="...",
)

# 2. Register to registry
# backend/src/subagents/builtins/__init__.py
BUILTIN_SUBAGENTS = {
    "my-agent": MY_AGENT_CONFIG,
}
```

**GPTase:**
```markdown
# 1. Create Markdown file
# config/agents/my_agent.md
<!--
@agent_id: my_agent
@capabilities: ...
-->
## System Prompt
...
```

```python
# 2. Create via Factory
agent = factory.create_agent("my_agent", memory_manager, tool_registry)
```

## 13. Agent Interaction Control Mechanisms (Deer-Flow)

### 13.1 Overall Interaction Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Lead Agent                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    System Prompt                        │   │
│  │  - Clarification System (priority: clarify first)       │   │
│  │  - Subagent System (concurrency limit guidance)         │   │
│  │  - Skills System (skill injection)                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  Middleware Chain                       │   │
│  │  SubagentLimitMiddleware → ... → ClarificationMiddleware│   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│              ┌───────────────┼───────────────┐                 │
│              ▼               ▼               ▼                 │
│         task_tool      ask_clarification   other_tools        │
│              │               │               │                 │
└──────────────┼───────────────┼───────────────┼─────────────────┘
               │               │               │
               ▼               │               │
┌──────────────────────┐       │               │
│  SubagentExecutor    │       │               │
│  ┌────────────────┐  │       │               │
│  │ Subagent #1    │  │       │               │
│  │ (isolated ctx) │  │       │               │
│  └────────────────┘  │       │               │
│  ┌────────────────┐  │       │               │
│  │ Subagent #2    │  │  Command(goto=END)    │
│  │ (isolated ctx) │  │       │               │
│  └────────────────┘  │       │               │
│         ...          │       │               │
└──────────────────────┘       │               │
                               ▼               ▼
                        ┌──────────────────────────┐
                        │   Wait for user/continue │
                        └──────────────────────────┘
```

### 13.2 Lead Agent → Subagent Interaction

**Core Mechanism: task_tool**

```python
# backend/src/tools/builtins/task_tool.py
@tool("task", parse_docstring=True)
def task_tool(
    runtime: ToolRuntime[ContextT, ThreadState],
    description: str,
    prompt: str,
    subagent_type: Literal["general-purpose", "bash"],
    max_turns: int | None = None,
) -> str:
    # 1. Extract parent context from runtime
    sandbox_state = runtime.state.get("sandbox")
    thread_data = runtime.state.get("thread_data")
    thread_id = runtime.context.get("thread_id")
    parent_model = metadata.get("model_name")
    trace_id = metadata.get("trace_id") or str(uuid.uuid4())[:8]

    # 2. Get tools (prevent nested subagents)
    tools = get_available_tools(subagent_enabled=False)

    # 3. Create SubagentExecutor with context passing
    executor = SubagentExecutor(
        config=config,
        tools=tools,
        parent_model=parent_model,
        sandbox_state=sandbox_state,    # Shared sandbox
        thread_data=thread_data,        # Shared thread data
        thread_id=thread_id,
        trace_id=trace_id,              # Distributed tracing
    )

    # 4. Async execution + backend polling
    task_id = executor.execute_async(prompt)

    # 5. Poll results and stream back
    while True:
        result = get_background_task_result(task_id)
        if result.status == COMPLETED:
            return f"Task Succeeded. Result: {result.result}"
```

**Key Points:**
- **Context Passing**: `sandbox_state`, `thread_data` passed from Lead Agent to Subagent
- **Tool Isolation**: `subagent_enabled=False` prevents Subagent from creating more Subagents
- **Async Execution**: Uses thread pool + backend polling, doesn't block Lead Agent
- **Streaming**: Real-time progress via `get_stream_writer()`

### 13.3 Concurrency Control Mechanism

**Dual-Layer Control: Prompt Guidance + Middleware Enforcement**

**Layer 1: System Prompt Guidance**

```python
# backend/src/agents/lead_agent/prompt.py
def _build_subagent_section(max_concurrent: int) -> str:
    return f"""<subagent_system>
**HARD CONCURRENCY LIMIT: MAXIMUM {max_concurrent} `task` CALLS PER RESPONSE.**

- Each response, you may include **at most {max_concurrent}** `task` tool calls.
- **Before launching subagents, you MUST count your sub-tasks in your thinking:**
  - If count <= {max_concurrent}: Launch all in this response.
  - If count > {max_concurrent}: Pick the {max_concurrent} most important sub-tasks.
- **Multi-batch execution** (for >{max_concurrent} sub-tasks):
  - Turn 1: Launch sub-tasks 1-{max_concurrent} in parallel -> wait for results
  - Turn 2: Launch next batch in parallel -> wait for results
  - Final turn: Synthesize ALL results
</subagent_system>"""
```

**Layer 2: Middleware Enforcement**

```python
# backend/src/agents/middlewares/subagent_limit_middleware.py
class SubagentLimitMiddleware(AgentMiddleware):
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent  # clamped to [2, 4]

    def _truncate_task_calls(self, state: AgentState) -> dict | None:
        messages = state.get("messages", [])
        last_msg = messages[-1]
        tool_calls = getattr(last_msg, "tool_calls", None)

        # Find all task tool calls
        task_indices = [i for i, tc in enumerate(tool_calls) if tc.get("name") == "task"]

        if len(task_indices) <= self.max_concurrent:
            return None  # No truncation needed

        # Drop excess task calls
        indices_to_drop = set(task_indices[self.max_concurrent:])
        truncated_tool_calls = [tc for i, tc in enumerate(tool_calls)
                                if i not in indices_to_drop]

        logger.warning(f"Truncated {len(indices_to_drop)} excess task tool call(s)")
        return {"messages": [last_msg.model_copy(update={"tool_calls": truncated_tool_calls})]}

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._truncate_task_calls(state)
```

### 13.4 State Sharing Mechanism

**ThreadState - Cross-Agent Shared State**

```python
# backend/src/agents/thread_state.py
class ThreadState(AgentState):
    sandbox: NotRequired[SandboxState | None]        # Sandbox state
    thread_data: NotRequired[ThreadDataState | None] # Thread data
    title: NotRequired[str | None]                   # Conversation title
    artifacts: Annotated[list[str], merge_artifacts] # Artifacts (with reducer)
    todos: NotRequired[list | None]                  # Todo list
    uploaded_files: NotRequired[list[dict] | None]   # Uploaded files
    viewed_images: Annotated[dict, merge_viewed_images]  # Viewed images

# Reducer functions - define state merge logic
def merge_artifacts(existing: list[str] | None, new: list[str] | None) -> list[str]:
    """Merge and deduplicate artifacts"""
    return list(dict.fromkeys((existing or []) + (new or [])))
```

**State Passing Flow:**

```
Lead Agent                    SubagentExecutor               Subagent
    │                              │                             │
    │  ThreadState                 │                             │
    │  {sandbox, thread_data,      │                             │
    │   artifacts, todos, ...}     │                             │
    │                              │                             │
    │──── runtime.state ──────────►│                             │
    │                              │                             │
    │                              │  _build_initial_state()     │
    │                              │  {messages: [task],         │
    │                              │   sandbox: sandbox_state,   │
    │                              │   thread_data: thread_data} │
    │                              │                             │
    │                              │──────── agent.stream() ────►│
    │                              │                             │
    │                              │◄────── SubagentResult ──────│
    │                              │                             │
    │◄────── Task Succeeded ───────│                             │
```

### 13.5 User Interaction Interruption

**ClarificationMiddleware - Intercept and Interrupt**

```python
# backend/src/agents/middlewares/clarification_middleware.py
class ClarificationMiddleware(AgentMiddleware):
    def wrap_tool_call(self, request, handler) -> ToolMessage | Command:
        # Check if this is an ask_clarification call
        if request.tool_call.get("name") != "ask_clarification":
            return handler(request)  # Execute other tools normally

        # Intercept clarification request
        return self._handle_clarification(request)

    def _handle_clarification(self, request) -> Command:
        args = request.tool_call.get("args", {})

        # Format user-friendly message
        formatted_message = self._format_clarification_message(args)

        # Create ToolMessage
        tool_message = ToolMessage(
            content=formatted_message,
            tool_call_id=tool_call_id,
            name="ask_clarification",
        )

        # Return Command to interrupt execution
        return Command(
            update={"messages": [tool_message]},
            goto=END,  # Jump to end node, wait for user response
        )
```

**Execution Flow:**

```
User Request -> Lead Agent thinks -> Finds missing info
             -> Calls ask_clarification()
             -> ClarificationMiddleware intercepts
             -> Command(goto=END) interrupts execution
             -> Returns formatted question to user
             -> [Wait for user response]
             -> Continue after user replies
```

### 13.6 Streaming Progress

**Stream Progress Push:**

```python
# backend/src/tools/builtins/task_tool.py
writer = get_stream_writer()

# Send task started event
writer({"type": "task_started", "task_id": task_id, "description": description})

while True:
    result = get_background_task_result(task_id)

    # Send progress updates
    if current_message_count > last_message_count:
        for i in range(last_message_count, current_message_count):
            writer({
                "type": "task_running",
                "task_id": task_id,
                "message": result.ai_messages[i],
            })

    # Send completion event
    if result.status == COMPLETED:
        writer({"type": "task_completed", "task_id": task_id, "result": result.result})
        return f"Task Succeeded. Result: {result.result}"
```

### 13.7 Interaction Control Summary

| Interaction Type | Control Mechanism | Implementation Location |
|-----------------|-------------------|------------------------|
| **Lead → Subagent Delegation** | `task_tool` + `SubagentExecutor` | `task_tool.py` |
| **Context Sharing** | `ThreadState` + runtime.state | `thread_state.py` |
| **Concurrency Limit** | Prompt guidance + Middleware truncation | `prompt.py` + `subagent_limit_middleware.py` |
| **Nesting Prevention** | `subagent_enabled=False` + `disallowed_tools` | `task_tool.py` + `SubagentConfig` |
| **User Interruption** | `ClarificationMiddleware` + `Command(goto=END)` | `clarification_middleware.py` |
| **Progress Streaming** | `get_stream_writer()` + event types | `task_tool.py` |
| **Distributed Tracing** | `trace_id` across Lead → Subagent | `executor.py` |
| **State Merging** | `Annotated` + Reducer functions | `thread_state.py` |

### 13.8 Comparison with GPTase

| Dimension | Deer-Flow | GPTase |
|-----------|-----------|--------|
| **Agent-to-Agent Communication** | `task_tool` + state passing | SOP JSON workflow |
| **Concurrency Control** | Middleware enforcement | No explicit control |
| **Context Sharing** | `ThreadState` + runtime | `memory_manager` |
| **User Interruption** | `ClarificationMiddleware` + `Command` | No built-in mechanism |
| **Progress Feedback** | Streaming event push | No built-in mechanism |
| **Execution Model** | Async thread pool + polling | Synchronous sequential execution |

## 14. Implementation Guide: Adding Deer-Flow Features to GPTase

This section provides concrete implementation strategies for adding deer-flow-style interaction control features to GPTase.

### 14.1 Feature Mapping: What to Implement

| Deer-Flow Feature | GPTase Current State | Implementation Priority |
|-------------------|---------------------|------------------------|
| `task_tool` delegation | SOP workflow via `ExecutorTool` | **High** - Add `TaskTool` |
| Middleware chain | None | **Medium** - Add hooks system |
| `ThreadState` sharing | `context` dict in ExecutorTool | **Medium** - Add `SharedState` |
| Concurrency control | None | **High** - Add limit enforcement |
| User interruption | None | **Medium** - Add `ClarificationTool` |
| Progress streaming | None | **Low** - Requires frontend changes |

### 14.2 Implementation 1: TaskTool for Agent Delegation

**Goal:** Allow agents to delegate tasks to other agents dynamically (like deer-flow's `task_tool`).

**Create new file:** `src/tools/task_tool.py`

```python
"""Task tool for delegating work to other agents."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Thread pools for execution
_scheduler_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="task-scheduler-")
_execution_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="task-exec-")


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Global storage for background tasks
_background_tasks: Dict[str, TaskResult] = {}


@dataclass
class AgentDelegationConfig:
    """Configuration for agent delegation."""
    name: str
    description: str
    agent_id: str
    tools: List[str] | None = None  # None = inherit all
    disallowed_tools: List[str] = field(default_factory=lambda: ["task"])  # Prevent nesting
    max_turns: int = 50
    timeout_seconds: int = 300


# Built-in delegation configs
BUILTIN_DELEGATIONS = {
    "general-purpose": AgentDelegationConfig(
        name="general-purpose",
        description="For complex multi-step tasks",
        agent_id="general_agent",
    ),
    "extraction": AgentDelegationConfig(
        name="extraction",
        description="For data extraction tasks",
        agent_id="enzyme_kinetics_extractor",
    ),
}


class TaskTool(BaseTool):
    """Tool for delegating tasks to other agents."""

    def __init__(
        self,
        agent_factory,  # MarkdownAgentFactory
        memory_manager,
        tool_registry,
        model_manager=None,
        max_concurrent: int = 3,
    ):
        super().__init__(
            name="task",
            description="Delegate a task to a specialized agent",
            timeout=600,
        )
        self.agent_factory = agent_factory
        self.memory_manager = memory_manager
        self.tool_registry = tool_registry
        self.model_manager = model_manager
        self.max_concurrent = max_concurrent

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Short (3-5 word) description of the task"
                },
                "prompt": {
                    "type": "string",
                    "description": "Detailed task description for the agent"
                },
                "delegation_type": {
                    "type": "string",
                    "enum": list(BUILTIN_DELEGATIONS.keys()),
                    "description": "Type of agent to delegate to"
                },
            },
            "required": ["description", "prompt", "delegation_type"]
        }

    async def execute(self, **kwargs) -> ToolResult:
        import uuid

        description = kwargs.get("description", "")
        prompt = kwargs.get("prompt", "")
        delegation_type = kwargs.get("delegation_type", "general-purpose")

        config = BUILTIN_DELEGATIONS.get(delegation_type)
        if not config:
            return ToolResult.error(f"Unknown delegation type: {delegation_type}")

        task_id = str(uuid.uuid4())[:8]

        # Create agent for delegation
        try:
            agent = self.agent_factory.create_agent(
                config.agent_id,
                self.memory_manager,
                self.tool_registry,
                self.model_manager,
            )
        except Exception as e:
            return ToolResult.error(f"Failed to create agent: {e}")

        # Execute task
        task = {"id": task_id, "description": description, "text": prompt}

        try:
            result = await asyncio.wait_for(
                agent.process_task(task),
                timeout=config.timeout_seconds
            )

            if result.get("status") == "success":
                return ToolResult.success(data={
                    "task_id": task_id,
                    "result": result.get("data"),
                })
            else:
                return ToolResult.error(result.get("error", "Task failed"))

        except asyncio.TimeoutError:
            return ToolResult.error(f"Task timed out after {config.timeout_seconds}s")
        except Exception as e:
            return ToolResult.error(f"Task execution failed: {e}")


# Usage in orchestrator
# from src.tools.task_tool import TaskTool
# task_tool = TaskTool(factory, memory_manager, tool_registry, model_manager)
# tool_registry.register_tool(task_tool, category="delegation")
```

### 14.3 Implementation 2: Middleware/Hooks System

**Goal:** Add hooks for pre/post processing around tool execution and agent calls.

**Create new file:** `src/middleware/__init__.py`

```python
"""Middleware system for GPTase agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class MiddlewareContext:
    """Context passed through middleware chain."""
    agent_id: str
    task: Dict[str, Any]
    state: Dict[str, Any]
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class Middleware(ABC):
    """Base middleware class."""

    @abstractmethod
    async def before_agent(self, context: MiddlewareContext) -> MiddlewareContext:
        """Called before agent processes task. Can modify context."""
        return context

    @abstractmethod
    async def after_agent(self, context: MiddlewareContext, result: Dict) -> Dict:
        """Called after agent processes task. Can modify result."""
        return result

    @abstractmethod
    async def wrap_tool_call(
        self,
        context: MiddlewareContext,
        tool_name: str,
        parameters: Dict[str, Any],
        handler: Callable
    ) -> Dict[str, Any]:
        """Wrap tool execution. Can intercept or modify calls."""
        return await handler(parameters)


class ConcurrencyLimitMiddleware(Middleware):
    """Enforce maximum concurrent task calls."""

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._pending_tasks: List[str] = []

    async def before_agent(self, context: MiddlewareContext) -> MiddlewareContext:
        return context

    async def after_agent(self, context: MiddlewareContext, result: Dict) -> Dict:
        return result

    async def wrap_tool_call(
        self,
        context: MiddlewareContext,
        tool_name: str,
        parameters: Dict[str, Any],
        handler: Callable
    ) -> Dict[str, Any]:
        # Only limit 'task' tool calls
        if tool_name != "task":
            return await handler(parameters)

        # Count pending tasks
        if len(self._pending_tasks) >= self.max_concurrent:
            logger.warning(
                f"Concurrency limit reached ({self.max_concurrent}), "
                f"rejecting task call"
            )
            return {
                "status": "error",
                "error": f"Maximum concurrent tasks ({self.max_concurrent}) reached"
            }

        task_id = parameters.get("description", "unknown")
        self._pending_tasks.append(task_id)

        try:
            result = await handler(parameters)
            return result
        finally:
            if task_id in self._pending_tasks:
                self._pending_tasks.remove(task_id)


class ClarificationMiddleware(Middleware):
    """Handle user clarification requests."""

    def __init__(self, clarification_callback: Optional[Callable] = None):
        self.clarification_callback = clarification_callback

    async def before_agent(self, context: MiddlewareContext) -> MiddlewareContext:
        return context

    async def after_agent(self, context: MiddlewareContext, result: Dict) -> Dict:
        return result

    async def wrap_tool_call(
        self,
        context: MiddlewareContext,
        tool_name: str,
        parameters: Dict[str, Any],
        handler: Callable
    ) -> Dict[str, Any]:
        if tool_name != "ask_clarification":
            return await handler(parameters)

        # Intercept clarification - don't execute, return to user
        question = parameters.get("question", "")
        options = parameters.get("options", [])

        if self.clarification_callback:
            # Let callback handle the clarification
            response = await self.clarification_callback(question, options)
            return {"status": "success", "response": response}

        # Default: return clarification request
        return {
            "status": "clarification_needed",
            "question": question,
            "options": options,
            "context": parameters.get("context", ""),
        }


class MiddlewareChain:
    """Chain of middlewares to execute in order."""

    def __init__(self, middlewares: List[Middleware] = None):
        self.middlewares = middlewares or []

    def add(self, middleware: Middleware) -> "MiddlewareChain":
        self.middlewares.append(middleware)
        return self

    async def run_before_agent(self, context: MiddlewareContext) -> MiddlewareContext:
        for middleware in self.middlewares:
            context = await middleware.before_agent(context)
        return context

    async def run_after_agent(
        self,
        context: MiddlewareContext,
        result: Dict
    ) -> Dict:
        for middleware in reversed(self.middlewares):
            result = await middleware.after_agent(context, result)
        return result

    async def run_wrap_tool_call(
        self,
        context: MiddlewareContext,
        tool_name: str,
        parameters: Dict[str, Any],
        handler: Callable
    ) -> Dict[str, Any]:
        async def wrapped_handler(params):
            return await handler(params)

        # Wrap from last to first so first middleware runs first
        wrapped = wrapped_handler
        for middleware in reversed(self.middlewares):
            prev_wrapped = wrapped
            wrapped = lambda p, m=middleware, w=prev_wrapped: m.wrap_tool_call(
                context, tool_name, p, w
            )

        return await wrapped(parameters)
```

### 14.4 Implementation 3: SharedState for Cross-Agent Context

**Goal:** Provide a typed shared state that can be passed between agents.

**Create new file:** `src/agents/shared_state.py`

```python
"""Shared state for cross-agent context passing."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Annotated
from datetime import datetime


def merge_list(existing: List | None, new: List | None) -> List:
    """Reducer: merge and deduplicate lists."""
    if existing is None:
        return new or []
    if new is None:
        return existing
    return list(dict.fromkeys(existing + new))


def merge_dict(existing: Dict | None, new: Dict | None) -> Dict:
    """Reducer: merge dictionaries."""
    if existing is None:
        return new or {}
    if new is None:
        return existing
    return {**existing, **new}


@dataclass
class SharedState:
    """Shared state that can be passed between agents.

    Similar to deer-flow's ThreadState but framework-agnostic.
    """

    # Identifiers
    thread_id: Optional[str] = None
    trace_id: Optional[str] = None

    # Session data
    session_data: Dict[str, Any] = field(default_factory=dict)

    # Artifacts with reducer
    artifacts: Annotated[List[str], merge_list] = field(default_factory=list)

    # Uploaded files
    uploaded_files: List[Dict[str, Any]] = field(default_factory=list)

    # Working directories
    workspace_path: Optional[str] = None
    output_path: Optional[str] = None

    # Execution context
    current_agent: Optional[str] = None
    parent_agent: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Custom data store
    custom: Dict[str, Any] = field(default_factory=dict)

    def add_artifact(self, artifact: str) -> None:
        """Add an artifact (deduplicated)."""
        if artifact not in self.artifacts:
            self.artifacts.append(artifact)
            self.updated_at = datetime.now()

    def set(self, key: str, value: Any) -> None:
        """Set a custom value."""
        self.custom[key] = value
        self.updated_at = datetime.now()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a custom value."""
        return self.custom.get(key, default)

    def merge(self, other: "SharedState") -> "SharedState":
        """Merge another state into this one."""
        if other.thread_id:
            self.thread_id = other.thread_id
        if other.trace_id:
            self.trace_id = other.trace_id

        # Merge artifacts
        self.artifacts = merge_list(self.artifacts, other.artifacts)

        # Merge session data
        self.session_data = {**self.session_data, **other.session_data}

        # Merge custom data
        self.custom = {**self.custom, **other.custom}

        self.updated_at = datetime.now()
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "thread_id": self.thread_id,
            "trace_id": self.trace_id,
            "session_data": self.session_data,
            "artifacts": self.artifacts,
            "uploaded_files": self.uploaded_files,
            "workspace_path": self.workspace_path,
            "output_path": self.output_path,
            "current_agent": self.current_agent,
            "parent_agent": self.parent_agent,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SharedState":
        """Create from dictionary."""
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)
```

### 14.5 Implementation 4: Update MarkdownAgent to Support SharedState

**Modify:** `src/agents/markdown_agent.py`

```python
# Add to MarkdownAgent.__init__
def __init__(
    self,
    definition: AgentDefinition,
    memory_manager,
    tool_registry,
    model_manager: Optional[Model] = None,
    skills: Optional[List[str]] = None,
    skill_registry=None,
    shared_state: Optional[SharedState] = None,  # NEW
    middleware_chain: Optional[MiddlewareChain] = None,  # NEW
):
    # ... existing init ...
    self.shared_state = shared_state or SharedState()
    self.middleware_chain = middleware_chain

# Update process_task to use middleware
async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
    context = MiddlewareContext(
        agent_id=self.agent_id,
        task=task,
        state=self.shared_state.to_dict(),
    )

    # Run before_agent middlewares
    if self.middleware_chain:
        context = await self.middleware_chain.run_before_agent(context)

    try:
        if not self.definition.requires_model:
            result = await self._process_simple_task(task)
        else:
            result = await self._process_llm_task(task)

        # Run after_agent middlewares
        if self.middleware_chain:
            result = await self.middleware_chain.run_after_agent(context, result)

        return result
    except Exception as e:
        logger.error(f"Task processing failed for {self.agent_id}: {e}")
        return {"status": "error", "error": str(e), "agent_id": self.agent_id}
```

### 14.6 Implementation 5: Update Factory to Support Middleware

**Modify:** `src/agents/markdown_agent.py` (MarkdownAgentFactory)

```python
class MarkdownAgentFactory:
    def __init__(
        self,
        config_dir: Optional[Path] = None,
        middleware_chain: Optional[MiddlewareChain] = None,  # NEW
    ):
        self.parser = MarkdownParser(config_dir)
        self._definitions_cache: Dict[str, AgentDefinition] = {}
        self._tool_defs_cache: Dict[str, Dict[str, Any]] = {}
        self.middleware_chain = middleware_chain  # NEW

    def create_agent(
        self,
        agent_id: str,
        memory_manager,
        tool_registry,
        model_manager: Optional[Model] = None,
        skills: Optional[List[str]] = None,
        skill_registry=None,
        shared_state: Optional[SharedState] = None,  # NEW
    ) -> MarkdownAgent:
        definition = self.load_definition(agent_id)

        # ... existing tool registration ...

        return MarkdownAgent(
            definition=definition,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            model_manager=model_manager,
            skills=skills,
            skill_registry=skill_registry,
            shared_state=shared_state,  # NEW
            middleware_chain=self.middleware_chain,  # NEW
        )
```

### 14.7 Complete Integration Example

```python
# Example: Setting up GPTase with deer-flow-style features

from src.agents.markdown_agent import MarkdownAgentFactory
from src.agents.shared_state import SharedState
from src.middleware import (
    MiddlewareChain,
    ConcurrencyLimitMiddleware,
    ClarificationMiddleware,
)
from src.tools.task_tool import TaskTool
from src.tools.registry import ToolRegistry

# 1. Create middleware chain
middleware = MiddlewareChain()
middleware.add(ConcurrencyLimitMiddleware(max_concurrent=3))

async def handle_clarification(question: str, options: List[str]) -> str:
    """Custom clarification handler."""
    print(f"[CLARIFICATION NEEDED] {question}")
    if options:
        print(f"Options: {options}")
    return input("Your response: ")

middleware.add(ClarificationMiddleware(handle_clarification))

# 2. Create factory with middleware
factory = MarkdownAgentFactory(middleware_chain=middleware)

# 3. Create shared state
shared_state = SharedState(
    thread_id="thread-123",
    trace_id="trace-abc",
    workspace_path="/tmp/workspace",
    output_path="/tmp/outputs",
)

# 4. Create agents with shared state
tool_registry = ToolRegistry()
memory_manager = MemoryManager()

agent = factory.create_agent(
    "enzyme_kinetics_extractor",
    memory_manager,
    tool_registry,
    shared_state=shared_state,
)

# 5. Register TaskTool for delegation
task_tool = TaskTool(
    agent_factory=factory,
    memory_manager=memory_manager,
    tool_registry=tool_registry,
    max_concurrent=3,
)
tool_registry.register_tool(task_tool, category="delegation")

# 6. Process task
result = await agent.process_task({
    "description": "Extract enzyme kinetics",
    "text": "Variant V1 showed Km of 0.5 mM..."
})
```

### 14.8 Implementation Roadmap

| Phase | Features | Effort |
|-------|----------|--------|
| **Phase 1** | `TaskTool` for delegation | 2-3 days |
| **Phase 2** | `SharedState` class | 1-2 days |
| **Phase 3** | Middleware system + `ConcurrencyLimitMiddleware` | 2-3 days |
| **Phase 4** | `ClarificationMiddleware` | 1-2 days |
| **Phase 5** | Integration with existing agents | 1-2 days |
| **Phase 6** | Progress streaming (optional) | 3-5 days |

### 14.9 Key Design Decisions

1. **Middleware vs. Direct Hooks**: Choose middleware for flexibility, direct hooks for simplicity
2. **SharedState vs. Context Dict**: Use SharedState for type safety, context dict for simplicity
3. **TaskTool vs. SOP**: TaskTool for dynamic delegation, SOP for predefined workflows
4. **Async vs. Thread Pool**: Use asyncio for I/O-bound tasks, thread pool for CPU-bound tasks

## 15. Summary

| Feature | Deer-Flow | GPTase |
|---------|-----------|--------|
| Agent Definition | Python + Dataclass | Markdown + Metadata |
| Framework | LangChain/LangGraph | Custom |
| Middleware | 11-layer chain | None (implementation guide provided) |
| Memory | LLM-driven + Queue | Basic persistent |
| Tools | YAML + dynamic loading | Registry pattern |
| Subagent | Task tool | SOP workflow (TaskTool implementation provided) |
| Skills | Markdown + YAML | Agent capabilities |
| Config Format | YAML | JSON + Markdown |
| Best For | General AI apps | Domain-specific tasks |
