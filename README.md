<h1 align="center">🤖 🌐 Network-AgenticOps-Lab</h1>

<p align="center">
  <strong>基于本地大模型、MCP 与网络自动化工具的故障诊断与受控修复实验</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Ollama-gemma4%3A4b-black">
  <img src="https://img.shields.io/badge/MCP-FastMCP-7C3AED">
  <img src="https://img.shields.io/badge/CML_Closed_Loop-Passed-22C55E">
</p>

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/52f59a7d-ccb8-4035-92e6-00b7927a45d2"
    alt="Network-AgenticOps-Lab"
    width="600">
</p>

</div>

## 💡 这是一个什么项目？

本项目让 Network Agent 根据网络状态自主分析故障、调用 MCP 工具执行受控修复，并在操作后重新验证网络是否恢复。

当前已经在本机 CML-Free 隔离实验环境中跑通以下真实虚拟设备闭环：

1. Agent 检测到 VIP `192.168.254.10` 不可达；
2. Agent 通过 MCP 查询 SW1 的接口状态和配置；
3. Agent 判断 `Ethernet0/3` 被 `shutdown`；
4. 安全守卫只放行 `no_shutdown(Ethernet0/3)`；
5. MCP Server 通过 Netmiko 和 Cisco Breakout Tool 修改 IOL-L2 running-config；
6. Agent 再次检测并确认 VIP 恢复可达。

> 查询、配置和 Ping 均作用于 CML 中实际运行的 IOL-L2 虚拟交换机，不是只修改 Python 状态变量；项目仍属于隔离实验，不可直接用于生产网络。

## 🧩 当前架构

| 组件 | 当前职责 |
|---|---|
| Ollama + Gemma | 在本地完成故障分析和工具选择 |
| 中文 Network Agent | 维护诊断过程、执行安全守卫并完成复测 |
| FastMCP Client / Server | 将 Agent 的决策转换为结构化工具调用 |
| MCP Server + Netmiko | 查询或配置 CML 中的 IOL-L2 虚拟交换机 |
| Cisco Breakout Tool | 将 Windows 本地端口映射到 CML 节点控制台 |
| Python 模拟环境 | 保留无 CML 时的 MCP 工具和状态转换自检 |

项目保留的模拟 MCP Server 提供以下工具：

- `check_endpoint`：检查 VIP 是否可达
- `get_interface_state`：查询端口状态
- `get_interface_config`：查询端口配置
- `get_running_config`：查询完整配置
- `no_shutdown`：恢复关闭的端口
- `apply_config`：执行受限的模拟配置

## ✅ 当前进度

- [x] 建立 Python 虚拟环境并安装依赖
- [x] 安装并验证 Ollama
- [x] 运行本地模型 `gemma4:e4b`
- [x] 验证 Agent 与 MCP Server 连接
- [x] 实现模拟 MCP Server
- [x] 验证端口故障状态转换
- [x] 完成 Agent 自动诊断、修复和复测
- [x] 完成中文适配版 Agent 并通过模拟闭环验收
- [x] 部署 CML-Free
- [x] 搭建 IOL-L2 最小虚拟网络
- [x] 通过 Cisco Breakout Tool 和 Netmiko 接入 IOL-L2
- [x] 完成 CML 虚拟网络故障闭环
- [x] 增加唯一写操作白名单和目标接口限制
- [x] 修正终端中英文不稳定显示
- [x] 补充项目成果说明和完整操作手册

## 🇨🇳 中文版 Agent

本项目唯一的 Agent 入口为：

```text
agent/network_agent_zh.py
```

该版本已经通过真实 CML/IOL-L2 闭环验收，当前实验参数为 `Ethernet0/3`、VLAN 254 和 VIP `192.168.254.10`。终端固定界面、故障原因、总结和预防建议使用中文；不再展示可能中英文混用的模型原始 `thinking`，但 MCP Tool 名称、JSON 字段、参数名和机器状态值继续保持英文，确保工具协议兼容。

## 🛠️ 技术栈

| 模块 | 技术 | 作用 |
|---|---|---|
| 本地模型 | Ollama + Gemma | 分析网络状态并选择工具 |
| Agent | Python | 维护对话并执行诊断循环 |
| 工具协议 | MCP + FastMCP | 连接 Agent 与网络操作工具 |
| 设备连接 | Netmiko + Cisco Breakout Tool | 连接 CML 虚拟交换机 |
| 虚拟网络 | CML-Free + IOL-L2 | 提供隔离实验网络 |
| 测试 | Pytest | 验证 MCP 工具和状态转换 |

## 🚀 快速运行

### 1. 安装

```powershell
git clone https://github.com/Mingming-up/Network-AgenticOps.git
cd Network-AgenticOps

python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. 准备模型

```powershell
ollama pull gemma4:e4b
ollama list
```

### 3. 启动模拟 MCP Server

```powershell
python simulation/mock_mcp_server.py
```

服务默认运行在：

```text
http://127.0.0.1:8000/mcp
```

### 4. 测试状态转换

在另一个 PowerShell 窗口运行：

```powershell
python -m pytest simulation/test_mock_mcp.py -v
```

### 5. 运行真实 CML 闭环

模拟测试使用独立的历史参数，只验证 MCP 工具和状态转换。真实 CML 闭环运行前，请先按照操作手册启动 CML、实验节点、Cisco Breakout Tool 和真实 MCP Server，并人工制造 `Ethernet0/3 shutdown` 故障。

```powershell
python agent/network_agent_zh.py
```

完整启动顺序、成功判定和安全关闭方法见 [操作手册](./REPRODUCTION_RUNBOOK.md)，实测证据与范围见 [项目成果说明](./PROJECT_RESULTS.md)。

## 🗺️ CML 闭环成果与范围

当前闭环只在 **CML-Free 虚拟网络** 中验证，不包含实体设备测试：

| 组件 | 当前职责 |
|---|---|
| Ollama | 运行本地模型 |
| Network Agent | 分析虚拟网络状态并选择工具 |
| MCP Server + Netmiko | 查询或配置指定的虚拟交换机 |
| CML-Free IOL-L2 | 提供隔离的 Cisco 虚拟交换机 |
| CML 虚拟终端 | 用于验证网络连通性 |

已经完成：

1. 部署 CML-Free；
2. 搭建一台 IOL-L2 和一台虚拟终端；
3. 手工验证端口关闭和恢复；
4. 使用 Netmiko 完成只读查询；
5. 将操作限制在指定虚拟设备和接口；
6. 完成故障检测、受控修复和复测。

当前尚未实现完整审批系统、持久化审计和自动回滚，不能直接用于生产网络。

## 📚 项目文档

- [项目成果说明](./PROJECT_RESULTS.md)：已验证架构、真实闭环证据、安全边界和实测结果；
- [操作手册](./REPRODUCTION_RUNBOOK.md)：基于当前 Windows/CML 环境重新运行和安全关闭闭环。
