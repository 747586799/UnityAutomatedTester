# UnityAutomatedTester 项目总览

## 项目定位

UnityAutomatedTester 是一个用于 Unity 项目的自动化测试调度服务。服务端使用 Python 实现，负责自动启动 Unity、管理多个 Unity 实例、接收 Unity 上报的测试进度与日志，并向指定 Unity 实例发送测试命令或自定义消息。

## 核心目标

1. 自动启动 Unity 进程，支持 `-batchmode` 与 `-nographics`。
2. 启动本地 HTTP/WebSocket 服务，等待 Unity 连接。
3. 使用 `instance_id` 区分和管理多个 Unity 实例。
4. 实时接收 Unity 上报的状态、进度、日志和测试结果。
5. 支持服务端向指定 Unity 实例发送命令。
6. 支持测试任务生命周期管理。
7. 支持后续接入 CI/CD、测试报告、管理后台和分布式执行。

## 推荐技术栈

### 服务端

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- asyncio
- subprocess / asyncio subprocess

### Unity 端

- C#
- WebSocket 客户端
- Unity Editor batchmode 执行入口

## 总体结构

```text
UnityAutomatedTester/
  server/
    app/
      main.py
      config.py
      api/
      core/
      protocol/
      websocket/
      runtime/
    tests/
    pyproject.toml

  unity_bridge/
    EntryPoint.cs
    UnityTesterClient.cs
    CommandLineOptions.cs
    UnityProgressReporter.cs

  runtime/
    instances/

  project-docs/
```

## 第一阶段 MVP 范围

第一阶段只实现核心闭环：

1. Python FastAPI 服务启动。
2. REST API 创建 Unity 实例。
3. 服务端启动 Unity 进程。
4. Unity 通过 WebSocket 连接服务端。
5. Unity 发送 `hello` 绑定实例。
6. 服务端记录实例状态。
7. Unity 上报进度、日志和结果。
8. 服务端向指定 Unity 实例发送消息。
9. 服务端停止指定 Unity 实例。

## 暂不实现内容

第一阶段暂不实现：

- Web 管理后台
- 用户权限系统
- 数据库存储
- 分布式调度
- 复杂测试报告
- 测试历史查询

这些功能可以在核心闭环稳定后迭代。
