# Network-AgenticOps 现有环境复现手册

## 1. 手册用途

本手册用于在当前电脑已经准备好的环境中，重新运行一次以下闭环：

> 启动 CML 实验，启动 Breakout 和 MCP Server，人工制造 `Ethernet0/3 shutdown` 故障，再由本地模型 Agent 自动诊断、执行 `no shutdown` 并确认 VIP 恢复。

本手册不包含账号注册、软件下载、镜像下载、OVA 导入、参考平台安装、Python 依赖安装或 Ollama 模型下载。

## 2. 已有环境清单

开始前应已经具备：

- VMware Workstation 中的虚拟机 `CML-Free-2.10.0`；
- 已挂载的 CML-Free 参考平台 ISO；
- CML 实验 `IOL-L2 Boot Test`；
- 实验中的 `SW1`、`VIP-HOST` 和两者之间的链路；
- `D:\CML-Breakout\breakout-windows-amd64.exe`；
- 项目目录 `C:\Users\win10\Documents\ChatGPT\Network-AgenticOps`；
- 项目现有虚拟环境 `networkagent\.venv`；
- Ollama 和模型 `gemma4:e4b`。

如果上述任何项目不存在，本手册不负责重新安装，应回到完整部署记录处理。

## 3. 固定参数

| 参数 | 当前值 |
|---|---|
| CML 实验 | `IOL-L2 Boot Test` |
| SW1 接口 | `Ethernet0/3`，IOS 输出可能缩写为 `Et0/3` |
| VLAN | `254`，名称 `VIP-NET` |
| SW1 SVI | `192.168.254.1/24` |
| VIP-HOST | `192.168.254.10/24` |
| Breakout UI | `http://127.0.0.1:8080` |
| SW1 本地控制台 | `127.0.0.1:9000` |
| MCP Server | `http://127.0.0.1:8000/mcp` |
| Ollama API | `http://127.0.0.1:11434` |

> CML 管理地址来自 VMware NAT/DHCP。上次验收为 `192.168.88.130`，但重新开机后可能变化。每次以 VMware 控制台实际显示的地址为准。

## 4. 本次需要的窗口

建议按以下方式保留窗口，避免混淆：

| 窗口 | 用途 | 是否持续运行 |
|---|---|---|
| VMware Workstation | 运行 `CML-Free-2.10.0` | 是 |
| 浏览器 CML 页面 | 启动实验、打开 SW1/VIP-HOST 控制台、制造故障 | 是 |
| PowerShell A | 运行 Cisco Breakout Tool | 是 |
| PowerShell B | 运行真实 CML MCP Server | 是 |
| PowerShell C | 验证端口、检查 Ollama并运行中文 Agent | Agent 完成前保持 |
| 浏览器 Breakout UI | 启用实验的本地控制台映射 | 是 |

不要在正在运行服务的 PowerShell A 或 B 中继续输入其他命令。

## 5. 完整复现流程

### 步骤 1：启动 CML 虚拟机

1. 打开 VMware Workstation；
2. 选中 `CML-Free-2.10.0`；
3. 启动虚拟机；
4. 等待控制台出现 CML 登录提示和管理地址；
5. 记下本次实际管理地址。

上次验收地址为：

```text
https://192.168.88.130/
```

如果本次地址发生变化，后续 Breakout 的 `BREAKOUT_CONTROLLER` 也要改成新地址。

### 步骤 2：打开并启动 CML 实验

1. 在浏览器打开 VMware 控制台显示的 CML HTTPS 地址；
2. 使用当前 CML 应用账号登录；
3. 在 Dashboard 打开 `IOL-L2 Boot Test`；
4. 进入 Workbench 后选择 `LAB` → `Start Lab`；
5. 等待 `SW1` 和 `VIP-HOST` 都出现绿色运行标记。

正确拓扑应为：

| 节点 A | 接口 A | 节点 B | 接口 B |
|---|---|---|---|
| SW1 | Ethernet0/3 | VIP-HOST | eth0 |

### 步骤 3：恢复 VIP-HOST 的运行时地址

VIP-HOST 的 IPv4 地址是运行时配置，节点重新启动后可能消失。

1. 在 CML Workbench 打开 `VIP-HOST` 控制台；
2. 使用当前已知的实验节点登录信息登录；
3. 先检查地址：

```sh
ip addr show eth0
```

如果输出中已经存在 `192.168.254.10/24`，不要重复添加。如果不存在，执行：

```sh
sudo ip address add 192.168.254.10/24 dev eth0
sudo ip link set dev eth0 up
ip addr show eth0
```

验收标准：输出中出现以下内容：

```text
inet 192.168.254.10/24
```

### 步骤 4：检查 SW1 正常基线

在 CML Workbench 打开 `SW1` 控制台，按一次 Enter，然后执行：

```ios
enable
show vlan brief | include 254
show interfaces status | include Et0/3
show running-config interface Ethernet0/3
show ip interface brief | include Vlan254
ping 192.168.254.10
```

正常基线应满足：

- VLAN 254 为 `active`；
- `Et0/3` 为 `connected`，属于 VLAN 254；
- `Ethernet0/3` 配置包含 `switchport mode access` 和 `switchport access vlan 254`；
- 接口配置不包含 `shutdown`；
- `Vlan254` 地址为 `192.168.254.1`；
- Ping 最终成功。首次 Ping 可能因 ARP 学习丢失一个包，可以再执行一次。

如果 SW1 基线配置缺失，才执行下面的恢复配置：

```ios
configure terminal
vlan 254
 name VIP-NET
interface Ethernet0/3
 switchport mode access
 switchport access vlan 254
 no shutdown
interface Vlan254
 ip address 192.168.254.1 255.255.255.0
 no shutdown
end
write memory
```

恢复后重新执行本步骤的只读检查和 Ping。基线未通过时，不要继续启动自动修复实验。

### 步骤 5：启动 Cisco Breakout Tool

打开 **PowerShell A**，执行：

```powershell
Set-Location 'D:\CML-Breakout'

$env:BREAKOUT_CONTROLLER = 'https://192.168.88.130'
$cmlCredential = Get-Credential -UserName 'admin' -Message '请输入当前 CML 应用账号密码'
$env:BREAKOUT_USERNAME = $cmlCredential.UserName
$env:BREAKOUT_PASSWORD = $cmlCredential.GetNetworkCredential().Password

& '.\breakout-windows-amd64.exe' -listen 127.0.0.1 -noverify ui
```

注意：

- 如果 CML 地址已经变化，修改第一项地址；
- `Get-Credential` 会遮蔽密码，不要把密码直接写在命令中；
- `-noverify` 用于当前 CML 本地自签名 HTTPS 证书；
- `-listen 127.0.0.1` 只允许本机访问 Breakout UI；
- 启动后保持 PowerShell A 运行。

### 步骤 6：启用 Breakout 的 SW1 映射

1. 浏览器打开 `http://127.0.0.1:8080`；
2. 在 Labs 页面点击刷新；
3. 找到 `IOL-L2 Boot Test`；
4. 打开实验右侧的 Status 开关；
5. 点击实验名称进入详情；
6. 确认 SW1 的 `serial0` 已启用并映射到 `127.0.0.1:9000`；
7. VIP-HOST 的 `serial0` 和 VNC 本次不需要，可以保持关闭。

### 步骤 7：验证 SW1 本地端口

在 **PowerShell C** 执行：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 9000
```

验收标准：

```text
TcpTestSucceeded : True
```

如果为 False，不要启动 MCP Server，先处理 Breakout 映射问题。

### 步骤 8：启动真实 CML MCP Server

打开 **PowerShell B**，执行：

```powershell
Set-Location 'C:\Users\win10\Documents\ChatGPT\enterprise-AiOps'

$env:NETWORK_DEVICE_HOST = '127.0.0.1'
$env:NETWORK_DEVICE_PORT = '9000'
$env:NETWORK_DEVICE_TYPE = 'cisco_ios_telnet'
$env:NETWORK_DEVICE_USERNAME = 'cisco'
$env:NETWORK_DEVICE_SECRET = 'cisco'

& '.\networkagent\.venv\Scripts\python.exe' '.\mcp_server\mcp_server.py'
```

这里的 username/secret 是 Netmiko 连接无登录串口时所需的非空占位值，不是 CML Web 密码。

成功时应看到：

```text
Starting MCP server 'network-agent'
Uvicorn running on http://127.0.0.1:8000
```

保持 PowerShell B 运行。

在 PowerShell C 中验证端口：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8000
```

预期：

```text
TcpTestSucceeded : True
```

### 步骤 9：确认 Ollama 和模型可用

在 **PowerShell C** 执行：

```powershell
& 'C:\Users\win10\AppData\Local\Programs\Ollama\ollama.exe' list
& 'C:\Users\win10\AppData\Local\Programs\Ollama\ollama.exe' ps
```

`list` 中必须能看到：

```text
gemma4:e4b
```

`ps` 为空不一定是故障，模型可能尚未加载；只要 `list` 能正常返回且 Ollama 服务可访问即可。

### 步骤 10：人工制造本轮故障

回到 CML Workbench 的 `SW1` 控制台，执行：

```ios
enable
configure terminal
interface Ethernet0/3
shutdown
end
show interfaces status | include Et0/3
show running-config interface Ethernet0/3
ping 192.168.254.10
```

本步骤**不要执行 `write memory`**。

故障验收标准：

- `Et0/3` 显示 `disabled`；
- 接口配置中存在 `shutdown`；
- Ping 成功率为 0%。

只有在上述故障证据成立后，才运行 Agent。

### 步骤 11：运行中文 Agent

运行 Agent 代表你授权本轮程序仅对 `Ethernet0/3` 执行白名单修复 `no shutdown`。

在 **PowerShell C** 执行：

```powershell
Set-Location 'C:\Users\win10\Documents\ChatGPT\Network-AgenticOps'
& '.\networkagent\.venv\Scripts\python.exe' '.\agent\network_agent_zh.py'
```

当前代码只执行一个监控周期。运行期间不要关闭：

- VMware/CML；
- CML 实验；
- Breakout PowerShell A；
- MCP Server PowerShell B；
- Ollama 服务。

### 步骤 12：判断闭环是否成功

预期工具链依次产生以下证据：

1. `check_endpoint` 返回 `reachable=false`；
2. `get_interface_state` 返回 `administratively/down`；
3. `get_interface_config` 返回的配置包含 `shutdown` 和 VLAN 254；
4. Agent 调用 `no_shutdown`，返回 `status=applied`；
5. Agent 重新调用 `check_endpoint`；
6. 最终返回 `reachable=true`；
7. Agent 输出中文故障原因、修复操作和预防建议；
8. 进程自动返回 PowerShell 提示符。

接口恢复后，生成树和 ARP 可能需要 10–30 秒收敛。第一次复测为 False 不等于修复失败，Agent 会按规则继续复测。

以下结果才算完整成功：

```text
故障前：reachable=false
接口证据：administratively/down，并且配置含 shutdown
修复动作：no_shutdown(Ethernet0/3) = applied
修复后：reachable=true
最终 action：corrective
```

## 6. 安全边界说明

当前真实验收 Agent 内置以下保护：

- 只允许写工具 `no_shutdown`；
- 只允许接口 `Ethernet0/3`；
- `apply_config` 会被阻止；
- 其他接口的 `no_shutdown` 会被阻止；
- 每次启动只运行一个周期；
- 修复后必须复测 VIP。

如果终端出现以下提示，应停止并检查模型为什么请求了未授权操作，不要绕过守卫：

```text
已阻止未获授权的写工具调用
```

## 7. 实验结束后的检查与关闭

### 7.1 检查正常状态

在 SW1 控制台执行：

```ios
show interfaces status | include Et0/3
show running-config interface Ethernet0/3
ping 192.168.254.10
```

应看到：

- `Et0/3 connected 254`；
- 配置中没有 `shutdown`；
- Ping 成功。

本轮人工故障没有保存，正常基线此前已经保存，因此不需要再次执行 `write memory`。

### 7.2 按顺序关闭

按下面的顺序关闭，避免先关 CML 虚拟机后让 MCP、Breakout 继续连接一个已经消失的后端。

#### 第 1 步：确认 Agent 已结束

Agent 单周期运行完成后会自动回到 PowerShell 提示符。看到类似下面的提示符，就可以直接关闭运行 Agent 的 PowerShell 标签页：

```text
PS C:\Users\win10\Documents\ChatGPT\Network-AgenticOps>
```

如果 Agent 仍在输出监控步骤，先等待本周期结束；确需提前停止时按一次 `Ctrl+C`。

#### 第 2 步：停止 MCP Server

找到显示 FastMCP、`Uvicorn running on http://127.0.0.1:8000` 的 PowerShell B：

1. 按一次 `Ctrl+C`；
2. 等待它回到 PowerShell 提示符；
3. 再关闭这个 PowerShell 标签页。

不要直接关闭仍在运行的窗口，否则不容易区分服务是正常退出还是被强制中断。

#### 第 3 步：解除 Breakout 映射并停止 Breakout

1. 在浏览器打开 Breakout UI（`http://127.0.0.1:8080`）；
2. 回到 `LABS` 页面；
3. 关闭 `IOL-L2 Boot Test` 的 Status 开关；
4. 确认 SW1 的本地串口映射不再启用；
5. 找到显示 `Serving UI/API on http://127.0.0.1:8080` 的 PowerShell A，按一次 `Ctrl+C`；
6. 等待 PowerShell 提示符重新出现。

随后在 PowerShell A 清理仅对当前窗口有效的临时密码变量：

```powershell
Remove-Item Env:BREAKOUT_PASSWORD -ErrorAction SilentlyContinue
Remove-Variable cred,cmlCredential -ErrorAction SilentlyContinue
```

执行后即可关闭 PowerShell A 和 Breakout 浏览器标签页。

#### 第 4 步：停止 CML 实验

回到 CML Workbench：

1. 点击顶部 `LAB`；
2. 选择 `Stop Lab`；
3. 等待 SW1 和 VIP-HOST 的运行标记消失，再关闭 CML Workbench 标签页。

停止节点后，VIP-HOST 中通过运行时命令设置的 `192.168.254.10/24` 会消失，这是预期现象；下次启动实验时需要按本手册步骤重新设置。

#### 第 5 步：正常关闭 CML 虚拟机

在 VMware Workstation 中使用：

```text
虚拟机 → 电源 → 关闭客户机
```

等待 CML 控制台完全关机、VMware 显示虚拟机已关闭后，再退出 VMware Workstation。不要选择“关闭电源”，也不要在虚拟机仍运行时直接结束 VMware 进程。

#### 第 6 步：按需停止 Ollama

如果接下来不再使用本地模型，可在新的 PowerShell 中执行：

```powershell
& 'C:\Users\win10\AppData\Local\Programs\Ollama\ollama.exe' stop 'gemma4:e4b'
```

如需完全退出 Ollama，再从 Windows 托盘图标退出。只是暂时结束本次实验时，这一步可以跳过。

#### 关闭顺序速记

```text
Agent → MCP Server → Breakout 映射与进程 → CML Lab → CML 虚拟机 → Ollama（可选）
```

关闭 PowerShell A 也会清除该窗口中的临时环境变量。

## 8. 常见问题

### 8.1 CML 页面打不开

先查看 VMware 控制台中的本次管理地址，不要默认地址永远是 `192.168.88.130`。确认虚拟机仍在运行、网络适配器仍为 NAT、Windows 的 VMnet8 未被禁用。

### 8.2 Breakout UI 显示 `ERR_CONNECTION_REFUSED`

说明本机 8080 没有进程监听。查看 PowerShell A：

- 是否因未提供 CML 密码而退出；
- `BREAKOUT_CONTROLLER` 是否为本次实际 CML 地址；
- 是否仍能访问 CML 页面；
- 是否误关闭了 Breakout 进程。

### 8.3 `127.0.0.1:9000` 为 False

依次检查：

1. CML 实验和 SW1 是否运行；
2. Breakout 进程是否仍运行；
3. Breakout UI 中 `IOL-L2 Boot Test` 是否已启用；
4. SW1 的 `serial0` 是否启用；
5. 映射端口是否仍为 9000。

### 8.4 MCP Server 启动时报缺少环境变量

五个 `NETWORK_DEVICE_*` 环境变量必须在**启动 MCP Server 的同一个 PowerShell B** 中设置。其他窗口设置的临时环境变量不会自动传入 PowerShell B。

### 8.5 Agent 无法连接 MCP

执行：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8000
```

如果为 False，检查 PowerShell B 中 MCP Server 是否仍在运行。

### 8.6 Agent 无法连接 Ollama

执行：

```powershell
& 'C:\Users\win10\AppData\Local\Programs\Ollama\ollama.exe' list
```

如果命令无法返回，先恢复本机 Ollama 服务，再运行 Agent。

### 8.7 修复后第一次 Ping 仍失败

接口执行 `no shutdown` 后，二层转发和 ARP 可能仍在收敛。等待 10–30 秒再复测，不要重复执行配置命令。

### 8.8 终端仍出现英文内容

`check_endpoint`、`no_shutdown`、JSON 字段、接口状态等属于 MCP 协议和机器数据，保持英文是正常的。当前 Agent 已不再展示模型不稳定的原始 `thinking`，最终故障原因、总结和预防建议应为中文。

## 9. 最短检查清单

每次复现可按下面的顺序快速核对：

- [ ] CML 虚拟机已启动并记下当前管理地址；
- [ ] `IOL-L2 Boot Test` 已启动；
- [ ] VIP-HOST 具有 `192.168.254.10/24`；
- [ ] 正常基线下 SW1 能 Ping VIP；
- [ ] Breakout UI 已启动；
- [ ] SW1 `serial0` 已映射到 `127.0.0.1:9000`；
- [ ] TCP 9000 为 True；
- [ ] MCP Server 已监听 TCP 8000；
- [ ] Ollama 能看到 `gemma4:e4b`；
- [ ] 人工 `shutdown Ethernet0/3`，且 VIP Ping 失败；
- [ ] 运行中文 Agent；
- [ ] Agent 调用 `no_shutdown`；
- [ ] VIP 最终 `reachable=true`；
- [ ] 检查正常状态并按顺序关闭环境。
