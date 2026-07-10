# UnityAutomatedTester

UnityAutomatedTester 是一个 Unity 自动化测试调度项目。Python 服务端负责启动和管理 Unity 实例，Unity Bridge 负责连接服务端、上报进度、日志和测试结果。

## 项目结构

```text
UnityAutomatedTester/
  server/                 # Python FastAPI 服务端
  unity_bridge/           # Unity C# Bridge 脚本
  runtime/instances/      # 运行时实例日志和结果目录
  project-docs/           # 项目设计和开发计划文档
```

## 启动 Python 服务端

进入服务端目录：

```powershell
cd d:\Documents\Git\UnityAutomatedTester\server
```

安装依赖：

```powershell
pip install -e ".[dev]"
```

启动服务：

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 5100
```

服务地址：

```text
HTTP:      http://127.0.0.1:5100
WebSocket: ws://127.0.0.1:5100/ws/unity
Docs:      http://127.0.0.1:5100/docs
```

健康检查：

```powershell
Invoke-RestMethod "http://127.0.0.1:5100/health"
```

## Unity 编辑器手动连接测试流程

该流程用于 Unity 已经打开时测试双方连接、日志、进度和消息收发。

### 1. 将 Unity Bridge 脚本放入 Unity 项目

把本仓库的 `unity_bridge` 目录下脚本复制到 Unity 项目，例如：

```text
YourUnityProject/
  Assets/
    UnityAutomatedTester/
      CommandLineOptions.cs
      EntryPoint.cs
      JsonMessageBuilder.cs
      UnityBridgeManualTestWindow.cs
      UnityProgressReporter.cs
      UnityTesterClient.cs
```

等待 Unity 编译完成。

### 2. 启动 Python 服务端

```powershell
cd d:\Documents\Git\UnityAutomatedTester\server
uvicorn app.main:app --host 127.0.0.1 --port 5100
```

### 3. 注册手动测试实例

手动测试时，Unity 不是由服务端启动的，所以需要先在服务端注册一个等待连接的实例。

PowerShell：

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

成功后会返回类似：

```json
{
  "id": "manual-unity-001",
  "project_path": "manual-unity-editor",
  "execute_method": "manual-editor-connection",
  "process_id": null,
  "state": "waiting_for_connection"
}
```

也可以打开 Swagger 页面执行：

```text
http://127.0.0.1:5100/docs
```

选择：

```text
POST /api/unity/manual
```

请求体：

```json
{
  "instance_id": "manual-unity-001",
  "project_path": "manual-unity-editor"
}
```

### 4. 在 Unity 中打开测试窗口

Unity 菜单：

```text
Tools/Unity Automated Tester/Manual Test Window
```

填写：

```text
Instance Id: manual-unity-001
Server Url: ws://127.0.0.1:5100/ws/unity
```

点击：

```text
Connect
```

Python 服务端控制台应看到类似日志：

```text
Unity connected: instance_id=manual-unity-001
Unity message received: instance_id=manual-unity-001 type=hello payload=...
Unity message received: instance_id=manual-unity-001 type=ready payload={}
```

Unity Console 应看到类似日志：

```text
UnityAutomatedTester sent message: ... hello ...
UnityAutomatedTester sent message: ... ready ...
UnityAutomatedTester manual test connected: manual-unity-001
```

### 5. 测试消息发送

在 Unity 测试窗口点击：

```text
Send Log
Send Progress
Send Heartbeat
Send Test Started
Send Test Completed
Send Test Failed
```

Python 服务端控制台应输出收到的消息：

```text
Unity message received: instance_id=manual-unity-001 type=log payload=...
Unity message received: instance_id=manual-unity-001 type=progress payload=...
Unity message received: instance_id=manual-unity-001 type=heartbeat payload={}
```

Unity Console 应输出发送日志：

```text
UnityAutomatedTester sent message: ...
UnityAutomatedTester manual test sent log: Hello from Unity Editor
UnityAutomatedTester manual test sent progress: 1/10 Manual progress
UnityAutomatedTester manual test sent heartbeat.
```

### 6. 查询服务端状态

查询实例：

```powershell
Invoke-RestMethod "http://127.0.0.1:5100/api/unity/manual-unity-001"
```

查询实例列表：

```powershell
Invoke-RestMethod "http://127.0.0.1:5100/api/unity"
```

查询 Unity 上报日志：

```powershell
Invoke-RestMethod "http://127.0.0.1:5100/api/unity/manual-unity-001/logs"
```

### 7. 从服务端向 Unity 发送消息

向 Unity 发送普通命令：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:5100/api/unity/manual-unity-001/message" `
  -ContentType "application/json" `
  -Body '{
    "type": "custom_command",
    "payload": {
      "message": "hello unity"
    }
  }'
```

Unity Console 应看到：

```text
UnityAutomatedTester received command: ...
```

发送关闭命令：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:5100/api/unity/manual-unity-001/message" `
  -ContentType "application/json" `
  -Body '{
    "type": "shutdown",
    "payload": {}
  }'
```

当前 `shutdown` 会让 Unity 编辑器退出，手动测试时谨慎使用。

## 服务端启动 Unity 的自动测试流程

该流程用于验证服务端自动启动 Unity，并通过 `-executeMethod` 执行 Unity Bridge。

### 1. 确保 Unity 项目包含 Bridge 脚本

Unity 项目中需要存在：

```text
Assets/UnityAutomatedTester/EntryPoint.cs
Assets/UnityAutomatedTester/CommandLineOptions.cs
Assets/UnityAutomatedTester/UnityTesterClient.cs
Assets/UnityAutomatedTester/UnityProgressReporter.cs
Assets/UnityAutomatedTester/JsonMessageBuilder.cs
```

### 2. 启动 Python 服务端

```powershell
cd d:\Documents\Git\UnityAutomatedTester\server
uvicorn app.main:app --host 127.0.0.1 --port 5100
```

### 3. 请求服务端启动 Unity

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:5100/api/unity/start" `
  -ContentType "application/json" `
  -Body '{
    "unity_executable": "C:/Program Files/Unity/Hub/Editor/2022.3.0f1/Editor/Unity.exe",
    "project_path": "D:/Projects/YourUnityProject",
    "execute_method": "UnityAutomatedTester.EntryPoint.Run",
    "args": {
      "test_name": "SmokeTest",
      "scene": "Main",
      "repeat": 3,
      "timeout": 60.5,
      "debug": true
    }
  }'
```

需要替换：

```text
unity_executable: 你的 Unity.exe 路径
project_path:     你的 Unity 项目路径
```

服务端会自动传入：

```text
-batchmode
-nographics
-projectPath
-executeMethod
-automatedTester.instanceId
-automatedTester.serverUrl
-logFile
-automatedTester.test_name SmokeTest
-automatedTester.scene Main
-automatedTester.repeat 3
-automatedTester.timeout 60.5
-automatedTester.debug true
```

自定义键值对来自请求体的 `args`。key 只允许字母、数字、下划线、点、横线，且不能使用保留 key：

```text
instanceId
serverUrl
```

服务端返回的实例详情中会包含：

```text
args
launch_command
```

可以通过实例查询接口查看实际启动命令：

```powershell
Invoke-RestMethod "http://127.0.0.1:5100/api/unity/{instance_id}"
```

### 4. Unity 中读取自定义键值对

自动启动后，Unity Bridge 会把 `args` 解析到 `UnityAutomatedTestContext.Options.Args`。

业务测试代码推荐使用统一 API：

```csharp
var testName = UnityAutomatedTestApi.GetArg("test_name", "DefaultTest");
var scene = UnityAutomatedTestApi.GetArg("scene", "Main");
var repeat = UnityAutomatedTestApi.GetIntArg("repeat", 1);
var timeout = UnityAutomatedTestApi.GetFloatArg("timeout", 30f);
var debug = UnityAutomatedTestApi.GetBoolArg("debug", false);

await UnityAutomatedTestApi.LogInfoAsync("test_name=" + testName + ", scene=" + scene);
await UnityAutomatedTestApi.ProgressAsync(1, repeat, "custom args loaded");
```

也可以直接访问：

```csharp
var rawArgs = UnityAutomatedTestContext.Options.Args;
```

Unity Bridge 启动后会自动发送：

```text
hello
ready
test_started
progress
test_completed
```

## 常见问题

### 连接成功但点击按钮没有日志

确认使用的是最新 Bridge 脚本，尤其是：

```text
UnityTesterClient.cs
UnityBridgeManualTestWindow.cs
```

然后重启 Python 服务端，并重新打开 Unity 测试窗口。

也可以直接查询服务端内存日志：

```powershell
Invoke-RestMethod "http://127.0.0.1:5100/api/unity/manual-unity-001/logs"
```

### Unity 连接后马上断开

常见原因：

1. 没有先调用 `POST /api/unity/manual` 注册相同的 `instance_id`。
2. Unity 测试窗口中的 `Instance Id` 与服务端注册的不一致。
3. Unity 测试窗口中的 `Server Url` 填错。
4. Python 服务端没有运行或端口不是 `5100`。

### 发送 shutdown 后 Unity 退出

这是当前设计行为。手动测试时如果只想验证消息收发，不要发送 `shutdown`。

## 开发文档

更多设计信息见：

- `project-docs/01-project-overview.md`
- `project-docs/02-architecture.md`
- `project-docs/03-protocol.md`
- `project-docs/04-api-design.md`
- `project-docs/05-development-plan.md`
- `project-docs/06-web-ui-design.md`
- `project-docs/07-server-agent-architecture.md`
