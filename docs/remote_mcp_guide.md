# 远程 MCP 服务部署指南

本文档说明如何在远程服务器上部署 MCP 工具服务，并让本地 GPTase 框架通过网络调用这些工具。

## 架构概述

```
┌─────────────────────────┐              HTTP/SSE              ┌──────────────────┐
│   Local GPTase          │ ─────────────────────────────────> │ Remote Tool Server│
│                         │ <────────────────────────────────  │                  │
│  - Agents               │       Call remote tools            │ - External DBs   │
│  - Orchestrator         │                                      │ - Heavy compute  │
│  - Tool Registry        │                                      │ - Specialized APIs│
│  - Local Tools          │                                      └──────────────────┘
└─────────────────────────┘
```

**核心思想**：GPTase 框架在本地运行，通过网络调用远程的**工具服务**。

---

## 为什么使用 fastmcp？

| 方案 | 代码行数 | 维护成本 | 官方支持 |
|------|----------|----------|----------|
| FastAPI 手动实现 | ~300+ 行 | 高（需处理协议细节） | 否 |
| **fastmcp** | **~50 行** | **低（自动处理协议）** | **是（Anthropic）** |

**fastmcp 优势**：
- ✅ 自动处理 MCP 协议细节
- ✅ 内置 SSE 和 stdio 传输支持
- ✅ 装饰器语法简洁
- ✅ 自动生成工具 schema
- ✅ 类型提示和验证

---

## 快速开始

### 1. 安装依赖

```bash
# 远程服务器上
pip install fastmcp httpx

# 本地 GPTase
pip install mcp
```

### 2. 创建远程工具服务器

在远程服务器上创建 `remote_tools.py`：

```python
from fastmcp import FastMCP
import httpx
import logging

# 创建 MCP 服务器实例
mcp = FastMCP("GPTase Remote Tools")
logger = logging.getLogger(__name__)

@mcp.tool()
async def query_pdb_database(pdb_code: str) -> dict:
    """Query PDB database for enzyme structure information.

    Args:
        pdb_code: 4-letter PDB code (e.g., "2rkx", "1a53")

    Returns:
        Dictionary containing structure information:
        - pdb_code: PDB identifier
        - title: Structure title
        - ec_number: EC enzyme classification (if available)
        - ligands: List of bound ligands
    """
    logger.info(f"Querying PDB for: {pdb_code}")

    # 实现你的数据库查询逻辑
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://files.rcsb.org/view/{pdb_code}.pdb"
        )
        response.raise_for_status()

        # 解析 PDB 文件（简化示例）
        content = response.text
        return {
            "pdb_code": pdb_code,
            "title": content.split("\n")[0][10:].strip(),
            "raw_content": content[:1000]  # 返回前 1000 字符作为示例
        }

@mcp.tool()
async def query_kegg_pathway(ec_number: str) -> dict:
    """Query KEGG database for pathway information.

    Args:
        ec_number: EC enzyme classification number (e.g., "3.1.1.7")

    Returns:
        Dictionary with pathway and gene information
    """
    logger.info(f"Querying KEGG for EC: {ec_number}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://rest.kegg.jp/link/pathway/ec:{ec_number}"
        )
        response.raise_for_status()

        return {
            "ec_number": ec_number,
            "pathways": response.text[:500]
        }

@mcp.tool()
async def run_heavy_computation(sequence: str, method: str = "default") -> dict:
    """Run heavy protein structure prediction.

    This is a placeholder for GPU-intensive computations that should run
    on a remote server with GPU access.

    Args:
        sequence: Protein amino acid sequence
        method: Computation method (default, fast, accurate)

    Returns:
        Predicted structure and confidence scores
    """
    logger.info(f"Running computation on sequence ({len(sequence)} aa)")

    # 这里实现你的重计算逻辑
    # 例如：调用 GPU 加速的折叠预测、分子对接等

    return {
        "sequence_length": len(sequence),
        "method": method,
        "confidence": 0.95,
        "predicted_structure": "..."  # 实际返回结构数据
    }

@mcp.tool()
async def batch_query_pdb(pdb_codes: list[str]) -> list[dict]:
    """Query multiple PDB structures in batch.

    Args:
        pdb_codes: List of 4-letter PDB codes

    Returns:
        List of structure information for each PDB code
    """
    results = []
    for pdb_code in pdb_codes:
        try:
            result = await query_pdb_database(pdb_code)
            results.append(result)
        except Exception as e:
            results.append({
                "pdb_code": pdb_code,
                "error": str(e)
            })
    return results

# 启动服务器
if __name__ == "__main__":
    # 使用 SSE 传输（适合远程连接）
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
```

### 3. 启动远程服务

```bash
# 在远程服务器上
python remote_tools.py

# 输出：
# INFO:     Started server process [12345]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 4. 配置防火墙

```bash
# 开放端口 8000
sudo ufw allow 8000/tcp

# 或使用 SSH 隧道（更安全，无需开放端口）
ssh -L 8000:localhost:8000 user@remote-server
```

### 5. 本地 GPTase 集成

在本地创建 `src/tools/mcp_remote.py`：

```python
"""MCP 远程工具包装器"""
import asyncio
import logging
from typing import Any, Dict, Optional

from mcp import ClientSession
from mcp.client.sse import sse_client

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class MCPRemoteClient:
    """MCP 远程客户端 - 连接到远程 fastmcp 服务器"""

    def __init__(self, server_url: str):
        """
        初始化远程 MCP 客户端

        Args:
            server_url: 远程服务器 URL (如 "http://remote-server:8000/sse")
        """
        self.server_url = server_url
        self._session: Optional[ClientSession] = None
        self._read = None
        self._write = None

    async def connect(self):
        """连接到远程 MCP 服务器"""
        logger.info(f"Connecting to remote MCP server: {self.server_url}")

        # 建立 SSE 连接
        self._read, self._write = await sse_client(self.server_url).__aenter__()
        self._session = ClientSession(self._read, self._write)

        # 初始化会话
        await self._session.initialize()
        logger.info("Connected to remote MCP server")

    async def disconnect(self):
        """断开连接"""
        if self._session:
            await self._session.close()
        logger.info("Disconnected from remote MCP server")

    async def list_tools(self) -> list[Dict[str, Any]]:
        """列出远程可用的工具"""
        if not self._session:
            await self.connect()

        tools_result = await self._session.list_tools()
        return tools_result.tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """调用远程工具"""
        if not self._session:
            await self.connect()

        logger.info(f"Calling remote tool: {name}")

        result = await self._session.call_tool(name, arguments)
        return result

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.disconnect()


class MCPRemoteTool(BaseTool):
    """将远程 MCP 工具包装为本地 Tool"""

    def __init__(self, client: MCPRemoteClient, tool_info: Dict[str, Any]):
        """
        初始化远程工具包装器

        Args:
            client: MCP 远程客户端实例
            tool_info: 工具信息（从 list_tools 获取）
        """
        self.client = client
        self.tool_info = tool_info

        super().__init__(
            name=tool_info["name"],
            description=tool_info.get("description", ""),
            timeout=300
        )

    async def execute(self, **kwargs) -> ToolResult:
        """执行远程工具调用"""
        try:
            result = await self.client.call_tool(self.name, kwargs)

            # MCP 返回格式：{"content": [{"type": "text", "text": "..."}]}
            if result and result.get("content"):
                text_content = result["content"][0].get("text", "")
                return ToolResult.success(data={"result": text_content})

            return ToolResult.success(data=result)

        except Exception as e:
            logger.error(f"Remote tool call failed: {e}")
            return ToolResult.error(error=str(e))

    def get_schema(self) -> dict:
        """获取工具参数 schema"""
        # 从 tool_info 提取 schema
        return self.tool_info.get("inputSchema", {"type": "object"})


async def discover_and_register_remote_tools(
    tool_registry,
    server_url: str
) -> int:
    """
    发现并注册远程工具到本地工具注册表

    Args:
        tool_registry: 本地 ToolRegistry 实例
        server_url: 远程 MCP 服务器 URL

    Returns:
        注册的工具数量
    """
    async with MCPRemoteClient(server_url) as client:
        # 获取远程工具列表
        tools = await client.list_tools()

        logger.info(f"Discovered {len(tools)} remote tools")

        # 为每个工具创建包装器并注册
        registered_count = 0
        for tool_info in tools:
            tool = MCPRemoteTool(client, tool_info)

            # 重新创建客户端（避免共享连接）
            tool.client = MCPRemoteClient(server_url)

            tool_registry.register_tool(tool)
            registered_count += 1
            logger.info(f"Registered remote tool: {tool_info['name']}")

        return registered_count
```

### 6. 自动注册远程工具

在 `src/tools/registry.py` 中添加自动发现功能：

```python
# 在 ToolRegistry 类中添加方法
async def register_remote_tools(self, servers: Dict[str, str]):
    """
    从多个远程服务器注册工具

    Args:
        servers: 服务器名称到 URL 的映射
                 {"database": "http://db-server:8000/sse",
                  "compute": "http://gpu-server:8000/sse"}
    """
    from src.tools.mcp_remote import discover_and_register_remote_tools

    total_registered = 0
    for server_name, server_url in servers.items():
        try:
            count = await discover_and_register_remote_tools(
                self, server_url
            )
            total_registered += count
            logger.info(f"Registered {count} tools from {server_name}")
        except Exception as e:
            logger.error(f"Failed to connect to {server_name}: {e}")

    logger.info(f"Total remote tools registered: {total_registered}")
    return total_registered
```

### 7. 配置文件

在 `config/llm_config.template.json` 中添加远程服务器配置：

```json
{
  "mcp_remote_servers": {
    "database_server": {
      "url": "http://your-db-server.com:8000/sse",
      "enabled": true,
      "description": "Remote database lookup tools"
    },
    "compute_server": {
      "url": "http://your-gpu-server.com:8000/sse",
      "enabled": true,
      "description": "GPU-intensive computation tools"
    }
  }
}
```

### 8. 使用示例

```python
# 在 Agent 或 Orchestrator 中使用
from src.tools.registry import ToolRegistry
from src.core.config import FrameworkConfig

config = FrameworkConfig()
registry = ToolRegistry()

# 注册远程工具
await registry.register_remote_tools(
    config.mcp_remote_servers
)

# 现在可以像使用本地工具一样使用远程工具
result = await registry.execute("query_pdb_database", pdb_code="2rkx")
print(result)
```

---

## 部署选项

### 选项 1：直接运行（开发/测试）

```bash
python remote_tools.py
```

### 选项 2：使用 systemd（生产环境）

创建 `/etc/systemd/system/mcp-tools.service`：

```ini
[Unit]
Description=GPTase MCP Remote Tools Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/your/project
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python remote_tools.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcp-tools
sudo systemctl start mcp-tools
sudo systemctl status mcp-tools
```

### 选项 3：使用 Docker

创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY remote_tools.py .

EXPOSE 8000

CMD ["python", "remote_tools.py"]
```

运行容器：

```bash
docker build -t gptase-mcp-tools .
docker run -d -p 8000:8000 --name mcp-tools gptase-mcp-tools
```

### 选项 4：使用 Nginx 反向代理（推荐）

```nginx
# /etc/nginx/sites-available/mcp-tools
server {
    listen 80;
    server_name your-domain.com;

    location /mcp {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_cache off;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

---

## 安全建议

### 1. 使用 API 密钥认证

```python
# remote_tools.py 中添加
from fastapi import Header, HTTPException

API_KEYS = {"your-secret-key": "client1"}

@mcp.sse_app.middleware("http")
async def verify_api_key(request: Request, call_next):
    api_key = request.headers.get("X-API-Key")
    if api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return await call_next(request)
```

### 2. 使用 HTTPS

```python
# 使用 SSL 证书
mcp.run(
    transport="sse",
    host="0.0.0.0",
    port=8443,
    ssl_keyfile="/path/to/key.pem",
    ssl_certfile="/path/to/cert.pem"
)
```

### 3. 限制访问来源

```python
# 在 fastmcp 应用中添加 CORS 限制
from fastapi.middleware.cors import CORSMiddleware

mcp.sse_app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # 只允许特定域名
    allow_methods=["POST"],
    allow_headers=["*"],
)
```

---

## 监控和日志

### 添加结构化日志

```python
import structlog

logger = structlog.get_logger()

@mcp.tool()
async def monitored_tool(param: str) -> dict:
    """带日志监控的工具"""
    logger.info("tool_started", param=param)

    try:
        result = await do_work(param)
        logger.info("tool_completed", param=param, result_size=len(result))
        return result
    except Exception as e:
        logger.error("tool_failed", param=param, error=str(e))
        raise
```

### 健康检查端点

```python
@mcp.sse_app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "server": "gptase-mcp-tools",
        "tools_count": len(mcp._tools)
    }
```

---

## 故障排查

### 问题：连接超时

```bash
# 检查端口是否开放
telnet remote-server 8000

# 检查防火墙
sudo ufw status

# 使用 curl 测试
curl http://remote-server:8000/health
```

### 问题：工具调用失败

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 检查远程服务器日志
tail -f /var/log/mcp-tools.log
```

### 问题：性能慢

```python
# 使用连接池
from httpx import AsyncClient, Limits

client = AsyncClient(
    limits=Limits(max_connections=100, max_keepalive_connections=20)
)
```

---

## 完整示例项目

```
remote-mcp-tools/
├── remote_tools.py          # fastmcp 服务器主文件
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── config/
│   └── logging.conf
└── tests/
    └── test_remote_tools.py
```

---

## 参考资料

- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [fastmcp GitHub](https://github.com/jlowin/fastmcp)
- [GPTase Framework](../README.md)
