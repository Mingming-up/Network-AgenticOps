# Network-AgenticOps 项目成果说明

## 1. 项目结论

截至 2026-08-15，本项目已经在本机 CML-Free 隔离实验环境中跑通一个完整的网络故障处理闭环：

> 本地大模型发现 VIP 不可达，调用 MCP 工具检查交换机接口状态与配置，定位 `shutdown` 故障，执行白名单修复命令 `no shutdown`，再重新检测并确认 VIP 恢复可达。

这不是只修改 Python 变量的模拟结果。最终验收中的查询、配置和 Ping 均作用于 CML 中实际运行的 IOL-L2 虚拟交换机。

## 2. 项目目标

项目希望验证一个最小但完整的 Agentic Network Operations 场景：

1. 本地大模型根据实时网络状态作出下一步判断；
2. Agent 不直接拼接并执行任意网络命令，而是通过 MCP 调用明确的网络工具；
3. MCP Server 使用 Netmiko 连接隔离实验中的 Cisco IOS 节点；
4. 写操作受到接口和工具白名单限制；
5. 修复完成后必须重新检查业务端点，不能只以命令执行成功作为闭环终点。

## 3. 已验证架构

| 组件 | 当前实现 | 职责 |
|---|---|---|
| 本地模型 | Ollama + `gemma4:e4b` | 分析工具结果并选择下一步 MCP 工具 |
| 中文 Network Agent | `agent/network_agent_zh.py` | 维护诊断上下文、解析模型 JSON、调用工具并完成复测 |
| MCP Client | FastMCP Client | 将 Agent 的工具决策发送给 MCP Server |
| MCP Server | `mcp_server/mcp_server.py` | 暴露查询、检测和修复工具 |
| 网络连接 | Netmiko 4.6.0 + Cisco Breakout Tool | 将 Windows 本地连接转发到 CML 中的 SW1 控制台 |
| 虚拟网络 | CML-Free 2.10.0 + IOL-L2 XE 17.18.2 | 提供可被查询和配置的 Cisco IOS 实验节点 |
| 验证端点 | Alpine `VIP-HOST` | 使用 `192.168.254.10/24` 作为连通性检测目标 |

实际调用路径为：

1. 中文 Agent 请求本地 Ollama 模型作出工具选择；
2. Agent 通过 `http://127.0.0.1:8000/mcp` 调用 FastMCP Server；
3. MCP Server 使用 Netmiko 连接 `127.0.0.1:9000`；
4. Cisco Breakout Tool 将本地 9000 端口转发到 CML 实验中 SW1 的 `serial0`；
5. 工具在 SW1 上执行 IOS 查询、Ping 或受控配置命令；
6. 工具结果返回模型，直到模型给出最终结论。

## 4. 验收拓扑与参数

| 项目 | 已验证值 |
|---|---|
| CML 虚拟机 | `CML-Free-2.10.0` |
| CML 版本 | `2.10.0+build.13` |
| CML 当前管理地址 | `192.168.88.130`（VMware NAT/DHCP，重新启动后可能变化） |
| CML 实验名称 | `IOL-L2 Boot Test` |
| 交换机节点 | `SW1`，IOL L2 XE 17.18.02 |
| 验证端点 | `VIP-HOST`，Alpine Linux |
| 虚拟链路 | `SW1 Ethernet0/3` — `VIP-HOST eth0` |
| VLAN | VLAN 254，名称 `VIP-NET` |
| SVI | `Vlan254 = 192.168.254.1/24` |
| VIP | `192.168.254.10/24` |
| Breakout 映射 | `SW1 serial0 = telnet://127.0.0.1:9000` |
| MCP 地址 | `http://127.0.0.1:8000/mcp` |
| Ollama 地址 | `http://localhost:11434/api/chat` |

## 5. 已完成的真实闭环

最终验收过程如下：

1. 在 CML Workbench 中人工对 SW1 `Ethernet0/3` 执行临时 `shutdown`；
2. Agent 调用 `check_endpoint`，得到 `192.168.254.10 reachable=false`；
3. Agent 调用 `get_interface_state`，得到 `Ethernet0/3 administratively/down`；
4. Agent 调用 `get_interface_config`，确认接口配置包含 `shutdown`，同时 VLAN 254 已正确配置；
5. Agent 判断无需重新配置 VLAN，自主选择 `no_shutdown`；
6. 安全守卫确认目标为唯一授权接口 `Ethernet0/3` 后放行写操作；
7. MCP Server 经 Netmiko 在 SW1 上执行 `no shutdown`；
8. Agent 再次调用 `check_endpoint`，最终得到 `reachable=true`；
9. Agent 输出中文故障原因、修复操作和预防建议。

由此验证了以下关键能力：

- 模型能够根据连续返回的真实证据决定下一项检查；
- Agent 能区分接口关闭与 VLAN 配置缺失，不重复执行无必要的配置；
- MCP/Netmiko 能够读取并修改 CML 中的 IOS running-config；
- 修复成功以 VIP 恢复可达为准，而不是只检查 `no shutdown` 是否返回成功。

## 6. MCP 工具成果

当前 MCP Server 暴露以下工具：

| 工具 | 类型 | 用途 |
|---|---|---|
| `greet` | 只读 | 验证 MCP 基础连通性 |
| `check_endpoint` | 只读 | 由 SW1 Ping 指定 IP 并返回可达性 |
| `get_interface_state` | 只读 | 查询接口管理状态和协议状态 |
| `get_interface_config` | 只读 | 查询单一接口 running-config |
| `get_running_config` | 只读 | 查询完整 running-config |
| `no_shutdown` | 写操作 | 恢复指定接口 |
| `apply_config` | 写操作 | MCP Server 具备该通用工具，但当前真实验收 Agent 不允许调用 |

## 7. 当前安全边界

最终验收不是让模型任意修改交换机，而是采用了以下限制：

- 故障由用户在隔离实验中主动制造；
- 启动本次 Agent 即代表用户授权执行本轮受控恢复；
- Agent 必须先进行连通性、接口状态和接口配置检查；
- 当前只允许写工具 `no_shutdown`；
- 当前只允许目标接口 `Ethernet0/3`；
- `apply_config` 和针对其他接口的写请求会被 Agent 本地守卫阻止；
- Agent 只运行一个完整周期，避免无人值守重复修改配置；
- 故障制造阶段不执行 `write memory`，便于恢复正常基线；
- 工具执行后必须再次检测 VIP。

## 8. 实测数据

最终一次完整 Agent 验收的实测耗时为：

| 项目 | 耗时 | 占比 |
|---|---:|---:|
| 总耗时 | 539.16 秒 | 100% |
| 本地大模型 | 317.26 秒 | 59% |
| MCP 工具调用 | 38.78 秒 | 7% |
| 其他开销 | 183.12 秒 | 34% |

这是一轮本机实验的记录，不是性能基准。运行时间会受到模型加载状态、主机资源、模型每轮推理长度和二层链路收敛时间影响。

## 9. 中文适配成果

本项目只提供中文 Agent，入口为 `agent/network_agent_zh.py`。

已完成的中文适配包括终端提示、最终原因、修复总结和预防建议。MCP 工具名、JSON 字段名、接口名和机器状态值继续保持英文，避免破坏协议兼容性。

首次真实验收发现 `gemma4:e4b` 的原始 `thinking` 会在不同请求间出现中英文不稳定。当前代码已停止向终端展示原始 `thinking`，只展示可审计的工具决策、真实工具结果和中文最终结论；该修正不改变工具选择和修复逻辑。

## 10. 当前交付物

| 文件 | 作用 |
|---|---|
| `agent/network_agent_zh.py` | 中文 Agent 入口和真实验收安全守卫 |
| `mcp_server/mcp_server.py` | CML/Netmiko MCP Server |
| `simulation/mock_mcp_server.py` | 不启动 CML 时使用的模拟 MCP Server |
| `simulation/test_mock_mcp.py` | 模拟状态转换测试 |
| `PROJECT_RESULTS.md` | 已验证架构、闭环证据、安全边界和实测结果 |
| `REPRODUCTION_RUNBOOK.md` | 基于当前电脑环境重新运行闭环的操作手册 |

## 11. 当前范围

当前成果聚焦于一个可解释、可验证的最小故障闭环，范围为：

- 单个 CML 实验；
- 一台 IOL-L2 交换机；
- 一个用户端口；
- 一个 VLAN 和一个 VIP；
- 一种明确故障：接口被 `shutdown`；
- 一种受控修复：对指定接口执行 `no shutdown`。

项目尚未扩展为多设备并发监控、长期无人值守运行、通用配置修复平台或完整审批与回滚系统。这些能力不属于本次成果声明。
