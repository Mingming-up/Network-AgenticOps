"""CML virtual-switch MCP server for the Network-AgenticOps closed loop."""

# 这是已完成 CML-Free/IOL-L2 闭环使用的真实设备连接层。
# 它接收 Agent 的 MCP 工具调用，再通过 Netmiko 登录隔离的 Cisco 虚拟交换机。
import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from netmiko import ConnectHandler

# 设备地址和凭据只从本地 .env 读取，避免把秘密写进代码或提交到 Git。
load_dotenv()

# FastMCP 实例负责注册工具并对外提供 HTTP MCP 服务。
mcp = FastMCP("network-agent")


def get_device_config() -> dict:
    """Load the planned CML IOL-L2 connection from local environment variables."""
    # 先一次性检查必填项，错误信息会明确指出缺少哪些环境变量。
    required = [
        "NETWORK_DEVICE_HOST",
        "NETWORK_DEVICE_USERNAME",
        "NETWORK_DEVICE_SECRET",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    # 返回格式与 Netmiko 的 ConnectHandler 参数保持一致。
    return {
        "host": os.environ["NETWORK_DEVICE_HOST"],
        "port": int(os.getenv("NETWORK_DEVICE_PORT", "22")),
        "device_type": os.getenv("NETWORK_DEVICE_TYPE", "cisco_ios"),
        "username": os.environ["NETWORK_DEVICE_USERNAME"],
        "secret": os.environ["NETWORK_DEVICE_SECRET"],
    }


@mcp.tool(description="Return a greeting used to test MCP connectivity.")
def greet(name: str) -> str:
    # greet 不访问设备，只用来验证 Agent 与 MCP Server 的基础连通性。
    return f"Hello, {name}!"


def get_connection():
    # 每次工具调用单独建立连接，避免长期保存失效或泄漏的 SSH 会话。
    connection = ConnectHandler(**get_device_config())
    connection.enable()
    return connection


@mcp.tool(description="Retrieve the administrative and operational state of an interface.")
def get_interface_state(interface: str) -> dict:
    connection = get_connection()
    try:
        # include 让交换机只返回目标接口所在行，便于后续解析状态字段。
        output = connection.send_command(f"show ip interface brief | include {interface}")
    finally:
        # 即使命令执行或解析失败，也必须断开设备连接。
        connection.disconnect()

    # Cisco IOS 的简要接口输出中，第 5、6 列分别是管理状态和协议状态。
    parts = output.split()
    if len(parts) < 6:
        raise ValueError(f"Unexpected interface output: {output!r}")

    return {
        "interface": interface,
        "admin_state": parts[4],
        "oper_state": parts[5],
    }


@mcp.tool(description="Ping an IP address from the CML virtual switch.")
def check_endpoint(ip: str) -> dict:
    connection = get_connection()
    try:
        output = connection.send_command(f"ping {ip}", read_timeout=60)
    finally:
        connection.disconnect()

    # IOS ping 输出出现 0 percent 时判定不可达；其他情况在此简化为可达。
    return {
        "ip": ip,
        "reachable": "Success rate is 0 percent" not in output,
    }


@mcp.tool(description="Execute no shutdown on an interface in the isolated CML lab.")
def no_shutdown(interface: str) -> dict:
    connection = get_connection()
    try:
        # send_config_set 会进入配置模式并按顺序执行这两条 IOS 命令。
        connection.send_config_set([f"interface {interface}", "no shutdown"])
    finally:
        connection.disconnect()

    return {
        "interface": interface,
        "action": "no shutdown",
        "status": "applied",
    }


@mcp.tool(description="Retrieve the running configuration for one interface.")
def get_interface_config(interface: str) -> dict:
    connection = get_connection()
    try:
        output = connection.send_command(f"show running-config interface {interface}")
    finally:
        connection.disconnect()

    return {"interface": interface, "config": output.strip()}


@mcp.tool(description="Retrieve the full running configuration of the CML switch.")
def get_running_config() -> dict:
    connection = get_connection()
    try:
        output = connection.send_command("show running-config")
    finally:
        connection.disconnect()

    return {"config": output.strip()}


@mcp.tool(description="Apply IOS configuration commands in the isolated CML lab.")
def apply_config(config_list: list[str]) -> dict:
    # 该工具可以修改多条配置，因此未来必须配合白名单、审批和回滚机制使用。
    connection = None
    try:
        connection = get_connection()
        output = connection.send_config_set(config_list)
        # Cisco IOS 常用这些文本表示命令错误；发现后不把操作报告为成功。
        if "%" in output or "Invalid" in output or "Incomplete" in output:
            return {"status": "failed", "error": output.strip()}
        return {"status": "applied"}
    except Exception as error:
        return {"status": "failed", "error": str(error)}
    finally:
        if connection is not None:
            connection.disconnect()


if __name__ == "__main__":
    # 以 Streamable HTTP 方式启动服务，供 Agent 通过 MCP_URL 连接。
    mcp.run(transport="streamable-http")
