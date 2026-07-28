# UnityAutomatedTester

UnityAutomatedTester 是一个面向 Unity 项目的自动化测试调度与结果对比工具。项目由 Python FastAPI Server、桌面 Agent、Unity C# Bridge 和 Web 管理页面组成，用于批量启动 Unity、执行测试入口、收集日志与报告、归档历史记录，并支持多实例 Report / 战斗服日志对比。

## 项目作用

本项目主要解决以下问题：

- 自动启动 Unity Editor，并通过 `-batchmode`、`-nographics`、`-executeMethod` 执行测试入口。
- 管理多个 Unity 实例，支持本机启动和 Agent 分布式启动。
- 通过 WebSocket 接收 Unity 上报的状态、进度、日志、心跳和测试结果。
- 提供 Web 页面查看实例、Agent、自动任务、历史归档和对比结果。
- 支持自动任务定时运行、运行次数限制、任务模板保存和战斗服日志路径配置。
- 每次组任务结束后归档实例日志、Report、Result、Runtime 文件和对比摘要。
- 支持多个实例 Report 对比，以及客户端 Report 与服务端 BattleLog 对比。

## 技术栈

- Server：Python 3.11+、FastAPI、Uvicorn、Pydantic、asyncio
- Agent：Python 3.11+、Tkinter、websockets、Pydantic
- Unity Bridge：C#、Unity Editor、WebSocket
- 打包：PyInstaller

## 项目结构

```text
UnityAutomatedTester/
  agent/                         # Agent 桌面程序，用于远程机器启动 Unity
    app/
      main.py                    # Tkinter UI 入口
      config.py                  # agent.config.json 读写
      launcher.py                # Unity 进程启动逻辑
      server_client.py           # Agent 与 Server WebSocket 通信
      models.py                  # Agent 数据模型
    agent.config.json            # Agent 配置
    pyproject.toml               # Agent 依赖

  server/                        # FastAPI Server
    app/
      main.py                    # FastAPI 应用入口
      config.py                  # 环境变量配置
      dependencies.py            # 全局服务对象初始化
      agents/                    # Agent 注册、心跳、WebSocket 路由
      api/                       # Unity REST API
      automation/                # 自动任务、调度器、任务模板
      core/                      # Unity 实例管理、启动器、状态机、消息分发
      protocol/                  # Unity / Server 通信协议模型
      runtime/                   # 运行目录、历史归档、启动配置管理
      web/                       # Web 管理页面静态资源
      websocket/                 # Unity WebSocket 接入
    pyproject.toml               # Server 依赖

  unity_bridge/                  # Unity 侧 C# Bridge 脚本
    EntryPoint.cs                # Unity 自动化入口示例
    UnityTesterClient.cs         # WebSocket 客户端
    UnityAutomatedTestApi.cs     # 测试代码调用 API
    UnityProgressReporter.cs     # 进度上报
    CommandLineOptions.cs        # 命令行参数解析
    UnityBridgeManualTestWindow.cs

  runtime/                       # 运行时数据目录
    instances/                   # 运行中的实例文件，归档后清理
    history/groups/              # 组任务历史归档
    automation_tasks.json        # 自动任务持久化
    .automation_task_template.json
    .launch_config.json

  project-docs/                  # 项目设计文档
  build.py                       # 一键打包脚本
  README.md
```

## 快速启动 Server

进入 Server 目录：

```powershell
cd d:\Documents\Git\UnityAutomatedTester\server
```

安装依赖：

```powershell
pip install -e ".[dev]"
```

启动 Server：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 5100
```

如果需要局域网 Agent / Unity 访问，将 host 改为本机局域网 IP：

```powershell
python -m uvicorn app.main:app --host 192.168.1.15 --port 5100
```

访问地址：

```text
Web UI:    http://127.0.0.1:5100/
API Docs:  http://127.0.0.1:5100/docs
Health:    http://127.0.0.1:5100/health
Unity WS:  ws://127.0.0.1:5100/ws/unity
Agent WS:  ws://127.0.0.1:5100/ws/agent
```

## Server 环境变量

Server 支持通过环境变量配置运行参数：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `UAT_HOST` | `127.0.0.1` | Server 监听地址，也用于生成 Unity WebSocket URL |
| `UAT_PORT` | `5100` | Server 端口 |
| `UAT_RUNTIME_ROOT` | `../runtime` | 运行时数据目录 |
| `UAT_DEFAULT_UNITY_EXECUTABLE` | 空 | 本机启动 Unity 时的默认 Unity.exe 路径 |
| `UAT_CONNECTION_TIMEOUT_SECONDS` | `60` | 连接超时配置 |
| `UAT_EXECUTION_TIMEOUT_SECONDS` | `1800` | 执行超时配置 |
| `UAT_HEARTBEAT_TIMEOUT_SECONDS` | `30` | 心跳超时配置 |
| `UAT_BATTLE_LOG_ROOT` | 空 | 战斗服日志根目录 |

示例：

```powershell
$env:UAT_HOST = "192.168.1.15"
$env:UAT_PORT = "5100"
$env:UAT_BATTLE_LOG_ROOT = "D:\Documents\Git\Project-One\BattleServer\bin\Debug\net9.0\logs\Battle"
python -m uvicorn app.main:app --host $env:UAT_HOST --port $env:UAT_PORT
```

## 启动 Agent

Agent 用于在远程机器上注册可用 Unity 项目槽位，并接收 Server 的启动 / 停止命令。

进入 Agent 目录：

```powershell
cd d:\Documents\Git\UnityAutomatedTester\agent
```

安装依赖：

```powershell
pip install -e .
```

启动 Agent UI：

```powershell
python -m app.main
```

Agent UI 中需要配置：

- `Agent ID`：Agent 唯一标识，默认可使用本机 hostname。
- `Server Agent WS`：例如 `ws://192.168.1.15:5100/ws/agent`。
- `Unity Server WS`：例如 `ws://192.168.1.15:5100/ws/unity`。
- 项目实例：每个槽位包含 `project_id`、`unity_executable_path`、`project_path`。

保存配置后点击：

```text
连接 Server
同步项目实例
```

Server Web UI 的 Agent 页面会显示已连接 Agent 和可用项目槽位。

## 接入 Unity Bridge

将 `unity_bridge/` 下 C# 文件复制到 Unity 项目中，例如：

```text
YourUnityProject/
  Assets/
    UnityAutomatedTester/
      CommandLineOptions.cs
      EntryPoint.cs
      JsonMessageBuilder.cs
      UnityAutomatedTestApi.cs
      UnityAutomatedTestContext.cs
      UnityBridgeManualTestWindow.cs
      UnityProgressReporter.cs
      UnityTesterClient.cs
```

Unity 编译完成后，自动化入口通常使用：

```text
UnityAutomatedTester.EntryPoint.Run
```

Server / Agent 启动 Unity 时会传入参数：

```text
-batchmode
-nographics
-projectPath <project_path>
-executeMethod <execute_method>
-automatedTester.instanceId <instance_id>
-automatedTester.serverUrl <ws://server/ws/unity>
-logFile <runtime log path>
-automatedTester.<custom_key> <custom_value>
```

Unity 测试代码可通过 `UnityAutomatedTestApi` 获取自定义参数、上报日志和进度。

## Web UI 使用方式

启动 Server 后打开：

```text
http://127.0.0.1:5100/
```

主要页面能力：

| 页面 | 功能 |
|---|---|
| 实例 | 查看当前运行中的 Unity 组和实例，进入实例详情，发送 ping / start / stop / shutdown / 自定义消息 |
| Agent | 查看已连接 Agent 与项目槽位 |
| 自动任务 | 创建、启动、停止、删除自动任务；配置项目、执行方法、实例参数、运行间隔、最大运行次数、战斗服日志路径 |
| 历史 | 查看已归档组任务，查看实例历史、日志、结果、Report 对比和 BattleLog 对比 |

## 自动任务使用方式

1. 启动 Server。
2. 启动并连接至少一个 Agent。
3. 在 Agent 中配置项目槽位，例如 `project_id = Project-One`。
4. 打开 Web UI → 自动任务。
5. 创建任务并填写：
   - 任务名称
   - `project_id`
   - `execute_method`
   - 运行间隔
   - 最大运行次数
   - 实例列表与参数
   - 战斗服日志路径（可选）
6. 点击启动。

任务运行流程：

```text
自动任务调度器
  -> 查找空闲 Agent 项目槽位
  -> 下发 start_unity 命令
  -> Agent 启动 Unity
  -> Unity Bridge 连接 Server
  -> Unity 上报 ready / progress / result
  -> 所有实例结束后归档到 runtime/history/groups
  -> 自动任务进入下一轮等待或停止
```

## 历史归档与对比

组任务结束后会归档到：

```text
runtime/history/groups/{group_id}-{yyyyMMdd-HHmmss}/
  group.json
  instances/
    {instance_id}/
      archive.json
      report.txt
      result.json
      unity.log
    _battle_log.txt
```

归档内容包括：

- 实例基本信息和启动参数
- Unity 上报日志
- `report.txt`
- `result.json`
- `unity.log`
- `runtime/instances/{group_id}/{instance_id}` 中的其他文件
- Report SHA256 对比结果
- 战斗服日志匹配和对比结果

归档完成后会清理：

```text
runtime/instances/{group_id}
```

对比页面：

- `report-view.html`：查看单个实例 Report。
- `report-diff.html`：比较两个实例 Report，或比较实例 Report 与战斗服日志。
- 清洗模式会统一处理命名空间、动态 ID、版本号、数字格式和部分噪声行。

## 常用 API

### Unity / 实例

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/unity/launch-config` | 获取启动配置 |
| `POST` | `/api/unity/manual` | 注册手动 Unity 实例 |
| `POST` | `/api/unity/groups/start` | 启动 Unity 组任务 |
| `GET` | `/api/unity/groups` | 当前组列表 |
| `GET` | `/api/unity/groups/{group_id}` | 当前组详情 |
| `GET` | `/api/unity/{instance_id}` | 实例详情 |
| `POST` | `/api/unity/{instance_id}/message` | 发送消息到 Unity |
| `POST` | `/api/unity/{instance_id}/stop` | 停止实例 |
| `GET` | `/api/unity/{instance_id}/logs` | 实例日志 |

### 历史

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/unity/history/groups` | 分页查询组历史 |
| `DELETE` | `/api/unity/history/groups` | 批量删除组历史 |
| `GET` | `/api/unity/history/groups/{group_history_id}` | 组历史详情 |
| `GET` | `/api/unity/history/groups/{group_history_id}/compare-report` | Report 对比结果 |
| `GET` | `/api/unity/history/groups/{group_history_id}/instances/{instance_id}` | 历史实例详情 |

### 自动任务

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/automation/tasks` | 自动任务列表 |
| `GET` | `/api/automation/task-template` | 获取任务模板 |
| `POST` | `/api/automation/tasks` | 创建自动任务 |
| `GET` | `/api/automation/tasks/{task_id}` | 自动任务详情 |
| `PUT` | `/api/automation/tasks/{task_id}` | 更新自动任务 |
| `DELETE` | `/api/automation/tasks/{task_id}` | 删除自动任务 |
| `POST` | `/api/automation/tasks/{task_id}/start` | 启动自动任务 |
| `POST` | `/api/automation/tasks/{task_id}/stop` | 停止自动任务 |

### Agent

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/agents` | Agent 列表 |
| `GET` | `/api/agents/{agent_id}` | Agent 详情 |

## 手动 Unity 编辑器连接测试

用于验证 Unity Bridge 与 Server 的通信。

1. 启动 Server。
2. 注册手动实例：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:5100/api/unity/manual" `
  -ContentType "application/json" `
  -Body '{
    "instance_id": "manual-unity-001",
    "project_path": "manual-unity-editor"
  }'
```

3. Unity 菜单打开：

```text
Tools/Unity Automated Tester/Manual Test Window
```

4. 填写：

```text
Instance Id: manual-unity-001
Server Url:  ws://127.0.0.1:5100/ws/unity
```

5. 点击 `Connect`，随后可测试日志、进度、心跳、完成和失败消息。

## 打包方式

项目根目录提供一键打包脚本 [build.py](file:///d:/Documents/Git/UnityAutomatedTester/build.py)。

### 安装打包依赖

```powershell
pip install pyinstaller
```

### 打包 Server 和 Agent exe

在项目根目录执行：

```powershell
cd d:\Documents\Git\UnityAutomatedTester
python build.py
```

输出目录：

```text
dist/
  UnityAutomatedTester_Server_v{version}.exe
  UnityAutomatedTester_Agent_v{version}.exe
  agent.config.json
```

版本号默认来自：

```powershell
git describe --tags --always --dirty
```

也可以手动指定：

```powershell
python build.py --version 0.1.0
```

### 只复制源码，不打包 exe

```powershell
python build.py --no-exe
```

### 指定输出目录

```powershell
python build.py --out-dir ./my-dist
```

### 打包产物启动

Server：

```powershell
.\dist\UnityAutomatedTester_Server_v0.1.0.exe --host 192.168.1.15 --port 5100
```

Agent：

```powershell
.\dist\UnityAutomatedTester_Agent_v0.1.0.exe
```

Agent 打包后会优先读取 exe 同级目录的 `agent.config.json`，用户可直接编辑或通过 Agent UI 保存。

## 开发与验证

### Server 导入验证

```powershell
cd d:\Documents\Git\UnityAutomatedTester\server
python -c "from app.main import app; print('OK')"
```

### 运行测试

```powershell
cd d:\Documents\Git\UnityAutomatedTester\server
pytest
```

### 健康检查

```powershell
Invoke-RestMethod "http://127.0.0.1:5100/health"
```

## 常见问题

### Agent 连接不上 Server

检查：

1. Server 是否使用局域网 IP 启动，而不是只监听 `127.0.0.1`。
2. Agent 的 `Server Agent WS` 是否为 `ws://<server-ip>:5100/ws/agent`。
3. 防火墙是否允许端口 `5100`。
4. Server Web UI 的 Agent 页面是否显示 Agent。

### Unity 连接后马上断开

检查：

1. Unity Bridge 中的 `instance_id` 是否与 Server 下发一致。
2. `serverUrl` 是否为 `ws://<server-ip>:5100/ws/unity`。
3. Unity 项目是否包含最新 `unity_bridge` 脚本。
4. Unity Console 和 Server 控制台是否有异常日志。

### 战斗服日志没有参与对比

检查：

1. 自动任务是否配置了战斗服日志路径。
2. 或 Server 启动时是否设置了 `UAT_BATTLE_LOG_ROOT`。
3. Report 中是否能提取到 `RoomId`。
4. 战斗服日志目录下是否存在 `BattleLog_{RoomId}.log`。

### 历史里看不到运行时文件

归档成功后，`runtime/instances/{group_id}/{instance_id}` 下的文件会复制到：

```text
runtime/history/groups/{history_id}/instances/{instance_id}/
```

随后 `runtime/instances/{group_id}` 会被清理。如果归档目录缺少文件，优先检查 Unity 是否实际生成了对应文件。

## 开发文档

更多设计资料见：

- [01-project-overview.md](file:///d:/Documents/Git/UnityAutomatedTester/project-docs/01-project-overview.md)
- [02-architecture.md](file:///d:/Documents/Git/UnityAutomatedTester/project-docs/02-architecture.md)
- [03-protocol.md](file:///d:/Documents/Git/UnityAutomatedTester/project-docs/03-protocol.md)
- [04-api-design.md](file:///d:/Documents/Git/UnityAutomatedTester/project-docs/04-api-design.md)
- [05-development-plan.md](file:///d:/Documents/Git/UnityAutomatedTester/project-docs/05-development-plan.md)
- [06-web-ui-design.md](file:///d:/Documents/Git/UnityAutomatedTester/project-docs/06-web-ui-design.md)
- [07-server-agent-architecture.md](file:///d:/Documents/Git/UnityAutomatedTester/project-docs/07-server-agent-architecture.md)
