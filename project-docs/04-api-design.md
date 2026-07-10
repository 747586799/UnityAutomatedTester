# API 设计

## 基础信息

默认服务地址：

```text
http://127.0.0.1:5100
```

默认 WebSocket 地址：

```text
ws://127.0.0.1:5100/ws/unity
```

## REST API

### 创建并启动 Unity 实例

```http
POST /api/unity/start
```

请求体：

```json
{
  "unity_executable": "C:/Program Files/Unity/Hub/Editor/2022.3.0f1/Editor/Unity.exe",
  "project_path": "D:/Projects/Game",
  "execute_method": "UnityAutomatedTester.EntryPoint.Run",
  "args": {
    "test_name": "SmokeTest"
  }
}
```

响应体：

```json
{
  "id": "unity-001",
  "state": "waiting_for_connection",
  "process_id": 12345,
  "project_path": "D:/Projects/Game"
}
```

## 查询实例列表

```http
GET /api/unity
```

响应体：

```json
[
  {
    "id": "unity-001",
    "state": "running",
    "process_id": 12345,
    "progress": 0.5
  }
]
```

## 查询指定实例

```http
GET /api/unity/{instance_id}
```

响应体：

```json
{
  "id": "unity-001",
  "state": "running",
  "process_id": 12345,
  "project_path": "D:/Projects/Game",
  "progress": 0.5,
  "last_heartbeat_time": "2026-07-07T10:01:00Z",
  "error_message": null
}
```

## 向指定 Unity 实例发送消息

```http
POST /api/unity/{instance_id}/message
```

请求体：

```json
{
  "type": "start_test",
  "payload": {
    "test_name": "SmokeTest",
    "scene": "Main"
  }
}
```

响应体：

```json
{
  "success": true,
  "message_id": "cmd-001"
}
```

## 停止指定 Unity 实例

```http
POST /api/unity/{instance_id}/stop
```

请求体：

```json
{
  "force": false
}
```

响应体：

```json
{
  "success": true,
  "id": "unity-001",
  "state": "stopped"
}
```

## 查询实例日志

```http
GET /api/unity/{instance_id}/logs
```

响应体：

```json
{
  "id": "unity-001",
  "logs": [
    {
      "timestamp": "2026-07-07T10:00:00Z",
      "level": "info",
      "message": "Test started"
    }
  ]
}
```

## 错误响应格式

```json
{
  "error": {
    "code": "instance_not_found",
    "message": "Unity instance not found",
    "details": {}
  }
}
```

## 常见错误码

| code | 说明 |
| --- | --- |
| instance_not_found | 实例不存在 |
| instance_not_connected | Unity 未连接 |
| invalid_message | 消息格式错误 |
| unity_launch_failed | Unity 启动失败 |
| process_stop_failed | 进程停止失败 |
| connection_timeout | Unity 连接超时 |
| execution_timeout | 测试执行超时 |
