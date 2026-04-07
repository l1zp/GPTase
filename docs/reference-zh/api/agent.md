# Agent API

> [首页](../README.md) → [API](.) → Agent

**文件：** `gptase/agents/base.py`

---

## 创建 Agent

### 从 Markdown 定义创建（推荐）

```python
from gptase.agents.base import Agent
from gptase.models.model import Model

model = Model()

# 通过 Agent 名称（查找 .claude/agents/{name}/{name}.md 或 .claude/agents/{name}.md）
agent = Agent.from_markdown("enzyme-kinetics-extractor", model_manager=model)

# 通过直接文件路径
agent = Agent.from_markdown("/path/to/agent.md", model_manager=model)

# 自定义搜索目录
agent = Agent.from_markdown("my-agent", config_dir=Path("/custom/agents/"))
```

名称查找同时支持连字符和下划线：`my-agent` 和 `my_agent` 都能找到同一个文件。

### 直接构造

```python
from gptase.agents.types import AgentMode

agent = Agent(
    system_prompt="你是一个有用的助手。",
    tools=["Read", "Grep", "Bash"],
    model_config=model_config,       # ModelConfig 实例
    model_name="claude-sonnet-4-6",  # 仅用于路由判断（当没有 model_config 时）
    agent_id="my-agent",
    workspace_dir="/path/to/workspace",
    mode=AgentMode.DIRECT,           # 执行模式 (DIRECT 或 PLAN)
    max_iterations=10,               # 最大工具轮次 / Claude SDK 最大回合数
)
```

---

## 执行

### `run()` — 主入口

```python
result = await agent.run(
    content: Union[str, List[Dict]],     # 文本字符串或预构建的内容列表
    image_paths: Optional[List[str]] = None,
) -> Dict[str, Any]
```

**返回值：**
```python
{"status": "success", "data": {"content": "..."}}              # 成功
{"status": "error",   "error": "..."}                          # 出错
{"status": "error",   "error": "...", "agent_id": "..."}       # process_task 出错
```

**路由逻辑：** `model_name.startswith("claude-")` → Claude SDK；否则 → LLM 循环。

`max_iterations` 会在两条路径中同时生效：
- Claude SDK 路径：作为 `max_turns`
- 非 Claude 路径：传给 `ToolExecutor(max_iterations=...)`

### `process_task()` — 结构化输入

```python
result = await agent.process_task(task: AgentTask) -> Dict[str, Any]
```

从 task 中提取图片路径，将 task 字段序列化为 JSON 注入 prompt，然后调用 `run()`。

### `is_claude_model()`

```python
agent.is_claude_model() -> bool
```

检查 `model_name.startswith("claude-")`，内部用于路由判断。

---

## 执行模式 (AgentMode)

Agent 支持两种执行模式（由 `gptase.agents.types.AgentMode` 定义）：

- `AgentMode.DIRECT`（默认）：立即启动 LLM 循环直接执行任务。
- `AgentMode.PLAN`：先调用 LLM 将目标拆解为一个结构化的有向无环图（DAG），生成包含多个 `PlannedTask` 的 `Plan`，然后按依赖顺序逐步执行这些子任务。

你可以在构造 Agent 时设置默认模式，或在每次调用时覆盖它：

```python
from gptase.agents.types import AgentMode

# 以规划模式运行
result = await agent.run("复杂的任务目标", mode=AgentMode.PLAN)
```

### 手动管理 Plan

如果你想在执行前检查、修改或审批计划，也可以直接使用 Agent 内部的 `PlanManager`：

```python
# 1. 生成计划
plan = await agent.planner.create_plan(goal="复杂的任务目标")

print(f"生成了 {len(plan.tasks)} 个子任务。")
for task in plan.tasks:
    print(f"- {task.description} (依赖: {task.dependencies})")

# 2. 执行计划
result = await agent.planner.execute_plan(plan)
```

> **注意：** 预定义的 Plan (`config/plans/*.yaml`) 在概念上就是由人类事先编写好的 `Plan`，以此跳过 LLM 动态规划的步骤。

---

## AgentTask

**文件：** `gptase/agents/types.py`

Pydantic 模型，设置 `extra="allow"` — 任何额外字段都被接受并以 JSON 形式注入 prompt。

```python
from gptase.agents.types import AgentTask

task = AgentTask(
    description="提取酶动力学参数",              # 可选，默认："Process the following data"
    workspace_dir="/path/to/workspace",          # 可选
    image_path="single.png",                     # 可选，单张图片
    image_paths=["img1.png", "img2.png"],        # 可选，图片列表
    images=["img3.png"],                         # 可选，备选图片字段
    # 任意额外字段：
    document_text="...",
    source="Nature 2024",
)

task.to_dict()           # 排除 None 值
task.get_extra_fields()  # 只返回未声明的额外字段
AgentTask.from_dict(data_dict)
```

图片去重：三个图片字段（`image_path`、`image_paths`、`images`）合并去重，保留顺序。

---

## 图片加载 {#图片加载}

`Agent._load_image_as_content(image_path)` 对每张图片执行：

1. 以二进制模式读取文件
2. Base64 编码内容
3. 根据文件扩展名检测 MIME 类型

| 扩展名 | MIME 类型 |
|---|---|
| `.jpg`, `.jpeg` | `image/jpeg` |
| `.png` | `image/png` |
| `.gif` | `image/gif` |
| `.webp` | `image/webp` |
| 其他 | `image/jpeg`（回退） |

返回：
```python
{
    "type": "image_url",
    "image_url": {"url": "data:image/png;base64,<编码内容>"}
}
```

图片列表前置于消息内容，文本跟在最后。文件不存在或加载失败时记录警告，跳过（非致命错误）。

---

## Markdown 格式 {#markdown-格式}

`.claude/agents/` 中的 Agent 文件必须包含 YAML 头部。支持两种布局：

```
.claude/agents/
  {name}/{name}.md     # 目录布局（推荐）
  {name}.md            # 平铺布局（兼容旧版）
```

**目录布局（推荐）：**
```
.claude/agents/my-agent/
  my-agent.md          # Agent 定义文件
```

**文件格式：**

```markdown
---
name: my-agent
description: 一句话描述这个 Agent 的用途
tools: Read, Grep, Glob, Bash
skills: pdf-extractor, academic-search
model: claude-sonnet-4-6
color: blue
---

系统 prompt 正文从这里开始。--- 之后的所有内容都是 system_prompt。

## 工作流程
...

## 输出格式
...
```

| 头部字段 | 是否必填 | 说明 |
|---|---|---|
| `name` | 是 | Agent ID — 必须与文件名（不含扩展名）匹配 |
| `description` | 是 | 显示在 `gptase list` 输出中 |
| `tools` | 否 | 逗号分隔的工具名称列表 |
| `skills` | 否 | 逗号分隔的 skill 名称列表，内容会追加到 system_prompt |
| `model` | 否 | 当前仅作说明用途；`Agent.from_markdown()` 目前不会应用它 |
| `color` | 否 | 在 Claude Code 界面中的显示颜色 |
| `max_iterations` | 否 | 最大工具调用轮次 / Claude SDK 最大回合数，默认 `10` |

> 当前行为：按 Agent 的模型选择来自 `FrameworkConfig.agent_models`，不是 markdown frontmatter 里的 `model:`。

---

## 内置工具 {#内置工具}

以下工具由 `gptase/tools/handlers.py` 注册，可在任意 Agent 的 `tools:` 字段中直接使用。

| 工具名 | 说明 |
|---|---|
| `Read` | 读取本地文件内容（支持行号/偏移量） |
| `Grep` | 正则模式搜索文件内容 |
| `Glob` | Glob 模式匹配文件路径 |
| `Bash` | 执行 Bash 命令（含危险命令拦截） |
| `DelegateTask` | 将子任务委派给另一个 Agent 执行 |
| `Todo` | 管理当前执行会话的 todo 列表（见下方） |

### Todo 工具 {#todo-工具}

`Todo` 是一个统一的任务追踪工具，让 Agent 能像 Claude Code 一样自主规划和追踪子任务进度。

**在 Agent 定义中启用：**

```markdown
---
name: my-agent
tools: Read, Grep, Todo
---
```

**三个操作（通过 `action` 参数区分）：**

```
# 创建任务（返回 8 位 ID）
Todo(action="create", content="提取 Km 值", priority="high")
  → [OK] Created todo [ef57b4fc] (high): 提取 Km 值

# 更新状态
Todo(action="update", todo_id="ef57b4fc", status="in_progress")
Todo(action="update", todo_id="ef57b4fc", status="completed")

# 列出所有任务
Todo(action="list")
  → [x] [ef57b4fc] (high) 提取 Km 值
    [ ] [9c2284ba] (medium) 生成报告
```

**状态图标：**

| 状态 | 图标 |
|---|---|
| `pending` | `[ ]` |
| `in_progress` | `[~]` |
| `completed` | `[x]` |
| `cancelled` | `[-]` |

**优先级：** `high` / `medium`（默认）/ `low`

**生命周期：** Todo 数据仅保存在当前执行会话的内存中，每次 `ToolExecutor.execute()` 开始时自动清空，不跨会话持久化。

---

## Skills {#skills}

Skills 是可复用的 prompt 片段，定义在 `.claude/skills/{skill_name}/SKILL.md` 中。Agent 加载时会将指定的 skill 内容追加到 system_prompt 末尾。

### Skill 文件格式

每个 skill 目录包含一个 `SKILL.md` 文件：

```markdown
---
name: pdf-extractor
description: |
  Extract content from PDF documents with MinerU.
  Trigger for requests like "read this PDF", "OCR this scanned PDF", or "extract tables from this PDF".
---

# PDF Extractor

Use MinerU to turn PDFs into Markdown and structured content.

## Routing

1. 如果存在 `MINERU_TOKEN`，优先使用 MinerU Cloud API。
2. 只有在没有 token 且 PDF 较小、较简单时才使用 `flash-extract`。
3. 对 OCR、表格、公式或大文件场景，本地 CLI 作为兜底方案。
```

Skill 文件同样使用 YAML frontmatter，`description` 字段用于触发词匹配。

### 目录结构

```
.claude/skills/{skill_name}/
  SKILL.md              # Skill 定义（必需）
  agents/openai.yaml    # UI 元数据（可选）
  evals/evals.json      # 行为评测用例（可选）
  references/           # 按需加载的参考文件（可选）
  tests/
    trigger_eval.json   # 触发条件测试用例（可选）
```

### 加载机制

```python
# Agent.from_markdown() 内部流程：
# 1. 解析 YAML 头部中的 skills 字段
# 2. 从 .claude/skills/{skill_name}/SKILL.md 加载内容
# 3. 剥离 skill 文件的 frontmatter
# 4. 将 skill body 追加到 agent system_prompt 末尾
```

### 示例

Agent 定义（`.claude/agents/research-agent/research-agent.md`）：

```markdown
---
name: research-agent
description: Research assistant with PDF reading capabilities
tools: Read, Grep, Glob
skills: pdf-extractor, academic-search
---

你是一个研究助手，专门帮助用户进行学术研究。

## 重点工作

1. 文献检索与分析
2. 数据提取与整理
```

加载后的实际 system_prompt：

```
你是一个研究助手，专门帮助用户进行学术研究。

## 重点工作

1. 文献检索与分析
2. 数据提取与整理

# PDF Extractor

Use MinerU to turn PDFs into Markdown and structured content...

# Academic Search

Search academic papers and publication metadata via OpenAlex, Semantic Scholar, Crossref, and Europe PMC...
```

### 内置 Skills

| Skill | 用途 |
|---|---|
| `pdf-extractor` | 使用 MinerU 提取 PDF 内容；设置 `MINERU_TOKEN` 时优先走 Cloud API |
| `biochem_databases` | 生化数据库查询（Rhea, KEGG, PDB, UniProt, PubChem, ChEBI 等） |
| `academic-search` | 跨 OpenAlex、Semantic Scholar、Crossref 和 Europe PMC 的学术文献检索 |
| `deadcode` | 无用代码识别与删除 |

### Skill 测试

每个 skill 可包含测试用例验证触发条件是否正确。

**测试文件位置：** `.claude/skills/{skill_name}/tests/trigger_eval.json`

**基础测试用例格式：**

```json
[
  {"query": "应该触发的查询", "should_trigger": true},
  {"query": "不应触发的查询", "should_trigger": false}
]
```

**边界测试用例（验证执行行为）：**

```json
{
  "query": "搜索一下今年内的kemp酶相关的文章",
  "should_trigger": true,
  "category": "boundary",
  "expected_behavior": {
    "use_openalex_api": true,
    "filter_by_date": true,
    "search_keyword": "kemp enzyme",
    "NOT_use_biochem_databases": true
  },
  "reason": "意图是文献检索，不是生化数据查询"
}
```

边界测试用例用于验证：
- 正确的 skill 被触发（避免多 skill 关键词冲突）
- 正确的 API/工具被使用
- 正确的参数被应用（日期过滤、关键词等）

**运行测试：**

```bash
# 测试指定 skill
gptase agent -n skill-tester -d "Test biochem_databases skill"

# 指定测试文件
gptase agent -n skill-tester -d "Test biochem_databases skill with .claude/skills/biochem_databases/tests/trigger_eval.json"
```

---

## AgentDefinition 与 AgentState

```python
@dataclass
class AgentDefinition:
    name: str
    description: str = ""
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""
    skills: List[str] = field(default_factory=list)  # 已加载的 skill 名称列表

    @property
    def agent_id(self) -> str: ...  # name 的别名

class AgentState(BaseModel):
    agent_id: str
    status: str = "idle"
    current_task: Optional[str] = None
```

---

*相关：[Plan API →](./plan.md) | [Model API →](./model.md)*
