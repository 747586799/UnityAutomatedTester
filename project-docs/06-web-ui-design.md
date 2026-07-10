# 网页界面设计文档

## 目标

为 UnityAutomatedTester 提供一个轻量网页界面。服务启动后，用户可以通过浏览器完成以下操作：

1. 查看当前 Unity 实例列表。
2. 查看每个 Unity 实例的连接状态、进度、日志和结果。
3. 使用固定启动参数快速启动 Unity。
4. 输入可选自定义 `args` 键值对。
5. 向指定 Unity 实例发送消息。
6. 停止指定 Unity 实例。

## 页面入口

推荐由 FastAPI 直接提供静态页面：

```text
http://127.0.0.1:5100/
```

API 文档仍保留：

```text
http://127.0.0.1:5100/docs
```

## 技术方案

第一阶段采用最小依赖方案：

```text
FastAPI StaticFiles + 原生 HTML + CSS + JavaScript fetch
```

不引入 React/Vue，避免过早增加构建链路。

推荐目录：

```text
server/
  app/
    main.py
    web/
      index.html
      styles.css
      app.js
```

FastAPI 挂载方式：

```python
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="app/web", html=True), name="web")
```

注意：API 路由应先注册，再挂载静态目录。

## 固定启动参数

网页启动 Unity 时固定使用以下参数：

```json
{
  "unity_executable": "D:/Tools/Unity/Editor/6000.3.9f1/Editor/Unity.exe",
  "project_path": "D:/Documents/Git/Project-One/Unity/Project-One",
  "execute_method": "HotFix.Test.GameAutomatedTester.AutomatedTesterStart.BatchStartTest"
}
```

这三项在第一版界面中默认写死，也可以显示为只读文本，方便用户确认。

## 可选输入参数 args

网页提供可编辑键值对区域，默认值：

```json
{
  "Account": "123456",
  "timeout": 60.5,
  "debug": true,
  "scene": "Assets/Scenes/Init.unity"
}
```

最终请求体：

```json
{
  "unity_executable": "D:/Tools/Unity/Editor/6000.3.9f1/Editor/Unity.exe",
  "project_path": "D:/Documents/Git/Project-One/Unity/Project-One",
  "execute_method": "HotFix.Test.GameAutomatedTester.AutomatedTesterStart.BatchStartTest",
  "args": {
    "Account": "123456",
    "timeout": 60.5,
    "debug": true,
    "scene": "Assets/Scenes/Init.unity"
  }
}
```

## 页面布局

### 1. 顶部状态区

显示服务基础信息：

```text
UnityAutomatedTester
Server: http://127.0.0.1:5100
WebSocket: ws://127.0.0.1:5100/ws/unity
Health: ok / error
```

按钮：

```text
刷新状态
刷新实例列表
```

### 2. 启动 Unity 表单

字段：

| 字段 | 类型 | 默认值 | 是否可编辑 |
| --- | --- | --- | --- |
| unity_executable | text | D:/Tools/Unity/Editor/6000.3.9f1/Editor/Unity.exe | 第一版只读 |
| project_path | text | D:/Documents/Git/Project-One/Unity/Project-One | 第一版只读 |
| execute_method | text | HotFix.Test.GameAutomatedTester.AutomatedTesterStart.BatchStartTest | 第一版只读 |

args 输入方式第一版建议使用 JSON textarea：

```json
{
  "Account": "123456",
  "timeout": 60.5,
  "debug": true,
  "scene": "Assets/Scenes/Init.unity"
}
```

按钮：

```text
启动 Unity
重置 args
格式化 args
```

启动行为：

1. 读取固定参数。
2. 解析 args JSON。
3. 调用 `POST /api/unity/start`。
4. 成功后把返回的实例加入列表。
5. 自动刷新实例列表。

### 3. Unity 实例列表

通过接口获取：

```http
GET /api/unity
```

显示字段：

| 字段 | 说明 |
| --- | --- |
| id | Unity 实例 ID |
| state | 实例状态 |
| process_id | Unity 进程 ID |
| progress | 当前进度 |

`progress` 需要以进度条形式展示，而不是只显示数字。

列表中的进度条展示规则：

```text
[████████░░░░░░░░] 50%
```

数据来源：

```text
Unity 上报 progress 消息
  ↓
服务端更新 UnityInstance.progress
  ↓
前端轮询 GET /api/unity
  ↓
列表中的进度条更新
```

进度值约定：

| 服务端 progress | 页面展示 |
| --- | --- |
| 0.0 | 0% |
| 0.5 | 50% |
| 1.0 | 100% |

如果 Unity 上报：

```json
{
  "type": "progress",
  "payload": {
    "current": 30,
    "total": 100,
    "percent": 0.3,
    "message": "Auto login"
  }
}
```

页面应展示：

```text
30% Auto login
```

第一阶段服务端实例摘要只返回 `progress` 数值；如果需要显示最近进度消息，后续可以在 `UnityInstance` 中增加 `progress_message` 字段。

推荐状态颜色：

| 状态 | 颜色 |
| --- | --- |
| waiting_for_connection | 黄色 |
| connected | 蓝色 |
| running | 紫色 |
| completed | 绿色 |
| failed | 红色 |
| stopped | 灰色 |
| disconnected | 橙色 |

每行操作：

```text
详情
日志
停止
发送 Ping
发送 Shutdown
```

### 4. 实例详情面板

点击实例后调用：

```http
GET /api/unity/{instance_id}
```

展示：

```text
id
state
process_id
project_path
unity_executable
execute_method
args
launch_command
start_time
connected_time
end_time
last_heartbeat_time
progress
error_message
result
```

`launch_command` 使用可复制代码块展示，方便排查 Unity 启动问题。

详情页必须包含一个更明显的进度条区域：

```text
当前进度
[████████████░░░░] 75%
状态：running
```

详情页进度条数据来源：

```text
GET /api/unity/{instance_id}.progress
```

当收到新的 `progress` 上报后，服务端更新实例进度。前端详情页通过自动刷新同步最新进度。

### 5. 日志面板

点击实例后进入详细信息界面，日志面板直接展示该实例收到的 Unity 日志。

交互要求：

1. 用户点击实例列表中的某个实例。
2. 页面进入或切换到实例详细信息界面。
3. 详情界面展示实例基础信息、进度条、日志列表、结果信息和操作按钮。
4. 日志列表展示该实例收到的所有 `log` 消息。
5. 如果自动刷新开启，当前实例日志应持续更新。

调用：

```http
GET /api/unity/{instance_id}/logs
```

展示 Unity 上报的日志：

```text
timestamp | level | message
```

日志展示规则：

| level | 展示样式 |
| --- | --- |
| info | 默认文本 |
| warning | 黄色 |
| error | 红色 |

日志为空时显示：

```text
暂无日志
```

日志较多时：

1. 日志区域固定高度。
2. 内部滚动。
3. 默认自动滚动到底部。
4. 用户手动向上滚动时可以暂停自动滚动。

按钮：

```text
刷新日志
清空显示
```

第一阶段只清空前端显示，不清空服务端内存。

### 6. 发送消息面板

向指定 Unity 实例发送消息：

```http
POST /api/unity/{instance_id}/message
```

预设按钮：

```text
Ping
Shutdown
Start Test
Stop Test
Custom Command
```

自定义消息 textarea：

```json
{
  "type": "custom_command",
  "payload": {
    "message": "hello unity"
  }
}
```

## 前端 API 调用

### 健康检查

```javascript
async function getHealth() {
  const response = await fetch('/health');
  return await response.json();
}
```

### 启动 Unity

```javascript
async function startUnity(args) {
  const body = {
    unity_executable: 'D:/Tools/Unity/Editor/6000.3.9f1/Editor/Unity.exe',
    project_path: 'D:/Documents/Git/Project-One/Unity/Project-One',
    execute_method: 'HotFix.Test.GameAutomatedTester.AutomatedTesterStart.BatchStartTest',
    args
  };

  const response = await fetch('/api/unity/start', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return await response.json();
}
```

### 获取实例列表

```javascript
async function listInstances() {
  const response = await fetch('/api/unity');
  return await response.json();
}
```

### 获取实例详情

```javascript
async function getInstance(instanceId) {
  const response = await fetch(`/api/unity/${instanceId}`);
  return await response.json();
}
```

### 获取日志

```javascript
async function getLogs(instanceId) {
  const response = await fetch(`/api/unity/${instanceId}/logs`);
  return await response.json();
}
```

### 渲染进度条

```javascript
function renderProgress(progress) {
  const normalized = Math.max(0, Math.min(1, Number(progress) || 0));
  const percent = Math.round(normalized * 100);

  return `
    <div class="progress">
      <div class="progress-bar" style="width: ${percent}%"></div>
      <span class="progress-text">${percent}%</span>
    </div>
  `;
}
```

推荐 CSS：

```css
.progress {
  position: relative;
  height: 18px;
  background: #e5e7eb;
  border-radius: 9px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: #22c55e;
  transition: width 0.2s ease;
}

.progress-text {
  position: absolute;
  inset: 0;
  text-align: center;
  line-height: 18px;
  font-size: 12px;
}
```

### 渲染实例详情日志

```javascript
async function renderInstanceDetail(instanceId) {
  const instance = await getInstance(instanceId);
  const logResult = await getLogs(instanceId);

  renderDetailPanel(instance);
  renderLogPanel(logResult.logs || []);
}

function renderLogPanel(logs) {
  if (!logs.length) {
    return '<div class="empty">暂无日志</div>';
  }

  return logs.map(log => `
    <div class="log-row log-${log.level || 'info'}">
      <span class="log-time">${log.timestamp}</span>
      <span class="log-level">${log.level || 'info'}</span>
      <span class="log-message">${log.message || ''}</span>
    </div>
  `).join('');
}
```

### 停止实例

```javascript
async function stopInstance(instanceId, force = false) {
  const response = await fetch(`/api/unity/${instanceId}/stop`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ force })
  });

  return await response.json();
}
```

### 发送消息

```javascript
async function sendMessage(instanceId, type, payload = {}) {
  const response = await fetch(`/api/unity/${instanceId}/message`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ type, payload })
  });

  return await response.json();
}
```

## 列表缓存策略

当前服务端实例存储在内存中：

```text
UnityInstanceManager._instances
```

网页端也可以做一层前端缓存：

```javascript
const instanceCache = new Map();
```

刷新列表时：

1. 调用 `GET /api/unity`。
2. 根据 `id` 更新 `instanceCache`。
3. 保留当前选中的实例 ID。
4. 如果实例状态变化，刷新详情面板。

第一阶段不需要 localStorage。页面刷新后重新从服务端拉取即可。

## 自动刷新

建议第一版每 2 秒自动刷新：

```text
GET /api/unity
```

如果当前选中了某个实例，则同步刷新：

```text
GET /api/unity/{instance_id}
GET /api/unity/{instance_id}/logs
```

刷新后需要更新：

1. 实例列表中的状态和进度条。
2. 当前详情页中的大进度条。
3. 当前详情页中的日志面板。
4. 当前详情页中的 result/error_message。

可提供开关：

```text
自动刷新 ON/OFF
```

## 错误处理

页面需要展示以下错误：

1. args JSON 格式错误。
2. `/api/unity/start` 返回 422。
3. Unity 启动失败。
4. Unity 未连接，发送消息失败。
5. 停止实例失败。

错误展示位置：

```text
页面顶部 Toast / Alert 区域
```

错误内容直接显示接口返回文本，便于调试。

## MVP 实现任务

### 阶段 1：静态页面基础

- 创建 `server/app/web/index.html`。
- 创建 `server/app/web/styles.css`。
- 创建 `server/app/web/app.js`。
- FastAPI 挂载静态目录。
- 页面显示服务状态。

### 阶段 2：启动表单

- 显示固定启动参数。
- 提供 args JSON textarea。
- 实现启动 Unity 按钮。
- 处理 422 错误展示。

### 阶段 3：实例列表

- 调用 `GET /api/unity`。
- 渲染实例列表。
- 实现状态颜色。
- 实现列表进度条。
- 收到 `progress` 后通过轮询刷新进度条。
- 实现自动刷新。

### 阶段 4：详情与日志

- 点击实例进入详细信息界面。
- 显示实例基础信息。
- 显示详情页大进度条。
- 显示 `args`。
- 显示 `launch_command`。
- 显示收到的 Unity 日志。
- 自动刷新当前实例日志。

### 阶段 5：实例操作

- 停止实例。
- 发送 ping。
- 发送 shutdown。
- 发送自定义消息。

## 后续增强

- 使用 localStorage 保存最近使用的 args。
- 支持编辑固定启动参数。
- 支持多个启动配置 Profile。
- 支持图形化键值对编辑器。
- 支持 WebSocket 实时推送实例状态。
- 支持测试报告页面。
- 支持实例历史持久化。
