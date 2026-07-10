# 通信协议设计

## 协议选择

Unity 与 Python 服务端之间使用 WebSocket + JSON 通信。

原因：

- 支持双向实时通信。
- 服务端可以主动向 Unity 下发命令。
- Unity 可以实时上报日志、进度和状态。
- JSON 易于调试和接入其他系统。

## WebSocket 地址

默认地址：

```text
ws://127.0.0.1:5100/ws/unity
```

## 基础消息结构

```json
{
  "id": "msg-001",
  "instance_id": "unity-001",
  "type": "progress",
  "timestamp": "2026-07-07T10:00:00Z",
  "payload": {}
}
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | string | 是 | 消息 ID |
| instance_id | string | 是 | Unity 实例 ID |
| type | string | 是 | 消息类型 |
| timestamp | string | 是 | ISO 8601 时间 |
| payload | object | 否 | 消息内容 |

## Unity 到服务端消息类型

### hello

Unity 连接后发送，用于绑定实例。

```json
{
  "id": "msg-001",
  "instance_id": "unity-001",
  "type": "hello",
  "timestamp": "2026-07-07T10:00:00Z",
  "payload": {
    "unity_version": "2022.3.0f1",
    "project_path": "D:/Projects/Game"
  }
}
```

### ready

Unity 初始化完成，可以接收命令。

```json
{
  "id": "msg-002",
  "instance_id": "unity-001",
  "type": "ready",
  "timestamp": "2026-07-07T10:00:03Z",
  "payload": {}
}
```

### progress

测试进度上报。

```json
{
  "id": "msg-003",
  "instance_id": "unity-001",
  "type": "progress",
  "timestamp": "2026-07-07T10:00:10Z",
  "payload": {
    "current": 30,
    "total": 100,
    "percent": 0.3,
    "message": "Loading scene"
  }
}
```

### log

日志上报。

```json
{
  "id": "msg-004",
  "instance_id": "unity-001",
  "type": "log",
  "timestamp": "2026-07-07T10:00:12Z",
  "payload": {
    "level": "info",
    "message": "Test started"
  }
}
```

### test_started

测试开始。

```json
{
  "id": "msg-005",
  "instance_id": "unity-001",
  "type": "test_started",
  "timestamp": "2026-07-07T10:00:15Z",
  "payload": {
    "test_name": "SmokeTest"
  }
}
```

### test_completed

测试完成。

```json
{
  "id": "msg-006",
  "instance_id": "unity-001",
  "type": "test_completed",
  "timestamp": "2026-07-07T10:02:00Z",
  "payload": {
    "success": true,
    "passed": 10,
    "failed": 0,
    "duration_seconds": 105
  }
}
```

### test_failed

测试失败。

```json
{
  "id": "msg-007",
  "instance_id": "unity-001",
  "type": "test_failed",
  "timestamp": "2026-07-07T10:02:00Z",
  "payload": {
    "error": "Assertion failed",
    "stack_trace": "..."
  }
}
```

### heartbeat

心跳。

```json
{
  "id": "msg-008",
  "instance_id": "unity-001",
  "type": "heartbeat",
  "timestamp": "2026-07-07T10:02:10Z",
  "payload": {}
}
```

## 服务端到 Unity 消息类型

### start_test

开始测试。

```json
{
  "id": "cmd-001",
  "instance_id": "unity-001",
  "type": "start_test",
  "timestamp": "2026-07-07T10:00:05Z",
  "payload": {
    "test_name": "SmokeTest",
    "scene": "Main"
  }
}
```

### stop_test

停止测试。

```json
{
  "id": "cmd-002",
  "instance_id": "unity-001",
  "type": "stop_test",
  "timestamp": "2026-07-07T10:01:00Z",
  "payload": {}
}
```

### execute

执行自定义命令。

```json
{
  "id": "cmd-003",
  "instance_id": "unity-001",
  "type": "execute",
  "timestamp": "2026-07-07T10:01:10Z",
  "payload": {
    "command": "load_scene",
    "args": {
      "scene": "Battle"
    }
  }
}
```

### shutdown

关闭 Unity。

```json
{
  "id": "cmd-004",
  "instance_id": "unity-001",
  "type": "shutdown",
  "timestamp": "2026-07-07T10:03:00Z",
  "payload": {}
}
```

## 握手流程

```text
1. 服务端启动 WebSocket 服务。
2. 服务端启动 Unity，并通过命令行传入 instance_id 和 server_url。
3. Unity 连接 WebSocket。
4. Unity 发送 hello。
5. 服务端校验 instance_id 是否存在。
6. 服务端绑定 instance_id 与 WebSocket。
7. 服务端将实例状态更新为 connected。
8. Unity 发送 ready。
9. 服务端下发 start_test 或等待外部命令。
```
