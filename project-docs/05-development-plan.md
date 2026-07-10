# 开发计划

## 开发原则

1. 先实现最小可运行闭环，再逐步扩展。
2. 服务端核心逻辑保持可测试。
3. REST API、WebSocket 协议和 Unity Bridge 使用统一数据模型。
4. 每个 Unity 实例必须独立管理进程、连接、状态、日志和结果。
5. 所有后续开发优先参考 `project-docs` 下的文档。

## 阶段 1：服务端基础框架

目标：搭建 Python 服务端项目骨架。

任务：

- 创建 `server` 目录。
- 创建 FastAPI 应用入口。
- 创建配置模块。
- 创建 REST 路由模块。
- 创建 WebSocket 路由模块。
- 创建协议模型。
- 创建实例状态枚举。
- 创建基础单元测试目录。

验收标准：

- 可以通过 `uvicorn app.main:app` 启动服务。
- 可以访问健康检查接口。
- 项目结构清晰，模块职责明确。

## 阶段 2：Unity 实例模型与管理器

目标：实现内存级多实例管理。

任务：

- 定义 `UnityInstance` 模型。
- 定义 `UnityLaunchOptions` 模型。
- 实现 `UnityInstanceManager`。
- 支持创建实例 ID。
- 支持查询实例列表。
- 支持查询指定实例。
- 支持更新实例状态。

验收标准：

- 可以通过 API 创建一个逻辑实例。
- 可以查询实例状态。
- 多个实例之间互不影响。

## 阶段 3：Unity 进程启动与停止

目标：实现服务端启动和停止 Unity。

任务：

- 实现 `UnityProcessLauncher`。
- 组装 Unity 启动参数。
- 支持 `-batchmode`。
- 支持 `-nographics`。
- 支持 `-projectPath`。
- 支持 `-executeMethod`。
- 传入 `instance_id` 和 `server_url`。
- 生成实例日志路径。
- 支持停止进程。

验收标准：

- 调用 `POST /api/unity/start` 后可以启动 Unity 进程。
- 实例记录正确的 `process_id`。
- 调用停止接口后可以停止 Unity 进程。

## 阶段 4：WebSocket 连接与握手

目标：实现 Unity 与服务端连接绑定。

任务：

- 实现 `/ws/unity` WebSocket 接口。
- 实现 `UnityConnectionRegistry`。
- Unity 连接后必须发送 `hello`。
- 服务端校验 `instance_id`。
- 绑定 `instance_id -> websocket`。
- 更新状态为 `connected`。
- 处理连接断开。

验收标准：

- Unity 连接后服务端能够识别对应实例。
- 实例状态可以从 `waiting_for_connection` 变为 `connected`。
- 连接断开后状态正确更新。

## 阶段 5：消息收发与进度上报

目标：实现双向消息通信。

任务：

- 定义统一消息模型。
- 处理 Unity 上报的 `progress`。
- 处理 Unity 上报的 `log`。
- 处理 Unity 上报的 `heartbeat`。
- 处理 Unity 上报的 `test_completed`。
- 处理 Unity 上报的 `test_failed`。
- 实现服务端向指定 Unity 下发消息。

验收标准：

- Unity 可以实时上报进度。
- 服务端可以保存最新进度。
- 服务端可以向指定 Unity 发送命令。
- 多个 Unity 实例消息不会串线。

## 阶段 6：Unity Bridge MVP

目标：实现 Unity 端最小连接客户端。

任务：

- 实现 `EntryPoint.cs`。
- 实现命令行参数解析。
- 实现 WebSocket 连接。
- 启动后发送 `hello`。
- 初始化完成后发送 `ready`。
- 支持发送进度和日志。
- 支持接收 `start_test`、`stop_test`、`shutdown`。

验收标准：

- Unity 在 batchmode 下启动后能够连接服务端。
- Unity 能够完成 hello 握手。
- Unity 能够向服务端上报进度。
- Unity 能够收到服务端命令。

## 阶段 7：超时、心跳与异常处理

目标：提高运行稳定性。

任务：

- 实现连接超时。
- 实现执行超时。
- 实现心跳超时。
- Unity 进程异常退出时更新状态。
- WebSocket 异常断开时更新状态。
- 保存错误信息。

验收标准：

- Unity 未按时连接时状态变为 `timeout`。
- Unity 长时间无心跳时状态变为 `timeout` 或 `disconnected`。
- Unity 进程异常退出时服务端能记录错误。

## 阶段 8：测试结果与运行产物

目标：规范测试结果输出。

任务：

- 每个实例创建独立运行目录。
- 保存 `unity.log`。
- 保存 `result.json`。
- 支持 artifacts 目录。
- API 支持查询结果。

验收标准：

- 每次运行都有独立目录。
- 测试完成后可以读取结果文件。
- CI 可以收集运行产物。

## 后续增强方向

- Web 管理页面。
- 数据库存储历史任务。
- 队列调度。
- 分布式 Agent。
- Docker 化部署。
- 测试报告 HTML 输出。
- Unity 包形式发布 Bridge。
- 与 GitLab CI / GitHub Actions / Jenkins 集成。

## 推荐开发顺序

1. 服务端项目骨架。
2. 协议模型。
3. 实例管理器。
4. REST API。
5. Unity 进程启动器。
6. WebSocket 握手。
7. 消息分发。
8. Unity Bridge。
9. 超时与异常处理。
10. 测试结果与产物管理。
