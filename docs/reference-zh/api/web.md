# Web UI API

> [首页](../README.md) → [常见任务](../common-tasks.md) → Web UI API

GPTase Web UI 基于 FastAPI 构建，提供 REST API 和 WebSocket 接口。

## 启动服务

```bash
# 构建前端（首次）
cd ui && ./build.sh

# 启动服务
gptase web --port 8000 --host 127.0.0.1
```

默认地址：`http://127.0.0.1:8000`

---

## REST API

### 列出 Agent

```
GET /api/agents
```

返回所有可用 Agent，第一个是 Auto 编排器。

**响应示例：**

```json
[
  {"id": "auto", "name": "Auto (Orchestrator)"},
  {"id": "enzyme-kinetics-extractor", "name": "enzyme-kinetics-extractor"},
  {"id": "vision-image-analyzer", "name": "vision-image-analyzer"}
]
```

---

### 列出 Plan

```
GET /api/plans
```

返回所有可用的 Plan 工作流。

**响应示例：**

```json
[
  {"plan_id": "enzyme_extraction_pipeline", "name": "Enzyme Extraction Pipeline", "version": "1.0"},
  {"plan_id": "literature_review", "name": "Literature Review", "version": "1.0"}
]
```

---

### 获取 Plan 定义

```
GET /api/plans/{plan_id}
```

返回指定 Plan 的完整定义。

**响应示例：**

```json
{
  "plan_id": "enzyme_extraction_pipeline",
  "name": "Enzyme Extraction Pipeline",
  "version": "1.0",
  "workflow": [
    {"step_id": "1", "agent": "document-structure-analyzer", "action": "analyze"},
    {"parallel": [
      {"step_id": "2a", "agent": "vision-image-analyzer"},
      {"step_id": "2b", "agent": "enzyme-kinetics-extractor"}
    ]},
    {"step_id": "3", "agent": "literature-synthesis"}
  ]
}
```

---

### 与 Agent 对话

```
POST /api/chat
```

向指定 Agent 发送消息。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `agent_id` | string | 是 | Agent ID，使用 `auto` 启用自动编排 |
| `message` | string | 是 | 用户消息 |
| `image_paths` | string[] | 否 | 图片路径列表（多模态任务） |

**请求示例：**

```json
{
  "agent_id": "enzyme-kinetics-extractor",
  "message": "从以下文本中提取 Km 和 kcat 值...",
  "image_paths": ["/path/to/figure.png"]
}
```

**响应示例：**

```json
{
  "status": "success",
  "data": {
    "content": "提取到的动力学参数如下：\n- Km: 0.5 mM\n- kcat: 120 s^-1"
  },
  "agent_id": "enzyme-kinetics-extractor"
}
```

**错误响应：**

```json
{
  "status": "error",
  "error": "Agent not found: unknown-agent"
}
```

---

### 启动 Plan 执行

```
POST /api/plan/run
```

在后台启动 Plan 工作流执行。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `plan_id` | string | 是 | Plan 工作流 ID |
| `input_data` | object | 是 | 输入数据字典 |
| `document_path` | string | 否 | 文档路径 |

**请求示例：**

```json
{
  "plan_id": "enzyme_extraction_pipeline",
  "input_data": {
    "text": "论文全文内容..."
  },
  "document_path": "/path/to/paper_dir"
}
```

**响应示例：**

```json
{
  "session_id": "plan_web_a1b2c3d4",
  "status": "started"
}
```

---

### 列出 Session

```
GET /api/sessions
```

返回最近的 Plan 执行会话。

**响应示例：**

```json
[
  {
    "session_id": "plan_web_a1b2c3d4",
    "plan_id": "enzyme_extraction_pipeline",
    "status": "completed",
    "progress": 100,
    "completed_steps": 3,
    "total_steps": 3,
    "created_at": "2024-03-10T12:00:00"
  },
  {
    "session_id": "plan_web_e5f6g7h8",
    "plan_id": "literature_review",
    "status": "running",
    "progress": 50,
    "completed_steps": 1,
    "total_steps": 2,
    "created_at": "2024-03-10T12:30:00"
  }
]
```

---

### 获取 Session 状态

```
GET /api/sessions/{session_id}
```

返回指定会话的详细状态。

**响应示例：**

```json
{
  "session_id": "plan_web_a1b2c3d4",
  "plan_id": "enzyme_extraction_pipeline",
  "status": "completed",
  "progress": 100,
  "completed_steps": 3,
  "total_steps": 3,
  "created_at": "2024-03-10T12:00:00",
  "step_results": {
    "1": {"status": "success", "data": {...}},
    "2a": {"status": "success", "data": {...}},
    "2b": {"status": "success", "data": {...}}
  }
}
```

---

## WebSocket

### Plan 实时更新

```
WS /ws/plan/{session_id}
```

连接后接收 Plan 执行的实时状态更新。

**消息格式：**

```json
{
  "type": "update",
  "data": {
    "session_id": "plan_web_a1b2c3d4",
    "status": "running",
    "progress": 50,
    "completed_steps": 1,
    "total_steps": 2
  }
}
```

**消息类型：**

| type | 说明 |
|---|---|
| `status` | 连接状态确认 |
| `update` | 执行进度更新 |

---

## 技术栈

| 组件 | 技术 |
|---|---|
| 后端框架 | FastAPI |
| ASGI 服务器 | Uvicorn |
| 前端框架 | React + TypeScript |
| 构建工具 | Vite |
| UI 组件 | Lucide Icons, React Markdown |

---

## 前端开发

```bash
cd ui

# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build
```

构建产物位于 `ui/dist/`，由 FastAPI 静态文件服务托管。

---

*下一层详情：[internals/ →](../internals/execution-flow.md)*
