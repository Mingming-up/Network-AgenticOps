# 这是模拟 MCP Server 的端到端状态转换测试。
# 运行测试前必须先单独启动 simulation/mock_mcp_server.py。
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


MCP_URL = "http://127.0.0.1:8000/mcp"
VIP_IP = "192.168.254.10"
USER_PORT = "Ethernet3/0"

EXPECTED_TOOLS = {
    "greet",
    "check_endpoint",
    "get_interface_state",
    "get_interface_config",
    "get_running_config",
    "no_shutdown",
    "apply_config",
}


def unpack_result(result) -> dict:
    """Extract the dictionary returned by a FastMCP tool."""
    # FastMCP 不同返回包装形式都统一转换成普通字典，方便后面的断言读取。
    data = result.structured_content
    assert data is not None, "Tool returned no structured content."

    if set(data) == {"result"}:
        return data["result"]

    return data


@pytest.mark.asyncio
async def test_mock_repair_flow():
    # Arrange：创建客户端并连接已经运行的模拟 MCP Server。
    client = Client(StreamableHttpTransport(MCP_URL))

    async with client:
        # 先确认 Agent 需要的全部工具都已注册，避免只测到部分功能。
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        assert EXPECTED_TOOLS.issubset(tool_names)

        # Assert before：初始故障状态下，VIP 应不可达且接口应为 administratively down。
        endpoint_before = unpack_result(
            await client.call_tool(
                "check_endpoint",
                {"ip": VIP_IP},
            )
        )
        assert endpoint_before["reachable"] is False

        interface_before = unpack_result(
            await client.call_tool(
                "get_interface_state",
                {"interface": USER_PORT},
            )
        )
        assert interface_before["admin_state"] == "administratively"
        assert interface_before["oper_state"] == "down"

        # Act：调用与真实 Server 同名的 no_shutdown 工具执行模拟修复。
        repair_result = unpack_result(
            await client.call_tool(
                "no_shutdown",
                {"interface": USER_PORT},
            )
        )
        assert repair_result["status"] == "applied"

        # Assert after：接口状态和 VIP 可达性都必须随修复发生变化。
        interface_after = unpack_result(
            await client.call_tool(
                "get_interface_state",
                {"interface": USER_PORT},
            )
        )
        assert interface_after["admin_state"] == "up"
        assert interface_after["oper_state"] == "up"

        endpoint_after = unpack_result(
            await client.call_tool(
                "check_endpoint",
                {"ip": VIP_IP},
            )
        )
        assert endpoint_after["reachable"] is True
