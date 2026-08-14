# 中文 Network Agent 的默认入口。
# 核心流程：调用 Ollama 分析 -> 解析模型返回的 JSON -> 调用 MCP 工具
# -> 把工具结果交还给模型 -> 直到模型给出最终结论。
import asyncio
import json
import re
import sys
import time
import textwrap
from string import Template
import requests
from datetime import datetime
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# 三个服务/模型配置：Agent 通过 HTTP 访问 Ollama，通过 MCP 访问网络工具。
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:e4b"
MCP_URL = "http://localhost:8000/mcp"

# 监控间隔控制两轮检查之间的等待时间；打印延迟只影响终端显示速度。
CHECK_INTERVAL = 30
PRINT_DELAY = 0.02  # seconds per character for slow printing

# 当前实验只监控一个 VIP、一个用户端口和一个 Access VLAN。
VIP_IP = "192.168.254.10"
USER_PORT = "Ethernet3/0"
ACCESS_VLAN = 100

# SYSTEM_PROMPT 相当于 Agent 的“排障操作手册”。
# Template 中的占位符会在末尾由真实实验参数替换；工具名和 JSON 字段必须保持英文。
SYSTEM_PROMPT = Template(textwrap.dedent("""\
    你是一个网络运维 AI Agent。你的任务是监控 VIP 端点，并在需要时采取修复操作。
    你也可以像初级网络工程师一样检查配置并提出修复建议。

    语言要求：
    - 必须使用简体中文进行思考和解释，包括推理过程，以及 reason、summary、prevention 和 confidence_basis 的字符串值。
    - VIP、MCP、接口名、VLAN、工具名、JSON 字段名、参数名、action 的机器值及工具返回字段必须保持下述英文原样。

    你可以通过 MCP Server 访问 Cisco IOS 交换机。MCP Server 充当连接桥梁：
    当你调用工具时，它会连接 Cisco IOS 交换机，并代表你执行相应的 CLI 命令。
    所有工具响应都包含交换机返回的实际输出。必须通过 JSON 工具调用使用这些工具。

    可用工具（必须使用准确的参数名）：
    - check_endpoint(ip: str) — 从交换机 Ping 指定 IP。返回 {"ip": str, "reachable": bool}。
    - get_interface_state(interface: str) — 查询接口的管理状态和运行状态。返回 {"interface": str, "admin_state": str, "oper_state": str}。
    - get_interface_config(interface: str) — 查询指定接口的 running-config。返回 {"interface": str, "config": str}。
    - get_running_config() — 查询交换机的完整 running-config。返回 {"config": str}。只需要查询一个接口时，优先使用 get_interface_config。
    - no_shutdown(interface: str) — 在接口上执行 "no shutdown"。返回 {"interface": str, "action": str, "status": str}。
    - apply_config(config_list: list) — 应用一组 IOS 配置命令。返回 {"status": str, "error": str if failed}。

    监控规则：
    1. 首先，必须使用 check_endpoint 检查 VIP $vip_ip 是否可达。
    2. 如果 VIP 可达，只返回：{"action": "none", "reason": "VIP 可达，无需执行操作。"}
    3. 如果 VIP 不可达，使用 get_interface_state 检查接口 $user_port 的状态。
    4. 如果 $user_port 的 admin_state 和 oper_state 都是 "down"，用户可能已经离开。
       只返回：{"action": "none", "reason": "用户端口 $user_port 为 down/down，用户可能已经离开。"}
    5. 如果 $user_port 不是 down/down 状态，则执行修复操作：
       - 首先，使用 get_interface_config 检查当前接口配置，确认已有配置。
       - 如果接口处于 administratively down 状态，使用 no_shutdown 启用接口。
       - 如果尚未配置 access vlan $access_vlan，使用 apply_config 应用该配置。
       - 如果在本步骤中执行了任何修复，必须再次使用 check_endpoint 验证 VIP 可达性。
         配置变更后，网络可能需要 10-15 秒重新收敛。可以再尝试调用 check_endpoint 2 次。
    6. 如果端口层面没有发现问题，则交换机整体配置可能存在问题。
       检查完整配置并对发现的问题发出告警，以便高级网络工程师审核修复建议。

    响应格式：
    调用读取数据的工具（check_endpoint、get_interface_state、get_interface_config、get_running_config）时，只返回 JSON：
    {"tool": "<tool_name>", "args": {<arguments>}}

    调用更改配置的工具（no_shutdown、apply_config）时，只返回 JSON：
    {"tool": "<tool_name>", "args": {<arguments>}, "confidence": <0-100>, "confidence_basis": "<用中文说明判断依据，限 1-2 句>"}
    置信度评分参考：
    - 90-100：工具结果提供了直接指向该修复操作的明确证据。
    - 70-89：证据指向性较强，但仍存在一些不确定性。
    - 50-69：根据有限数据作出的合理推测。
    - 低于 50：不确定，应考虑先收集更多数据。

    未执行任何配置变更并结束时，只返回 JSON：
    {"action": "none", "reason": "<中文解释>"}

    执行修复操作并结束时，只返回 JSON：
    {"action": "corrective", "reason": "<中文解释>", "summary": "<用中文说明故障和修复内容>", "prevention": "<中文预防建议>"}

    在选择下一工具或给出最终结论时，思考过程必须使用简体中文。
    除 JSON 外，不要在响应中包含任何其他文字。
""")).substitute(vip_ip=VIP_IP, user_port=USER_PORT, access_vlan=ACCESS_VLAN)


def slow_print(text: str, delay: float = PRINT_DELAY):
    """Print text character-by-character for readability."""
    # 这个函数只改善终端阅读体验，不参与故障判断或工具调用。
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def call_ollama(messages: list) -> tuple[str, str | None, float]:
    """Returns (content, thinking, elapsed_seconds) tuple."""
    # perf_counter 适合测量耗时，不受系统时间调整影响。
    start = time.perf_counter()
    resp = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False, "think": True},
        timeout=120,
    )
    elapsed = time.perf_counter() - start
    # 非 2xx HTTP 状态在这里转换为异常，由上层监控周期统一处理。
    resp.raise_for_status()
    msg = resp.json()["message"]
    # content 是模型最终输出；thinking 可能为空；elapsed 用于性能统计。
    return msg.get("content", ""), msg.get("thinking"), elapsed


def parse_json_response(text: str) -> dict:
    # Prompt 要求模型只返回 JSON，但模型偶尔仍会包一层 Markdown 代码块。
    text = text.strip()
    # 去掉 ```json ... ``` 或 ``` ... ``` 外壳。
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
        text = text.strip()
    # 优先按标准 JSON 直接解析，避免无必要修改模型输出。
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 兜底兼容模型偶发的多重大括号，例如 {{{...}}} -> {...}。
    text = re.sub(r'\{{3,}', '{', text)
    text = re.sub(r'\}{3,}', '}', text)
    return json.loads(text)


async def run_agent_cycle(client: Client, cycle: int):
    # 一个 cycle 是一轮完整的“检测—分析—调用工具—复测”闭环。
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*60}")
    print(f"[{timestamp}] 监控周期 #{cycle}")
    print(f"{'='*60}")

    # messages 保存本轮对话上下文，后续每次工具调用结果都会继续追加进去。
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"现在执行监控检查。首先检查 VIP {VIP_IP} 是否可达。"},
    ]

    # 分开统计模型和 MCP 的耗时，便于判断性能瓶颈在哪一层。
    cycle_start = time.perf_counter()
    total_llm_time = 0.0
    total_mcp_time = 0.0

    # 限制最多 10 步，防止模型反复调用工具形成无限循环。
    for step in range(10):  # max 10 tool calls per cycle
        print(f"\n--- 第 {step + 1} 步：请求 AI 分析 ---")
        ai_response, thinking, llm_elapsed = call_ollama(messages)
        total_llm_time += llm_elapsed
        print(f"  ⏱️  大模型响应耗时：{llm_elapsed:.2f} 秒")

        if thinking:
            print(f"\n  💭 AI 分析：")
            for line in thinking.strip().splitlines():
                slow_print(f"     {line}")

        print(f"\n  🤖 AI 响应：")
        slow_print(f"  {ai_response}")

        try:
            parsed = parse_json_response(ai_response)
        except (json.JSONDecodeError, ValueError):
            print(f"  ⚠️  无法解析 AI 响应，本轮监控结束。")
            break

        # 有 action 且没有 tool，表示模型不再调用工具，本轮可以结束。
        if "action" in parsed and "tool" not in parsed:
            action = parsed.get("action", "unknown")
            reason = parsed.get("reason", "未提供原因。")
            icon = "✅" if action == "none" else "🔧"
            slow_print(f"\n  {icon} 最终结论 [{action.upper()}]：{reason}")

            if action == "corrective":
                summary = parsed.get("summary")
                prevention = parsed.get("prevention")
                if summary:
                    slow_print(f"\n  📝 总结：{summary}")
                if prevention:
                    slow_print(f"  🛡️  预防建议：{prevention}")

            cycle_elapsed = time.perf_counter() - cycle_start
            print(f"\n  ⏱️  本轮耗时：")
            print(f"       总耗时：      {cycle_elapsed:.2f} 秒")
            print(f"       大模型耗时：  {total_llm_time:.2f} 秒 ({total_llm_time/cycle_elapsed*100:.0f}%)")
            print(f"       MCP 耗时：    {total_mcp_time:.2f} 秒 ({total_mcp_time/cycle_elapsed*100:.0f}%)")
            print(f"       其他开销：    {cycle_elapsed - total_llm_time - total_mcp_time:.2f} 秒")
            break

        # 没有最终 action 时，模型应该返回下一次要调用的 MCP 工具。
        tool_name = parsed.get("tool")
        tool_args = parsed.get("args", {})

        if not tool_name:
            print("  ⚠️  AI 响应中没有 tool 或 action，本轮监控结束。")
            break

        # apply_config 规定 args 应为字典；这里兼容模型偶尔直接返回列表的情况。
        if isinstance(tool_args, list) and tool_name == "apply_config":
            tool_args = {"config_list": tool_args}

        if isinstance(tool_args, dict):
            args_str = ", ".join(f"{k}={v!r}" for k, v in tool_args.items())
        else:
            args_str = repr(tool_args)
        print(f"\n  🔧 工具调用：{tool_name}({args_str})")

        # 置信度目前只用于展示，还不是阻止低置信度操作的审批门禁。
        confidence = parsed.get("confidence")
        confidence_basis = parsed.get("confidence_basis")
        if confidence is not None:
            bar_len = confidence // 5
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  🎯 置信度：{confidence}% [{bar}]")
            if confidence_basis:
                print(f"     判断依据：{confidence_basis}")
        # 真正的工具调用发生在这里；当前实验连接的是模拟 MCP Server。
        mcp_start = time.perf_counter()
        try:
            result = await client.call_tool(tool_name, tool_args)
            mcp_elapsed = time.perf_counter() - mcp_start
            total_mcp_time += mcp_elapsed
            result_text = str(result)
            print(f"  ⏱️  MCP 响应耗时：{mcp_elapsed:.2f} 秒")
            # 如果结果像 JSON，就按字段逐行显示；否则保留 FastMCP 的原始文本。
            try:
                result_obj = json.loads(result_text.replace("'", '"'))
                print(f"  📋 工具结果：")
                for k, v in result_obj.items():
                    slow_print(f"       {k}: {v}")
            except (json.JSONDecodeError, AttributeError):
                slow_print(f"  📋 工具结果：{result_text}")
        except Exception as e:
            mcp_elapsed = time.perf_counter() - mcp_start
            total_mcp_time += mcp_elapsed
            result_text = f"错误：{e}"
            print(f"  ⏱️  MCP 响应耗时：{mcp_elapsed:.2f} 秒")
            print(f"  ❌ 错误：{e}")

        # 把“模型决定”和“工具结果”都加入上下文，模型才能基于新证据选择下一步。
        messages.append({"role": "assistant", "content": ai_response})
        messages.append({"role": "user", "content": f"工具 {tool_name} 的返回结果：{result_text}\n\n请继续按照监控规则进行分析。"})


async def main():
    print(f"正在启动网络 Agent — 监控 VIP {VIP_IP}，每 {CHECK_INTERVAL} 秒检查一次")
    print(f"模型：{MODEL} | MCP：{MCP_URL}")

    # StreamableHttpTransport 通过 HTTP 连接独立运行的 MCP Server。
    client = Client(StreamableHttpTransport(MCP_URL))

    async with client:
        # 启动时先列出工具，可尽早发现 Server 未启动或工具注册不完整。
        tools = await client.list_tools()
        print(f"已连接 MCP。可用工具：{[t.name for t in tools]}")

        cycle = 1
        # while True:
        # 学习实验暂时只跑 5 轮；原来的 while True 被保留为持续监控参考。
        for _ in range(5):
            try:
                await run_agent_cycle(client, cycle)
            except Exception as e:
                print(f"\n监控周期 #{cycle} 出错：{e}")

            cycle += 1
            print(f"\n距离下次检查还有 {CHECK_INTERVAL} 秒……")
            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    # 只有直接运行本文件时才启动 Agent；被其他文件 import 时不会自动运行。
    asyncio.run(main())
