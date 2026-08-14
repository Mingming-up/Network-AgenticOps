  <div align="center">

# 🤖🌐 Network-AgenticOps

**基于本地大模型、MCP 与网络自动化工具的故障诊断与自动修复实验**

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Gemma-black)
![MCP](https://img.shields.io/badge/MCP-FastMCP-7C3AED)
![Status](https://img.shields.io/badge/Status-Simulation_Passed-22C55E)

</div>

## 💡 这是一个什么项目？

本项目尝试让 Network Agent 根据网络状态自主分析故障、调用 MCP 工具执行修复，并在操作后重新验证网络是否恢复。

当前已经在 Python 模拟网络中跑通以下场景：

1. Agent 检测到 VIP 不可达；
2. Agent 查询端口状态和配置；
3. Agent 判断端口被 `shutdown`；
4. Agent 调用 `no_shutdown`；
5. Agent 再次检测并确认 VIP 恢复可达。

> 当前完成的是模拟软件闭环，不是 CML 虚拟网络闭环，也不代表具备生产网络自动运维能力。

## 🧩 当前架构

| 组件 | 当前职责 |
|---|---|
| Ollama + Gemma | 在本地完成故障分析和工具选择 |
| Network Agent | 维护诊断过程并处理模型响应 |
| FastMCP Client | 将 Agent 的决策转换为 MCP 工具调用 |
| 模拟 MCP Server | 执行查询或修复操作 |
| 模拟网络状态 | 保存端口、VLAN 和 VIP 的当前状态 |

模拟 MCP Server 提供以下工具：

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
- [ ] 部署 CML-Free
- [ ] 搭建 IOL-L2 最小虚拟网络
- [ ] 通过 Netmiko 接入 IOL-L2
- [ ] 完成 CML 虚拟网络故障闭环

## 🇨🇳 中文版 Agent

后续复现和功能实现默认使用：

```text
agent/network_agent_zh.py
```

该版本中文适配，已经通过模拟闭环验收。终端固定界面、AI 分析、故障原因、总结和预防建议均尽量使用中文；MCP Tool 名称、JSON 字段、参数名、返回字段以及 `none`、`corrective` 等机器值继续保持英文，确保工具协议兼容。

## 🛠️ 技术栈

| 模块 | 技术 | 作用 |
|---|---|---|
| 本地模型 | Ollama + Gemma | 分析网络状态并选择工具 |
| Agent | Python | 维护对话并执行诊断循环 |
| 工具协议 | MCP + FastMCP | 连接 Agent 与网络操作工具 |
| 设备连接 | Netmiko | 后续连接 CML 虚拟交换机 |
| 虚拟网络 | CML-Free + IOL-L2 | 后续构建隔离实验网络 |
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

### 5. 运行 Agent

测试会改变模拟状态。运行 Agent 前，请先重启模拟 MCP Server，恢复初始故障状态。

```powershell
python agent/network_agent_zh.py
```

当前验证仍然只使用模拟 MCP Server，尚未部署 CML-Free，也未连接真实 IOL-L2 或实体网络设备。

## 🗺️ 后续路线

后续只在 **CML-Free 虚拟网络** 中验证，不包含实体设备测试：

| 组件 | 后续职责 |
|---|---|
| Ollama | 运行本地模型 |
| Network Agent | 分析虚拟网络状态并选择工具 |
| MCP Server + Netmiko | 查询或配置指定的虚拟交换机 |
| CML-Free IOL-L2 | 提供隔离的 Cisco 虚拟交换机 |
| CML 虚拟终端 | 用于验证网络连通性 |

计划完成：

1. 部署 CML-Free；
2. 搭建一台 IOL-L2 和一台虚拟终端；
3. 手工验证端口关闭和恢复；
4. 使用 Netmiko 完成只读查询；
5. 将操作限制在指定虚拟设备和接口；
6. 完成故障检测、修复和复测；
7. 补充审批、日志、备份和回滚机制。
