# 架构设计

## 架构目标

项目采用 Python 服务端 + Unity C# Bridge 的架构。

Python 服务端负责：

- 对外提供 REST API。
- 启动和停止 Unity 进程。
- 管理多个 Unity 实例。
- 维护 Unity WebSocket 连接。
- 接收 Unity 上报消息。
- 向 Unity 下发命令。

Unity Bridge 负责：

- 读取命令行参数。
- 连接 Python WebSocket 服务。
- 执行测试入口。
- 上报日志、进度、状态和结果。
- 接收服务端命令。

## 系统组件

```text
External Client / CI
        |
        | REST API
        v
Python FastAPI Server
        |
        | start process
        v
Unity Editor Process
        |
        | WebSocket
        v
Python FastAPI Server
```

## 服务端模块划分

```text
server/app/
  main.py
  config.py

  api/
    unity_routes.py

  core/
    models.py
    states.py
    manager.py
    launcher.py
    registry.py
    dispatcher.py

  protocol/
    messages.py
    types.py

  websocket/
    unity_socket.py

  runtime/
    workspace.py
```

### main.py

应用入口。

职责：

- 创建 FastAPI 应用。
- 注册 REST 路由。
- 注册 WebSocket 路由。
- 初始化全局服务对象。

### config.py

配置定义。

职责：

- 服务监听地址与端口。
- 默认 Unity 可执行文件路径。
- 连接超时时间。
- 执行超时时间。
- 运行时目录。

### api/unity_routes.py

REST API 层。

职责：

- 创建 Unity 实例。
- 停止 Unity 实例。
- 查询 Unity 实例列表。
- 查询指定 Unity 实例。
- 向指定 Unity 实例发送消息。

### core/manager.py

核心实例管理器。

职责：

- 创建实例 ID。
- 管理实例状态。
- 调用 launcher 启动 Unity。
- 调用 registry 管理 WebSocket 连接。
- 调用 dispatcher 分发消息。

### core/launcher.py

Unity 进程启动器。

职责：

- 拼接 Unity 启动参数。
- 启动 Unity 进程。
- 记录进程 ID。
- 停止 Unity 进程。
- 处理进程退出码。

### core/registry.py

连接注册表。

职责：

- 维护 `instance_id -> websocket` 映射。
- 注册连接。
- 移除连接。
- 查询连接。

### core/dispatcher.py

消息分发器。

职责：

- 处理 Unity 上报消息。
- 将服务端命令发送给指定 Unity。
- 统一处理日志、进度、心跳和结果消息。

### protocol/messages.py

通信协议模型。

职责：

- 定义统一消息结构。
- 定义请求和响应模型。
- 保证 REST 和 WebSocket 的数据结构一致。

### websocket/unity_socket.py

WebSocket 接入层。

职责：

- 接受 Unity 连接。
- 读取 Unity 消息。
- 处理 `hello` 握手。
- 连接断开时通知 manager。

### runtime/workspace.py

运行时文件管理。

职责：

- 创建实例运行目录。
- 生成 Unity 日志路径。
- 保存结果文件。
- 管理 artifacts 目录。

## Unity 实例状态机

```text
created
  ↓
starting
  ↓
waiting_for_connection
  ↓
connected
  ↓
running
  ↓
completed / failed / timeout / stopped / disconnected
```

## UnityInstance 字段

```text
id
project_path
unity_executable
execute_method
process_id
state
start_time
connected_time
end_time
last_heartbeat_time
progress
log_file
result_file
exit_code
error_message
```

## 多实例管理原则

1. 每个 Unity 实例必须有唯一 `instance_id`。
2. 每个 Unity 实例拥有独立运行目录。
3. 每个 Unity 实例拥有独立日志文件。
4. WebSocket 连接必须通过 `hello` 消息绑定到实例。
5. 服务端向 Unity 发送消息时必须指定 `instance_id`。
6. Unity 进程退出、WebSocket 断开、心跳超时都要更新实例状态。

## 运行时目录

```text
runtime/
  instances/
    {instance_id}/
      unity.log
      server.log
      result.json
      artifacts/
```
