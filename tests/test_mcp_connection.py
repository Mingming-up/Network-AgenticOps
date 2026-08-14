# 基础 MCP 连通性测试：只验证能否发现并调用 greet，不执行网络配置。
import os

import pytest
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# 优先读取本地 .env；未配置时连接本机 8000 端口。
load_dotenv()

MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")


@pytest.mark.asyncio
async def test_mcp_greet_tool():
    # 创建异步 MCP Client，测试期间由上下文管理器负责建立和关闭连接。
    client = Client(StreamableHttpTransport(MCP_URL))

    async with client:
        # 先验证服务端注册了 greet，再检查一次实际调用的返回内容。
        tools = await client.list_tools()
        assert any(tool.name == "greet" for tool in tools), "Tool 'greet' not found"
        response = await client.call_tool("greet", {"name": "Network Engineer"})

        assert response is not None
        assert "Network Engineer" in str(response)
