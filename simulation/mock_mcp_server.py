# 这是当前模拟闭环使用的 MCP Server。
# 它不会连接真实交换机，而是用 LAB_STATE 字典模拟接口、VLAN 和 VIP 状态变化。
from fastmcp import FastMCP

# 工具名和返回字段尽量与后续真实 CML Server 一致，这样 Agent 无需更换协议。
mcp = FastMCP("network-agent-mock")

VIP_IP = "192.168.254.10"
USER_PORT = "Ethernet3/0"
ACCESS_VLAN = 100

# 模拟交换机的初始故障状态：端口被管理员 shutdown，因此 VIP 不可达。
# Server 每次重启都会重新创建这个字典，也就恢复到初始故障状态。
LAB_STATE = {
    "admin_state": "administratively",
    "oper_state": "down",
    "access_vlan": ACCESS_VLAN,
}


def validate_interface(interface: str) -> None:
    # 模拟环境只允许操作一个指定接口，防止测试误以为任意接口都存在。
    if interface != USER_PORT:
        raise ValueError(
            f"Unknown simulated interface: {interface}. "
            f"Use {USER_PORT}."
        )


@mcp.tool(
    # annotations 向 MCP Client 描述工具的安全属性，不会代替函数内部校验。
    annotations={
        "title": "Greeting Test",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def greet(name: str) -> str:
    """Return a greeting used to test MCP connectivity."""
    return f"Hello, {name}!"


@mcp.tool(
    annotations={
        "title": "Check Simulated Endpoint",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def check_endpoint(ip: str) -> dict:
    """Check whether the simulated VIP is reachable."""
    # 只有 IP、端口状态和 VLAN 同时正确，才把模拟 VIP 判定为可达。
    reachable = (
        ip == VIP_IP
        and LAB_STATE["admin_state"] == "up"
        and LAB_STATE["oper_state"] == "up"
        and LAB_STATE["access_vlan"] == ACCESS_VLAN
    )

    return {
        "ip": ip,
        "reachable": reachable,
    }


@mcp.tool(
    annotations={
        "title": "Get Simulated Interface State",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def get_interface_state(interface: str) -> dict:
    """Return the administrative and operational interface state."""
    # 先验证接口，再返回当前内存状态；本函数不修改 LAB_STATE。
    validate_interface(interface)

    return {
        "interface": interface,
        "admin_state": LAB_STATE["admin_state"],
        "oper_state": LAB_STATE["oper_state"],
    }


@mcp.tool(
    annotations={
        "title": "Get Simulated Interface Configuration",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def get_interface_config(interface: str) -> dict:
    """Return the simulated running configuration for one interface."""
    validate_interface(interface)

    # 根据内存状态动态拼出类似 Cisco IOS 的接口配置文本。
    shutdown_command = (
        "shutdown"
        if LAB_STATE["admin_state"] == "administratively"
        else "no shutdown"
    )

    config = (
        f"interface {interface}\n"
        " switchport mode access\n"
        f" switchport access vlan {LAB_STATE['access_vlan']}\n"
        f" {shutdown_command}"
    )

    return {
        "interface": interface,
        "config": config,
    }


@mcp.tool(
    annotations={
        "title": "Get Simulated Running Configuration",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def get_running_config() -> dict:
    """Return a concise simulated switch running configuration."""
    # 复用单接口查询结果，避免在两个工具中重复生成接口配置。
    interface_result = get_interface_config(USER_PORT)

    return {
        "config": (
            "hostname MOCK-SW1\n"
            f"{interface_result['config']}\n"
            f"vlan {ACCESS_VLAN}\n"
            " name USERS"
        )
    }


@mcp.tool(
    annotations={
        "title": "Enable Simulated Interface",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def no_shutdown(interface: str) -> dict:
    """Enable the simulated interface and restore its link state."""
    validate_interface(interface)

    # 这里的“修复”只是改变 Python 字典，不会执行任何网络命令。
    LAB_STATE["admin_state"] = "up"
    LAB_STATE["oper_state"] = "up"

    return {
        "interface": interface,
        "action": "no shutdown",
        "status": "applied",
    }


@mcp.tool(
    annotations={
        "title": "Apply Simulated Configuration",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def apply_config(config_list: list[str]) -> dict:
    """Apply a limited list of commands to the simulated interface."""
    # 记录最近一次 interface 命令选择的接口，模拟 IOS 配置上下文。
    selected_interface = None

    # 严格使用允许列表：不在下面分支中的命令一律拒绝。
    for command in config_list:
        command = command.strip()

        if command.startswith("interface "):
            selected_interface = command.removeprefix("interface ").strip()
            validate_interface(selected_interface)

        elif command == "no shutdown":
            # 必须先进入正确的接口上下文，才能执行接口配置命令。
            if selected_interface != USER_PORT:
                return {
                    "status": "failed",
                    "error": "Select the simulated interface first.",
                }

            LAB_STATE["admin_state"] = "up"
            LAB_STATE["oper_state"] = "up"

        elif command == "shutdown":
            if selected_interface != USER_PORT:
                return {
                    "status": "failed",
                    "error": "Select the simulated interface first.",
                }

            LAB_STATE["admin_state"] = "administratively"
            LAB_STATE["oper_state"] = "down"

        elif command.startswith("switchport access vlan "):
            vlan_text = command.removeprefix(
                "switchport access vlan "
            ).strip()

            # 先验证为纯数字，再转换为 int 保存到模拟状态。
            if not vlan_text.isdigit():
                return {
                    "status": "failed",
                    "error": f"Invalid VLAN value: {vlan_text}",
                }

            LAB_STATE["access_vlan"] = int(vlan_text)

        elif command == "switchport mode access":
            continue

        else:
            return {
                "status": "failed",
                "error": f"Unsupported simulated command: {command}",
            }

    return {
        "status": "applied",
    }


if __name__ == "__main__":
    # 直接运行本文件时，默认在 http://127.0.0.1:8000/mcp 提供工具。
    mcp.run(transport="streamable-http")
