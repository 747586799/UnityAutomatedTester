# 中心 Server + 多 Agent 架构开发文档

## 目标

当前项目已经支持单机 Python Server 启动本机 Unity Editor，并通过 Unity Bridge 接收连接、进度、日志和测试结果。

为了支持多台电脑同时启动 Unity / Player，需要升级为：

```text
中心 Server + 每台执行机一个 Agent
```

目标能力：

1. 中心 Server 统一提供 Web UI。
2. 多台执行机运行 Agent 并连接中心 Server。
3. 用户可以在 Web UI 中选择某台 Agent 启动 Unity。
4. Agent 在本机启动 Unity Editor 或打包后的 Player exe。
5. Unity Bridge 仍然连接中心 Server，上报进度、日志、结果。
6. Server 能展示所有 Agent、所有 Unity 实例和测试状态。
7. 支持后续自动调度、并发限制、任务队列和分布式测试。

## 总体架构

```text
Browser Web UI
      |
      | HTTP
      v
Center Server
      |
      | WebSocket /ws/agent
      v
Agent-01 on PC-A
      |
      | local process
      v
Unity Editor / Game.exe
      |
      | WebSocket /ws/unity
      v
Center Server
```

多台机器时：

```text
                 ┌───────────── Agent-01 ───────────── Unity / Player
Browser ─ Server ├───────────── Agent-02 ───────────── Unity / Player
                 └───────────── Agent-03 ───────────── Unity / Player
```

## 职责划分

## Center Server 职责

中心 Server 负责：

1. 提供 Web UI。
2. 管理 Agent 注册表。
3. 管理 Unity 实例注册表。
4. 管理 WebSocket 连接。
5. 分发启动、停止、消息命令给 Agent。
6. 接收 Unity Bridge 的进度、日志、结果。
7. 展示所有 Agent 和实例状态。
8. 提供 REST API 给 Web UI 调用。

Server 不直接启动远程机器的进程。

## Agent 职责

每台执行机运行一个 Agent。

Agent 负责：

1. 连接中心 Server。
2. 注册自身信息。
3. 维护本机配置。
4. 接收 Server 下发的启动任务。
5. 在本机启动 Unity Editor 或 Player exe。
6. 停止本机进程。
7. 上报进程状态。
8. 上报本机资源和可用能力。

Agent 只管理本机进程，不直接提供 Web UI。

## Unity Bridge 职责

Unity Bridge 保持当前职责：

1. 读取命令行参数。
2. 连接中心 Server 的 `/ws/unity`。
3. 发送 `hello`、`ready`、`progress`、`log`、`test_completed`、`test_failed`。
4. 接收 Server 下发的消息。
5. 暴露统一测试 API 给业务测试代码。

Unity Bridge 不需要知道自己是由 Server 本机启动，还是由远程 Agent 启动。

## 推荐目录结构

```text
UnityAutomatedTester/
  server/
    app/
      agents/
        models.py
        registry.py
        dispatcher.py
        routes.py
        websocket.py
      core/
      api/
      websocket/
      web/

  agent/
    app/
      main.py
      config.py
      models.py
      launcher.py
      server_client.py
      process_registry.py
      runtime_workspace.py
    pyproject.toml
    agent.config.json

  unity_bridge/
  project-docs/
```

## Server 端模块设计

### agents/models.py

定义 Agent 相关模型。

```python
class AgentState(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    DISCONNECTED = "disconnected"

class AgentCapability(BaseModel):
    editor: bool = True
    player: bool = True
    unity_versions: list[str] = []
    projects: list[str] = []
    players: list[str] = []
    max_parallel: int = 1

class AgentInfo(BaseModel):
    agent_id: str
    hostname: str
    ip: str | None = None
    os: str
    state: AgentState
    running_count: int = 0
    capabilities: AgentCapability
    connected_time: datetime | None = None
    last_heartbeat_time: datetime | None = None
```

### agents/registry.py

维护 Agent 注册表。

```text
agent_id -> AgentInfo
agent_id -> WebSocket
```

职责：

- 注册 Agent。
- 更新 Agent 心跳。
- 移除 Agent 连接。
- 查询 Agent。
- 查询在线 Agent 列表。
- 判断 Agent 是否可用。

### agents/websocket.py

提供 Agent 连接入口：

```text
/ws/agent
```

连接流程：

1. Agent 建立 WebSocket 连接。
2. Agent 发送 `agent_hello`。
3. Server 注册 Agent。
4. Server 进入循环接收 Agent 消息。
5. 断开时 Agent 状态变为 `disconnected`。

### agents/dispatcher.py

Server 向 Agent 下发命令：

- `start_unity`
- `stop_unity`
- `ping`
- `shutdown_agent`

并处理 Agent 上报：

- `agent_hello`
- `agent_heartbeat`
- `start_result`
- `process_exited`
- `agent_log`

### agents/routes.py

REST API：

```text
GET  /api/agents
GET  /api/agents/{agent_id}
POST /api/agents/{agent_id}/start
POST /api/agents/{agent_id}/stop/{instance_id}
POST /api/agents/{agent_id}/ping
```

## Agent 端模块设计

### agent/app/config.py

Agent 本机配置。

配置文件示例：

```json
{
  "agent_id": "pc-001",
  "server_url": "ws://192.168.1.10:5100/ws/agent",
  "unity_server_url": "ws://192.168.1.10:5100/ws/unity",
  "unity_editors": {
    "6000.3.9f1": "D:/Tools/Unity/Editor/6000.3.9f1/Editor/Unity.exe"
  },
  "projects": {
    "Project-One": "D:/Documents/Git/Project-One/Unity/Project-One"
  },
  "players": {
    "Project-One": "D:/Builds/Project-One/Project-One.exe"
  },
  "max_parallel": 2,
  "workspace": "D:/UnityAutomatedTester/runtime"
}
```

### agent/app/server_client.py

Agent 连接中心 Server。

职责：

1. 建立 `/ws/agent` 连接。
2. 发送 `agent_hello`。
3. 定时发送 `agent_heartbeat`。
4. 接收 Server 命令。
5. 调用 launcher 启动/停止 Unity。
6. 上报启动结果和进程退出。
7. 断线后重连。

### agent/app/launcher.py

负责本机启动 Unity Editor 或 Player exe。

Editor 模式命令：

```text
Unity.exe
-batchmode
-nographics
-projectPath {project_path}
-executeMethod {execute_method}
-automatedTester.instanceId {instance_id}
-automatedTester.serverUrl {unity_server_url}
-automatedTester.agentId {agent_id}
-logFile {log_file}
-automatedTester.{key} {value}
```

Player 模式命令：

```text
Game.exe
-automatedTester.instanceId {instance_id}
-automatedTester.serverUrl {unity_server_url}
-automatedTester.agentId {agent_id}
-automatedTester.{key} {value}
```

### agent/app/process_registry.py

维护本机进程：

```text
instance_id -> Process
```

职责：

- 保存进程 ID。
- 查询进程状态。
- 停止进程。
- 监听进程退出。

## 通信协议

## Agent 到 Server

### agent_hello

```json
{
  "type": "agent_hello",
  "agent_id": "pc-001",
  "payload": {
    "hostname": "DESKTOP-01",
    "ip": "192.168.1.101",
    "os": "windows",
    "capabilities": {
      "editor": true,
      "player": true,
      "unity_versions": ["6000.3.9f1"],
      "projects": ["Project-One"],
      "players": ["Project-One"],
      "max_parallel": 2
    }
  }
}
```

### agent_heartbeat

```json
{
  "type": "agent_heartbeat",
  "agent_id": "pc-001",
  "payload": {
    "running_count": 1,
    "cpu_percent": 30.5,
    "memory_percent": 62.1
  }
}
```

### start_result

```json
{
  "type": "start_result",
  "agent_id": "pc-001",
  "instance_id": "unity-001",
  "payload": {
    "success": true,
    "process_id": 12345,
    "launch_command": ["Unity.exe", "-batchmode"]
  }
}
```

### process_exited

```json
{
  "type": "process_exited",
  "agent_id": "pc-001",
  "instance_id": "unity-001",
  "payload": {
    "exit_code": 0
  }
}
```

## Server 到 Agent

### start_unity

```json
{
  "type": "start_unity",
  "request_id": "req-001",
  "instance_id": "unity-001",
  "payload": {
    "mode": "editor",
    "unity_version": "6000.3.9f1",
    "project": "Project-One",
    "execute_method": "HotFix.Test.GameAutomatedTester.AutomatedTesterStart.BatchStartTest",
    "args": {
      "Account": "123456",
      "scene": "Assets/Scenes/Init.unity",
      "timeout": 60.5,
      "debug": true
    }
  }
}
```

### stop_unity

```json
{
  "type": "stop_unity",
  "request_id": "req-002",
  "instance_id": "unity-001",
  "payload": {
    "force": false
  }
}
```

## Unity 实例模型扩展

当前 UnityInstance 需要增加字段：

```text
agent_id
launch_target: local / agent
mode: editor / player
request_id
```

示例：

```python
class UnityInstance(BaseModel):
    id: str
    agent_id: str | None = None
    launch_target: str = "local"
    mode: str = "editor"
    process_id: int | None = None
    state: UnityInstanceState
    progress: float = 0.0
```

## 启动流程

## 指定 Agent 启动 Editor

```text
1. 用户在 Web UI 选择 Agent pc-001。
2. 用户点击启动 Unity。
3. Server 创建 instance_id。
4. Server 创建 UnityInstance，状态为 starting。
5. Server 通过 /ws/agent 向 pc-001 发送 start_unity。
6. Agent 根据本机配置拼接 Unity Editor 命令。
7. Agent 启动 Unity Editor。
8. Agent 上报 start_result。
9. Server 更新 process_id，状态为 waiting_for_connection。
10. Unity Bridge 连接 Server /ws/unity。
11. Server 收到 hello，绑定 instance_id。
12. Server 状态变为 connected/running。
13. Unity 上报 progress/log/result。
```

## 指定 Agent 启动 Player

```text
1. 用户选择 Agent pc-001。
2. 启动模式选择 player。
3. Server 向 Agent 发送 start_unity。
4. Agent 根据 players 配置找到 Game.exe。
5. Agent 启动 Game.exe 并传入 automatedTester 参数。
6. Player 启动后通过 Unity Bridge Runtime 入口连接 Server。
7. 后续流程与 Editor 一致。
```

## Agent 选择策略

第一阶段支持手动选择：

```text
agent_id: pc-001
```

后续支持自动选择：

```text
agent_id: auto
```

自动选择规则：

1. Agent 在线。
2. Agent 支持指定 mode。
3. Agent 支持指定 project。
4. Agent 当前运行数小于 `max_parallel`。
5. 优先选择 running_count 最少的 Agent。

## Web UI 扩展

### Agent 列表

新增页面区域：

```text
Agent ID | Hostname | IP | State | Running | Capabilities
pc-001   | DESKTOP1 | ...| online | 1/2     | editor/player
```

### 启动表单新增字段

```text
启动目标: local / agent
Agent: pc-001 / pc-002 / auto
模式: editor / player
Unity Version: 6000.3.9f1
Project: Project-One
Args: JSON
```

### 实例列表新增字段

```text
id
agent_id
mode
state
process_id
progress
```

## 错误处理

需要处理：

1. Agent 不在线。
2. Agent 不支持指定 Unity 版本。
3. Agent 不支持指定项目。
4. Agent 并发数已满。
5. Agent 启动进程失败。
6. Unity 未按时连接。
7. Agent 断线。
8. Unity 进程异常退出。

错误状态建议：

```text
agent_unavailable
agent_capacity_full
launch_failed
connection_timeout
process_exited
agent_disconnected
```

## 安全建议

第一阶段内网使用可以不加复杂认证，但需要预留：

1. Agent token。
2. Server 校验 agent_id + token。
3. Web UI 登录。
4. 禁止任意命令执行，只允许启动配置中的 Unity/Player。
5. Agent 只接受 Server 下发的结构化任务，不接受自由 shell 命令。

Agent 注册建议：

```json
{
  "agent_id": "pc-001",
  "token": "change-me"
}
```

## 开发计划

### 阶段 1：Server Agent 注册

目标：Server 能看到 Agent 在线。

任务：

- 新增 `server/app/agents` 模块。
- 实现 Agent 模型。
- 实现 Agent 注册表。
- 实现 `/ws/agent`。
- 实现 `GET /api/agents`。
- 实现 Agent 心跳。

验收：

- Agent 启动后 Server 能显示 online。
- Agent 断开后 Server 能显示 disconnected。

### 阶段 2：Agent 基础程序

目标：Agent 可以连接 Server 并注册。

任务：

- 新增 `agent` 项目。
- 实现 Agent 配置文件。
- 实现 WebSocket 客户端。
- 实现 `agent_hello`。
- 实现 `agent_heartbeat`。
- 实现断线重连。

验收：

- Agent 控制台显示已连接 Server。
- Server API 能查询到 Agent。

### 阶段 3：远程启动 Editor

目标：Server 可以命令 Agent 启动 Unity Editor。

任务：

- Server 实现向 Agent 下发 `start_unity`。
- Agent 实现 Editor 启动命令构建。
- Agent 上报 `start_result`。
- Unity Bridge 连接 Server。
- UnityInstance 增加 `agent_id`。

验收：

- Web UI 选择 Agent 后能启动该机器上的 Unity Editor。
- Server 能看到实例连接、进度和日志。

### 阶段 4：远程启动 Player

目标：支持启动打包后的 exe。

任务：

- Agent 配置 players。
- Agent 实现 Player 启动命令构建。
- Unity Bridge 增加 runtime 自动连接入口。
- Web UI 支持选择 editor/player。

验收：

- Web UI 可以启动指定 Agent 上的 Game.exe。
- Player 能连接 Server 并上报日志、进度和结果。

### 阶段 5：Web UI 多机管理

目标：Web UI 支持多 Agent 控制。

任务：

- Agent 列表。
- 启动表单增加 Agent 选择。
- 实例列表显示 agent_id。
- 支持自动选择 Agent。
- 支持 Agent 状态刷新。

验收：

- 可以从页面选择不同 Agent 启动任务。
- 多台机器实例同时显示在一个列表中。

## MVP 优先级

推荐先做：

1. `/ws/agent` 注册。
2. `GET /api/agents` 查询。
3. Agent 独立程序连接 Server。
4. Server 下发 start_unity。
5. Agent 启动 Editor。
6. Unity Bridge 连接 Server。
7. Web UI 显示 agent_id。

暂不做：

- 数据库持久化。
- 权限登录。
- 复杂任务队列。
- 自动 Agent 调度。
- Player 模式。

这些可在远程 Editor 启动闭环完成后继续迭代。
