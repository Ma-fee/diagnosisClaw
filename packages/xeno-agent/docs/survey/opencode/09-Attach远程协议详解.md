# OpenCode Attach 远程协议详解

## 1. 协议概述

OpenCode Attach 协议是 OpenCode TUI 与远程 Agent Server 之间的通信协议，基于 HTTP + SSE (Server-Sent Events) 实现。该协议支持实时双向通信：客户端通过 HTTP 请求发送指令，服务端通过 SSE 推送事件。

### 1.1 协议层次结构

```
┌─────────────────────────────────────────┐
│           Application Layer             │
│  (Session/Message/Part/Tool 事件语义)   │
├─────────────────────────────────────────┤
│           Transport Layer               │
│       (HTTP/1.1 + SSE Streaming)        │
├─────────────────────────────────────────┤
│           Protocol Format               │
│          (JSON + Zod Schema)            │
└─────────────────────────────────────────┘
```

## 2. 连接建立

### 2.1 连接参数

```bash
opencode attach http://localhost:4096 [options]

选项:
  --password <pwd>     # 身份验证密码
  --directory <dir>    # 工作目录
  --session-id <id>    # 恢复已有会话
```

### 2.2 身份验证

使用 HTTP Basic Authentication，用户名固定为 `opencode`：

```typescript
const auth = `Basic ${Buffer.from(`opencode:${password}`).toString("base64")}`
headers: {
  "Authorization": auth,
  "Accept": "text/event-stream"  // SSE 必需
}
```

### 2.3 连接初始化流程

```
┌────────┐                           ┌────────┐
│ Client │                           │ Server │
└───┬────┘                           └───┬────┘
    │ 1. GET /event (SSE subscribe)      │
    │ ───────────────────────────────>   │
    │ 2. GET /session (list sessions)    │
    │ ───────────────────────────────>   │
    │ 3. GET /config                     │
    │ ───────────────────────────────>   │
    │ 4. GET /agent/list                 │
    │ ───────────────────────────────>   │
    │ 5. GET /provider/list              │
    │ ───────────────────────────────>   │
    │                                    │
    │ <── 6. SSE events start streaming ─
```

## 3. 核心端点规范

### 3.1 SSE 事件订阅

```http
GET /event HTTP/1.1
Host: localhost:4096
Accept: text/event-stream
Authorization: Basic b3BlbmNvZGU6cGFzc3dvcmQ=
Cache-Control: no-cache
```

**响应**: `text/event-stream` 流

```
event: message.part.updated
data: {"type":"message.part.updated","properties":{"part":{...}}}

event: session.updated
data: {"type":"session.updated","properties":{"info":{...}}}

:heartbeat  # 每 30 秒的心跳注释
```

**心跳机制**: 服务端每 30 秒发送 `:heartbeat` 注释行，防止客户端超时（WKWebView 默认 60 秒超时）。

### 3.2 Session 管理端点

#### 创建 Session

```http
POST /session HTTP/1.1
Content-Type: application/json

{
  "title": "string",           // 会话标题
  "agent": "string",           // Agent 名称
  "modelID": "string",         // 模型 ID
  "providerID": "string",      // 提供商 ID
  "parentID": "string?",       // 父会话 ID（subagent 使用）
  "permission": [...]          // 权限规则
}
```

**响应**:

```json
{
  "id": "sess_xxx",
  "title": "...",
  "agent": "...",
  "model": { "providerID": "...", "modelID": "..." },
  "time": { "created": 1234567890, "updated": 1234567890 },
  "status": "active"
}
```

#### 获取 Session 列表

```http
GET /session?start=<timestamp>&roots=true&search=<keyword>&limit=<n> HTTP/1.1
```

**查询参数**:

| 参数     | 类型    | 说明                                      |
| -------- | ------- | ----------------------------------------- |
| `start`  | number  | 时间戳过滤，返回 updated > start 的会话   |
| `roots`  | boolean | **仅返回顶级会话**（parentID 为空的会话） |
| `search` | string  | 按标题搜索过滤                            |
| `limit`  | number  | 最大返回数量，默认无限制                  |

**响应**: `Session[]`

> **注意**: `roots=true` 用于主会话列表，过滤掉 subagent 创建的子会话。

#### 获取 Session 详情

```http
GET /session/{sessionID} HTTP/1.1
```

**响应**: `Session.Info`

#### 获取子 Session 列表 ⭐

用于获取某个父会话的所有子会话（subagent 会话）。

```http
GET /session/{sessionID}/children HTTP/1.1
```

**响应**: `Session.Info[]`

**使用场景**: 当用户点击工具卡片中的 "View Subagent" 时，UI 调用此端点获取子会话列表，然后可以导航到子会话查看详情。

```typescript
// 响应示例
[
  {
    id: "sess_abc123",
    parentID: "sess_parent456", // 指向父会话
    title: "(@general subagent)",
    directory: "/path/to/project",
    time: { created: 1234567890, updated: 1234567891 },
    status: "active",
  },
];
```

### 3.3 消息端点

#### 获取消息列表

```http
GET /session/{sessionID}/message?limit=100 HTTP/1.1
```

**响应**:

```json
{
  "data": [
    {
      "info": {
        /* Message 对象 */
      },
      "parts": [
        /* Part 数组 */
      ]
    }
  ]
}
```

#### 发送消息（流式响应）

```http
POST /session/{sessionID}/message HTTP/1.1
Content-Type: application/json

{
  "content": "string",         // 用户输入
  "parts": [...],              // 文件/上下文 Parts
  "modelID": "string",         // 覆盖模型
  "providerID": "string"       // 覆盖提供商
}
```

**响应**: `application/json` 流，每个 chunk 是一个 Part 更新事件。

#### 中止处理

```http
POST /session/{sessionID}/abort HTTP/1.1
```

#### Fork Session

```http
POST /session/{sessionID}/fork HTTP/1.1
Content-Type: application/json

{
  "messageID": "string"        // 从哪条消息分叉
}
```

## 4. 事件系统规范

### 4.1 事件定义机制

OpenCode 使用 **BusEvent** 模式定义类型安全的事件。所有事件通过 `BusEvent.define()` 工厂函数创建，基于 Zod Schema 进行运行时验证：

```typescript
// 事件定义模式 (bus/bus-event.ts)
const Event = BusEvent.define(
  "event.type.name", // 事件类型标识符
  z.object({
    // Zod schema 定义 properties
    field1: z.string(),
    field2: z.number(),
  }),
);

// 发布事件
Bus.publish(Event, { field1: "value", field2: 123 });

// 订阅事件
Bus.subscribe(Event, (evt) => {
  console.log(evt.properties.field1);
});
```

**事件命名规范**: 使用 `domain.action` 或 `domain.subdomain.action` 层级命名，如 `message.part.updated`、`session.created`。

### 4.2 事件传输格式

SSE 流中的事件格式：

```
event: message.part.updated
data: {"type":"message.part.updated","properties":{"part":{"id":"...","type":"text",...}}}

event: session.updated
data: {"type":"session.updated","properties":{"info":{"id":"...",...}}}
```

- **event 字段**: 事件类型标识符（对应 BusEvent.define 的第一个参数）
- **data 字段**: JSON 序列化的事件对象，包含 `type` 和 `properties`

### 4.3 核心事件类型

#### Session 事件

```typescript
// 会话创建
{ type: "session.created", properties: { info: Session } }

// 会话更新
{ type: "session.updated", properties: { info: Session } }

// 会话删除
{ type: "session.deleted", properties: { id: string } }

// 会话状态变更
{ type: "session.status", properties: { sessionID: string, status: SessionStatus } }

// Diff 更新
{ type: "session.diff", properties: { sessionID: string, diff: FileDiff[] } }
```

#### Message 事件

```typescript
// 消息更新
{
  type: "message.updated",
  properties: { info: Message }
}

// 消息删除
{
  type: "message.removed",
  properties: { sessionID: string, messageID: string }
}
```

#### Part 事件（流式更新关键）

```typescript
// Part 更新/创建
{
  type: "message.part.updated",
  properties: {
    part: Part  // 完整的 Part 对象
  }
}

// Part 删除
{
  type: "message.part.removed",
  properties: {
    messageID: string,
    partID: string
  }
}
```

#### 权限/提问事件

```typescript
// 权限请求
{
  type: "permission.asked",
  properties: {
    id: string,
    sessionID: string,
    tool: { name: string, callID: string, input: any },
    patterns: string[]
  }
}

// 权限响应（客户端 → 服务端）
{ type: "permission.replied", properties: { requestID: string, allowed: boolean } }

// 用户提问请求
{
  type: "question.asked",
  properties: {
    id: string,
    sessionID: string,
    question: string
  }
}

// 用户提问响应
{ type: "question.replied", properties: { requestID: string, answer: string } }
```

### 4.3 事件订阅机制

客户端通过 `/event` SSE 端点订阅所有事件，服务端维护事件广播。

## 5. 数据模型规范

### 5.1 Session 模型

```typescript
interface Session {
  id: string; // 唯一标识符
  parentID?: string; // 父会话 ID（subagent 使用）
  title: string; // 会话标题
  agent: string; // Agent 名称
  model: {
    providerID: string;
    modelID: string;
  };
  time: {
    created: number; // Unix timestamp (ms)
    updated: number;
    completed?: number;
    compacting?: number;
  };
  status: "active" | "idle" | "busy";
  permission?: PermissionRule[];
  share?: { url: string };
  revert?: {
    messageID: string;
    diff: string;
  };
}
```

### 5.2 Message 模型

```typescript
interface Message {
  id: string;
  sessionID: string;
  parentID?: string; // 父消息 ID
  role: "user" | "assistant";
  time: {
    created: number;
    completed?: number;
  };
  agent: string; // 处理消息的 agent
  model: {
    modelID: string;
    providerID: string;
  };
  error?: {
    name: string;
    data: { message: string };
  };
  finish?: string;
  mode?: "primary" | "subagent";
}
```

### 5.3 Part 模型（核心内容单元）

Part 是消息的内容片段，支持增量更新。

```typescript
type Part = TextPart | ToolPart | FilePart | ReasoningPart;

interface BasePart {
  id: string;
  messageID: string;
  index: number; // 在消息中的顺序
}

interface TextPart extends BasePart {
  type: "text";
  text: string; // 文本内容（可增量追加）
  synthetic?: boolean; // 是否系统生成
  ignored?: boolean; // UI 是否忽略
}

interface ToolPart extends BasePart {
  type: "tool";
  tool: string; // 工具名称
  callID: string; // 唯一调用 ID
  state: ToolState; // 执行状态
}

interface ToolState {
  status: "pending" | "running" | "completed" | "error";
  input?: any; // 工具输入参数
  output?: any; // 工具输出结果
  metadata?: {
    // 工具元数据
    sessionId?: string; // Subagent Session ID
    model?: { providerID: string; modelID: string };
    diff?: string; // Edit 工具的 diff
    files?: FilePatch[]; // Patch 工具的文件列表
    diagnostics?: Diagnostic[]; // LSP 诊断信息
    title?: string;
  };
  error?: string; // 错误信息
}

interface FilePart extends BasePart {
  type: "file";
  filename: string;
  mime: string; // MIME 类型
  data: string; // Base64 编码
}

interface ReasoningPart extends BasePart {
  type: "reasoning";
  text: string; // 推理过程（可增量）
}
```

## 6. Subagent 协议细节

### 6.1 Subagent 创建流程

```
主 Session (Parent)
    │
    │ 1. Tool Call: task
    │    { subagent_type: "general", prompt: "..." }
    │
    ▼
Server 处理 task 工具:
    │
    │ 2. Session.create({
    │      parentID: ctx.sessionID,
    │      title: "{description} (@{agent} subagent)",
    │      permission: [...]
    │    })
    │
    │ 3. SessionPrompt.prompt({
    │      sessionID: newSession.id,
    │      agent: agent.name,
    │      parts: [...],
    │      tools: { todowrite: false, ... }
    │    })
    │
    ▼
返回 Task 结果:
    {
      title: params.description,
      metadata: { sessionId: session.id, model },
      output: "task_id: {session.id} ...<task_result>..."
    }
```

### 6.2 父子 Session 关联

```typescript
// 创建时建立关系
const session = await Session.create({
  parentID: ctx.sessionID, // ← 关键关联字段
  title: `(@${agent.name} subagent)`,
  permission: [
    { permission: "todowrite", pattern: "*", action: "deny" },
    { permission: "todoread", pattern: "*", action: "deny" },
    // 防止嵌套 subagent 循环
    ...(!hasTaskPermission
      ? [{ permission: "task", pattern: "*", action: "deny" }]
      : []),
  ],
});
```

### 6.3 Subagent Part 结构

当 subagent 执行时，父会话会收到 `tool` 类型的 Part：

```typescript
{
  type: "tool",
  tool: "task",
  callID: "call_xxx",
  state: {
    status: "running",           // 或 "completed"
    input: {
      description: "任务描述",
      subagent_type: "general",
      prompt: "..."
    },
    output: "task_id: sess_xxx...<task_result>...</task_result>",
    metadata: {
      sessionId: "sess_xxx",     // ← 子会话 ID，UI 跳转关键
      model: { providerID: "...", modelID: "..." },
      title: "任务描述"
    }
  }
}
```

### 6.4 Subagent 查看流程 ⭐

当用户想要查看 subagent 的执行详情时，完整的协议交互流程：

#### 6.4.1 时序图

```
┌──────────┐          ┌──────────┐          ┌──────────┐
│   User   │          │   TUI    │          │  Server  │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │                     │                     │
     │ 1. 看到 Subagent    │                     │
     │    工具卡片         │                     │
     │                     │                     │
     │ 2. 点击 "View"      │                     │
     │ ──────────────────> │                     │
     │                     │                     │
     │                     │ 3. GET /session/    │
     │                     │    {parentID}/      │
     │                     │    children         │
     │                     │ ──────────────────> │
     │                     │                     │
     │                     │ 4. Session.Info[]   │
     │                     │ <────────────────── │
     │                     │    [{id, parentID,  │
     │                     │      title, ...}]    │
     │                     │                     │
     │                     │ 5. 选择子会话并     │
     │                     │    GET /session/    │
     │                     │    {childID}/       │
     │                     │    message          │
     │                     │ ──────────────────> │
     │                     │                     │
     │                     │ 6. 消息列表 +       │
     │                     │    Parts            │
     │                     │ <────────────────── │
     │                     │                     │
     │ 7. 显示子会话       │                     │
     │    内容             │                     │
     │ <────────────────── │                     │
     │                     │                     │
     │                     │ 8. [持续] SSE 接收  │
     │                     │    message.part.    │
     │                     │    updated          │
     │                     │ <────────────────── │
```

#### 6.4.2 协议消息详解

**步骤 3-4: 获取子会话列表**

```http
GET /session/sess_parent_001/children HTTP/1.1
Accept: application/json
Authorization: Basic b3BlbmNvZGU6cGFzc3dvcmQ=
```

**响应**:

```json
[
  {
    "id": "sess_sub_abc123",
    "parentID": "sess_parent_001",
    "title": "(@general subagent)",
    "directory": "/workspace/project",
    "agent": "general",
    "model": {
      "providerID": "openai",
      "modelID": "gpt-4"
    },
    "time": {
      "created": 1704067200000,
      "updated": 1704067230000,
      "completed": 1704067250000
    },
    "status": "active"
  },
  {
    "id": "sess_sub_def456",
    "parentID": "sess_parent_001",
    "title": "(@code subagent)",
    ...
  }
]
```

#### 6.4.3 关键字段说明

| 字段             | 类型    | 说明                                                 |
| ---------------- | ------- | ---------------------------------------------------- |
| `parentID`       | string  | **指向父会话的 ID**，非空表示这是 subagent 会话      |
| `title`          | string  | 格式为 `(@{agent} subagent)`，便于识别               |
| `status`         | string  | `active` \| `idle` \| `busy`，反映 subagent 执行状态 |
| `time.completed` | number? | 如果存在表示 subagent 已完成执行                     |

#### 6.4.4 客户端实现逻辑

```typescript
// 1. 从 ToolPart 获取子会话 ID
const subagentSessionId = toolPart.state.metadata?.sessionId;

// 2. 或者查询父会话的所有子会话
const children = await fetch(`/session/${parentId}/children`);
const subagentSessions = await children.json();

// 3. 导航到子会话（加载其消息）
const messages = await fetch(`/session/${subagentSessionId}/message`);
const data = await messages.json();

// 4. 渲染子会话内容
data.forEach(({ info, parts }) => {
  renderMessage(info);
  parts.forEach(renderPart);
});

// 5. 订阅子会话的实时更新
const eventSource = new EventSource("/event");
eventSource.addEventListener("message.part.updated", (e) => {
  const { part } = JSON.parse(e.data).properties;
  if (part.sessionID === subagentSessionId) {
    updatePart(part);
  }
});
```

#### 6.4.5 Session 树形结构视图

为了实现类似文件浏览器的会话树，客户端可以：

```typescript
// 获取所有根会话
const roots = await fetch("/session?roots=true").then((r) => r.json());

// 对每个会话递归获取子会话
async function buildSessionTree(session) {
  const children = await fetch(`/session/${session.id}/children`).then((r) =>
    r.json(),
  );

  return {
    ...session,
    children: await Promise.all(children.map(buildSessionTree)),
  };
}

// 最终结构
const tree = await Promise.all(roots.map(buildSessionTree));
/*
[
  {
    id: "root_sess_1",
    title: "Main Session",
    children: [
      {
        id: "sub_sess_a",
        title: "(@general subagent)",
        children: [...]  // 可能还有嵌套 subagent
      },
      {
        id: "sub_sess_b",
        title: "(@code subagent)",
        children: []
      }
    ]
  }
]
*/
```

### 6.5 Task 工具元数据补充 ⭐

`ToolState.metadata` 支持更多字段用于不同工具的 UI 展示：

```typescript
interface ToolMetadata {
  // Subagent 工具
  sessionId?: string; // 子会话 ID
  title?: string; // 任务描述

  // Edit 工具
  diff?: string; // 代码 diff (unified format)

  // Patch 工具
  files?: Array<{
    filename: string;
    status: "added" | "modified" | "deleted";
  }>;

  // Bash/命令工具
  command?: string; // 执行的命令

  // LSP 相关
  diagnostics?: Array<{
    file: string;
    line: number;
    message: string;
    severity: "error" | "warning";
  }>;

  // 通用
  model?: {
    providerID: string;
    modelID: string;
  };
}
```

### 6.6 Subagent Tool Call 监控机制 ⭐

当 subagent 执行工具调用时，主 session 的 UI 需要实时显示 "X toolcalls" 更新。这是通过**全局 SSE 流**实现的：

#### 6.6.1 核心机制

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SUBAGENT TOOL CALL FLOW                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ 1. MAIN SESSION triggers Task tool                                      │
│    └─> Creates child session with parentID=mainSessionID                │
│    └─> Returns: metadata: { sessionId: childSessionId }                 │
│                                                                         │
│ 2. CHILD SESSION executes tools                                         │
│    └─> Each tool call emits: message.part.updated {part}                │
│    └─> part.sessionID = CHILD session ID（不是 parent ID）                │
│                                                                         │
│ 3. SERVER broadcasts via SSE (/event)                                   │
│    └─> All events flow through single global stream                     │
│                                                                         │
│ 4. CLIENT receives event                                                │
│    └─> Updates store.part[messageID] = [...]                            │
│    └─> Events with child sessionID stored under child key               │
│                                                                         │
│ 5. UI reacts: Task tool component reads child data                      │
│    └─> Via props.metadata.sessionId → lookup child session              │
│    └─> Counter: getSessionToolParts(store, childSessionId).length       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 6.6.2 关键要点

**1. 单一全局 SSE 流**

所有 session（包括 subagent）的更新都通过同一个 SSE 连接推送，无需单独建立监控连接：

```typescript
// 客户端建立一次连接
const eventSource = new EventSource("/event")
eventSource.addEventListener("message.part.updated", (e) => {
  const { part } = JSON.parse(e.data).properties
  // part.sessionID 是事件来源的 session ID
  store.part[part.messageID] = [...]  // 更新存储
})
```

**2. Event 中的 sessionID 是子 session ID**

```typescript
// 子 session 发出的 event
{
  type: "message.part.updated",
  properties: {
    part: {
      id: "prt_xxx",
      sessionID: "ses_CHILD",      // ← 子 session ID
      messageID: "msg_xxx",
      type: "tool",
      tool: "read",
      state: { status: "running", /* ... */ }
    }
  }
}
```

**不需要在 event 中携带 parentID！**

**3. 父子关联通过 Tool Metadata 建立**

```typescript
// Task 工具返回的 metadata
return {
  title: params.description,
  metadata: {
    sessionId: session.id, // ← 子 session ID 存入 metadata
    model,
  },
};

// 前端通过 metadata.sessionId 关联
const childSessionId = () => props.metadata.sessionId;
const childToolParts = () => getSessionToolParts(store, childSessionId());
// 显示: {childToolParts().length} toolcalls
```

#### 6.6.3 客户端事件处理

```typescript
// packages/ui/src/components/message-part.tsx
ToolRegistry.register({
  name: "task",
  render(props) {
    const childSessionId = () => props.metadata.sessionId as string;

    // 同步子 session 数据
    createEffect(() => {
      const sessionId = childSessionId();
      if (!sessionId) return;
      Promise.resolve(syncSession(sessionId)).catch(() => undefined);
    });

    // 计算 tool call 数量
    const childToolParts = createMemo(() => {
      const sessionId = childSessionId();
      if (!sessionId) return [];
      return getSessionToolParts(data.store, sessionId);
    });

    // UI: {childToolParts().length} toolcalls
  },
});
```

#### 6.6.4 服务端实现要点

要实现兼容的 server：

1. **全局 SSE 端点**: `GET /event` 推送所有 session 的事件
2. **Part 事件格式**: `message.part.updated` 必须包含 `sessionID`（子 session）
3. **Session 存储**: 创建 session 时记录 `parentID`
4. **Task 工具**: 返回 `metadata: { sessionId }` 供前端关联

```typescript
// 创建 subagent session
const childSession = await Session.create({
  parentID: ctx.sessionID, // 服务端存储父子关系
  title: `(@${agent} subagent)`,
});

// 推送 tool call 事件（sessionID 是子 session）
Bus.publish("message.part.updated", {
  part: {
    sessionID: childSession.id, // 子 session ID
    messageID: msg.id,
    type: "tool",
    tool: "read",
    state: { status: "running" },
  },
});
```

### 6.7 Session 列表分页机制 ⭐

对于历史会话较多的场景，支持游标分页：

```http
GET /session?roots=true&start=<timestamp>&limit=50 HTTP/1.1
```

**请求参数**:

| 参数    | 类型   | 说明                                                         |
| ------- | ------ | ------------------------------------------------------------ |
| `start` | number | Unix 毫秒时间戳，返回 `updated < start` 的会话（旧于该时间） |
| `limit` | number | 每页数量                                                     |

**响应结构**:

```json
{
  "data": [
    {
      /* Session Info */
    },
    {
      /* Session Info */
    }
  ],
  "nextCursor": "1704067200000" // 最后一条的 updated 时间，用于下一页
}
```

**客户端分页逻辑**:

````typescript
async function* listSessionsPaginated(directory) {
  let cursor = undefined;

  do {
    const params = new URLSearchParams({ roots: "true", directory });
    if (cursor) params.set("start", cursor);

    const response = await fetch(`/session?${params}`);
    const { data, nextCursor } = await response.json();

    yield data;
    cursor = nextCursor;
  } while (cursor);
}

### 6.8 Tool Title 生成机制 ⭐

**重要：Tool Title 不是 LLM 显式输出的，而是由工具实现自己生成的。**

#### 6.8.1 Title 字段定义

```typescript
// ToolStateRunning - title 是可选的（运行中通过 ctx.metadata 设置）
interface ToolStateRunning {
  status: "running"
  input: Record<string, any>
  title?: string              // ← 运行中可选
  metadata?: Record<string, any>
  time: { start: number }
}

// ToolStateCompleted - title 是必需的（最终状态必须提供）
interface ToolStateCompleted {
  status: "completed"
  input: Record<string, any>
  output: string
  title: string               // ← 完成状态必需
  metadata: Record<string, any>
  time: { start: number; end: number }
}
````

#### 6.8.2 Title 不在 LLM 可见的 Schema 中

LLM 调用工具时**看不到** `title` 参数，它只能提供工具定义中声明的参数：

| 工具      | LLM 提供的参数                                 | Title 生成方式                             |
| --------- | ---------------------------------------------- | ------------------------------------------ |
| **bash**  | `command`, `timeout`, `workdir`, `description` | `title: params.description`                |
| **read**  | `filePath`, `offset`, `limit`                  | `title: path.relative(worktree, filePath)` |
| **edit**  | `filePath`, `oldString`, `newString`           | `title: path.relative(worktree, filePath)` |
| **write** | `filePath`, `content`                          | `title: path.relative(worktree, filePath)` |
| **task**  | `description`, `prompt`, `subagent_type`       | `title: params.description`                |
| **grep**  | `pattern`, `path`                              | `title: params.pattern`                    |

#### 6.8.3 工具返回 Title

工具执行完成后必须返回 `title`：

```typescript
// bash 工具示例
return {
  title: params.description, // 从 LLM 提供的 description 生成
  metadata: { output, exit },
  output,
};

// read 工具示例
const title = path.relative(Instance.worktree, filepath);
return {
  title, // 从 filePath 生成
  output,
  metadata: { preview, truncated, loaded },
};
```

#### 6.8.4 运行中更新 Title

工具可以通过 `ctx.metadata()` 在运行中更新 title：

```typescript
ctx.metadata({
  title: "正在执行...",
  metadata: { progress: 50 },
});
```

#### 6.8.5 服务端实现要点

```typescript
// 实现示例
async function executeTool(toolName, params, ctx) {
  // 1. 开始运行（status: "running"）
  emitEvent({
    type: "message.part.updated",
    properties: {
      part: {
        id: "prt_xxx",
        type: "tool",
        tool: toolName,
        state: {
          status: "running",
          input: params,
          // title 可选
        },
      },
    },
  });

  // 2. 执行工具逻辑...

  // 3. 生成 title（基于参数或结果）
  const title = generateTitle(toolName, params);

  // 4. 完成运行（status: "completed"）
  emitEvent({
    type: "message.part.updated",
    properties: {
      part: {
        state: {
          status: "completed",
          title, // ← 必需
          output: result,
          metadata: {},
        },
      },
    },
  });
}
```

### 6.9 工具类型匹配机制 ⭐

#### 6.9.1 ToolPart 结构区分

```typescript
interface ToolPart {
  id: string;
  sessionID: string;
  messageID: string;
  type: "tool"; // ← 固定值：所有工具都是 "tool"
  callID: string;
  tool: string; // ← 实际工具类型："bash", "read", "edit", "task"...
  state: ToolState;
}
```

**关键区分**：

- `type: "tool"` — 固定值，表明这是工具类型的 part
- `tool: "bash"` — UI 据此匹配渲染组件

#### 6.9.2 UI 渲染匹配机制

前端通过 **ToolRegistry** 根据 `part.tool` 查找渲染组件：

```typescript
// packages/ui/src/components/message-part.tsx
const render = ToolRegistry.render(part.tool) ?? GenericTool;
```

匹配逻辑：

1. 查找 `ToolRegistry` 中注册的 `part.tool` 渲染器
2. 找到 → 使用自定义渲染组件
3. 未找到 → 回退到 `GenericTool`（通用 MCP 组件）

#### 6.9.3 内置工具渲染映射

| 工具名 (`tool`) | 图标                    | 特殊渲染功能                      |
| --------------- | ----------------------- | --------------------------------- |
| `read`          | `glasses`               | 文件内容查看器，支持代码高亮      |
| `list`          | `bullet-list`           | 目录列表显示                      |
| `glob`          | `magnifying-glass-menu` | 文件模式搜索结果                  |
| `grep`          | `magnifying-glass-menu` | 内容搜索结果                      |
| `webfetch`      | `window-cursor`         | 网页内容，支持跳转链接            |
| `task`          | `task`                  | Subagent 任务，支持点击查看子会话 |
| `bash`          | `console`               | 命令输出，代码块样式              |
| `edit`          | `code-lines`            | Diff 对比视图（before/after）     |
| `write`         | `code-lines`            | 新文件代码展示                    |
| `apply_patch`   | `code-lines`            | 多文件 patch 视图                 |
| `todowrite`     | `checklist`             | 待办清单复选框                    |
| `question`      | `bubble-5`              | 用户提问表单                      |

#### 6.9.4 未知/自定义工具处理

如果 `tool` 名称未注册，UI 回退到 `GenericTool`：

```typescript
function GenericTool(props) {
  return <BasicTool
    icon="mcp"           // MCP 拼图图标
    trigger={{ title: props.tool }}  // 显示工具名
    hideDetails={false}
  />
}
```

**行为**：

- 图标：MCP 拼图块图标
- 标题：工具名字符串
- 无特殊渲染，仅可折叠卡片展示
- 支持自定义 MCP 工具

#### 6.9.5 服务端实现要点

```typescript
// 正确：type 固定为 "tool"，tool 字段标识具体类型
emitEvent({
  type: "message.part.updated",
  properties: {
    part: {
      id: "prt_xxx",
      sessionID: "ses_xxx",
      messageID: "msg_xxx",
      type: "tool", // ← 固定值
      tool: "bash", // ← UI 据此渲染！重要！
      callID: "call_xxx",
      state: {
        status: "completed",
        title: "列出文件",
        output: "file1.txt\nfile2.txt",
      },
    },
  },
});

// 自定义工具示例 - UI 会显示为 GenericTool
emitEvent({
  type: "message.part.updated",
  properties: {
    part: {
      type: "tool",
      tool: "my_custom_tool", // ← 未注册的工具名
      state: { status: "completed", title: "自定义工具", output: "..." },
    },
  },
});
```

### 6.10 Subagent 第一个 Prompt 显示/隐藏机制 ⭐

**问题**: Subagent 的内容区域（红框2）有时显示第一个 prompt（## 1. TASK 等），有时不显示。

#### 6.10.1 核心机制：synthetic 字段

**TextPart.synthetic** 字段控制内容是否对隐藏：

```typescript
// packages/opencode/src/cli/cmd/tui/routes/session/index.tsx:1164
const text = createMemo(
  () =>
    props.parts.flatMap((x) =>
      x.type === "text" && !x.synthetic ? [x] : [],
    )[0],
);
```

| synthetic 值          | 效果                   |
| --------------------- | ---------------------- |
| `undefined` / `false` | 用户和 AI 都能看到 ✅  |
| `true`                | 只给 AI，TUI 中隐藏 ❌ |

#### 6.10.2 Audience 注解处理

OpenCode 原生 ACP agent 根据 `part.annotations.audience` 自动设置 `synthetic`：

```typescript
// packages/opencode/src/acp/agent.ts:1238-1247
const audience = part.annotations?.audience;
const forAssistant = audience?.length === 1 && audience[0] === "assistant";

parts.push({
  type: "text",
  text: part.text,
  ...(forAssistant && { synthetic: true }), // audience: ["assistant"] → 隐藏
});
```

**规则**:

- `audience: ["assistant"]` → `synthetic: true`（只给 AI，对用户隐藏）
- `audience: ["user"]` → `ignored: true`（只给用户，不发给 AI）
- 无 audience → 双方可见

#### 6.10.3 UI 组件层级

```
session/index.tsx
├── Header (红框1)        ← header.tsx，显示 "Subagent session" + 导航
├── scrollbox (可滚动容器)
│   └── UserMessage (红框2) ← 过滤 synthetic parts 决定显示内容
│       └── TextPart          ← 实际渲染 markdown
│   └── AssistantMessage
└── Prompt (输入框)       ← subagent 时隐藏 (parentID 存在)
```

**Prompt 隐藏逻辑**:

```tsx
// session/index.tsx:1101
<Prompt
  visible={!session()?.parentID && ...}  // subagent 有 parentID，所以隐藏
/>
```

#### 6.10.4 常见错误与修复

**错误1: 意外设置 synthetic**

```typescript
// ❌ 错误 - 内容在 TUI 中隐藏
parts.push({
  type: "text",
  text: promptText,
  synthetic: true, // ← 导致不显示！
});

// ✅ 正确 - 双方可见
parts.push({
  type: "text",
  text: promptText,
  // synthetic 不设置
});
```

**错误2: Audience 注解处理不当**

```typescript
// ❌ 错误：希望用户看到，但 audience 标记为 assistant
{
  type: "text",
  text: promptText,
  annotations: { audience: ["assistant"] }  // native 实现会转为 synthetic:true
}

// ✅ 正确：移除 audience 注解或改为双方可见
{
  type: "text",
  text: promptText
  // 无 annotations
}
```

#### 6.10.5 远程服务器实现要点

**正确的第一个 prompt 发送方式**:

```python
# 1. 创建 subagent session
session = await create_session(
    parent_id=parent_session_id,
    title=f"{description} (@{agent_type} subagent)"
)

# 2. 发送第一个用户消息（prompt），不包含 synthetic
await send_message_updated(
    session_id=session.id,
    message=Message(
        role="user",
        parts=[{
            "type": "text",
            "text": prompt_text,
            # 不设置 synthetic
            # 不设置 annotations.audience: ["assistant"]
        }]
    )
)
```

#### 6.10.6 事件触发链

```
Subagent 启动
    │
    ├─→ Session.create(parentID, title)
    │   └─→ Bus.publish("session.created")
    │
    ├─→ SessionPrompt.prompt()
    │   └─→ Bus.publish("message.updated")
    │       └─→ TUI 显示 banner（来自 Session title）
    │
    └─→ 第一个 prompt 通过 message.parts 发送
        └─→ TUI UserMessage 组件渲染（过滤 synthetic）
            └─→ TextPart 渲染 markdown 内容
```

**关键事件**:

- `session.created` - 创建 session
- `message.updated` - 触发 banner 和内容显示

#### 6.10.7 调试检查清单

如果第一个 prompt 不显示，检查：

1. **TextPart 是否设置了 `synthetic: true`**

   ```typescript
   console.log("Parts:", message.parts);
   console.log(
     "Synthetic:",
     message.parts.filter((p) => p.synthetic),
   );
   ```

2. **Audience 注解**

   ```typescript
   console.log("Annotations:", part.annotations);
   ```

3. **事件是否正确发送**
   ```typescript
   // 检查事件类型和 payload
   console.log("Event:", event.type, event.properties);
   ```

#### 6.10.8 参考代码路径

| 功能           | 文件路径                                | 行号      |
| -------------- | --------------------------------------- | --------- |
| synthetic 过滤 | `cli/cmd/tui/routes/session/index.tsx`  | 1164      |
| Header 渲染    | `cli/cmd/tui/routes/session/header.tsx` | 86-122    |
| Prompt 隐藏    | `cli/cmd/tui/routes/session/index.tsx`  | 1101      |
| Audience 处理  | `acp/agent.ts`                          | 1238-1247 |
| TextPart 类型  | `session/message-v2.ts`                 | 95-109    |
| Subagent 创建  | `tool/task.ts`                          | 66-102    |

## 7. 实现建议

### 7.1 最小可兼容服务端

```typescript
// 必需端点
const endpoints = {
  // SSE 事件流
  "GET /event": () => EventStream,

  // Session CRUD
  "POST /session": () => Session,
  "GET /session/:id": () => Session,
  "GET /session": () => Session[],

  // Message
  "GET /session/:id/message": () => { info: Message, parts: Part[] }[],
  "POST /session/:id/message": () => AsyncIterable<Part>,
  "POST /session/:id/abort": () => void,

  // Bootstrapping
  "GET /agent": () => Agent[],
  "GET /config": () => Config,
  "GET /provider": () => Provider[]
}

// 必需事件
const requiredEvents = [
  "session.created",
  "session.updated",
  "session.deleted",
  "message.updated",
  "message.part.updated",
  "message.part.removed",
  "permission.asked",
  "question.asked"
]
```

### 7.2 事件序列示例

```
[Client] POST /session → { id: "sess_001", ... }
[Server] SSE: event:session.created data:{...}

[Client] POST /session/sess_001/message → { content: "Hello" }
[Server] SSE: event:message.updated data:{info:{id:"msg_001",...}}
[Server] SSE: event:message.part.updated data:{part:{id:"part_001",type:"text",text:"Hi"}}
[Server] SSE: event:message.part.updated data:{part:{id:"part_002",type:"tool",tool:"task",state:{status:"running",metadata:{sessionId:"sess_002"}}}}

[Client] GET /session/sess_002/message → 子会话消息
[Server] SSE: event:message.part.updated data:{part:{id:"part_003",...}}
```

### 7.3 关键实现细节

1. **Part ID 生成**: 使用单调递增的 ULID/CUID 确保排序
2. **事件排序**: 事件的 `index` 字段决定 Part 在消息中的显示顺序
3. **增量文本**: `TextPart.text` 可以分多次更新，客户端追加显示
4. **权限批准流**: 服务端推送 `permission.asked`，客户端回复到专用端点
5. **心跳维持**: SSE 流必须每 30 秒发送注释行 `:heartbeat`

## 8. OpenAPI 参考

完整端点定义参考官方 OpenAPI Schema：

```
packages/sdk/openapi.json
packages/sdk/js/src/v2/gen/types.gen.ts
packages/sdk/js/src/v2/gen/sdk.gen.ts
```

SDK 生成命令：

```bash
./packages/sdk/js/script/build.ts
```

## 参考源码路径

| 组件                    | 路径                                                 | 关键内容                                      |
| ----------------------- | ---------------------------------------------------- | --------------------------------------------- |
| Attach 命令入口         | `packages/opencode/src/cli/cmd/tui/attach.ts`        | 远程连接初始化、Basic Auth                    |
| SSE 订阅实现            | `packages/opencode/src/cli/cmd/tui/context/sdk.tsx`  | SDK 封装、事件流处理                          |
| 事件处理分发            | `packages/opencode/src/cli/cmd/tui/context/sync.tsx` | 事件同步逻辑                                  |
| **Session API 路由** ⭐ | `packages/opencode/src/server/routes/session.ts`     | **GET /session, GET /session/:id/children**   |
| 服务器主入口            | `packages/opencode/src/server/server.ts`             | 路由注册、中间件                              |
| Session 模块            | `packages/opencode/src/session/index.ts`             | **Session.create(), Session.children()** 实现 |
| Task 工具               | `packages/opencode/src/tool/task.ts`                 | **Subagent 创建**（parentID 设置）            |
| Bus 事件系统            | `packages/opencode/src/bus/index.ts`                 | BusEvent 定义、发布订阅                       |
| SDK 类型生成            | `packages/sdk/js/src/gen/types.gen.ts`               | 接口类型定义                                  |
| SDK 客户端              | `packages/sdk/js/src/gen/sdk.gen.ts`                 | session.children() 等方法                     |

### 关键代码片段参考

**Session.children() 实现** (`packages/opencode/src/session/index.ts`):

```typescript
// Lines 343-353
export async function children(parentID: string) {
  const result = await db
    .select()
    .from(sessionTable)
    .where(eq(sessionTable.parentID, parentID))
    .orderBy(desc(sessionTable.updated))
    .all();
  return result.map(fromDb);
}
```

**Session 路由 - children 端点** (`packages/opencode/src/server/routes/session.ts`):

```typescript
// Lines 124-153
{
  method: "GET",
  path: "/session/:sessionID/children",
  operationId: "session.children",
  handler: async ({ params }) => {
    const { sessionID } = params;
    return Session.children(sessionID);
  },
}
```

**Subagent 创建** (`packages/opencode/src/tool/task.ts`):

```typescript
// Lines 66-102
const session = await Session.create({
  parentID: ctx.sessionID, // ← 关键：建立父子关系
  title: `(@${agent.name} subagent)`,
  permission: [
    { permission: "todowrite", pattern: "*", action: "deny" },
    { permission: "todoread", pattern: "*", action: "deny" },
  ],
});

// 返回结果包含 metadata.sessionId
return {
  title: params.description,
  metadata: { sessionId: session.id, model },
  output: `task_id: ${session.id}...`,
};
```

## 9. TUI 底部 Agent/Model 显示规范 ⭐

**问题**: Subagent 界面底部显示 "Agent · Provider"（如 "Explore · ack-dev"），有时显示不正确（如 "Default · subagent"）。

### 9.1 核心机制

TUI 底部显示的 agent 和 model 信息来自**全局状态**，不是直接从 Session 对象读取：

```typescript
// prompt/index.tsx:999-1006
{Locale.titlecase(local.agent.current().name)} · {local.model.parsed().provider}
```

数据更新逻辑（`prompt/index.tsx:148-167`）：
```typescript
createEffect(() => {
  const sessionID = props.sessionID
  const msg = lastUserMessage()  // ← 从最后一个 UserMessage 获取

  if (sessionID !== syncedSessionID) {
    // 只更新 primary agent（mode !== "subagent"）
    const isPrimaryAgent = local.agent.list().some((x) => x.name === msg.agent)
    if (msg.agent && isPrimaryAgent) {
      local.agent.set(msg.agent)
      if (msg.model) local.model.set(msg.model)
    }
  }
})
```

### 9.2 必需端点

#### 9.2.1 GET /config/agents（或 GET /agent）

**必需**：TUI 通过此端点获取可用 agents 列表。

```http
GET /config/agents HTTP/1.1
Accept: application/json
Authorization: Basic ...
```

**响应格式**：

```typescript
[
  {
    "name": "material_assistant",      // ← Agent 唯一标识
    "mode": "primary",                  // ← 必须是 "primary"！
    "description": "物料助手",
    "permission": {                     // 权限规则
      "*": "allow",
      "bash": "ask",
      "edit": "deny"
    },
    "model": {                          // 可选：默认模型
      "providerID": "openai-chat",
      "modelID": "ack-dev"
    }
  },
  {
    "name": "build",
    "mode": "primary",
    ...
  }
]
```

**关键字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | Agent 唯一标识符，匹配 `UserMessage.agent` |
| `mode` | string | **必须是 `"primary"`**！`"subagent"` 模式的 agent 会被过滤掉，导致 TUI 无法识别 |
| `permission` | object | 工具权限规则 |
| `model` | object | 该 agent 的默认模型配置 |

**⚠️ 重要**：`mode: "subagent"` 的 agent 会被 TUI 过滤（`local.tsx:37`），这意味着：
- ❌ `{name: "explore", mode: "subagent"}` → TUI 不会更新显示
- ✅ `{name: "explore", mode: "primary"}` → TUI 正常更新显示

#### 9.2.2 GET /config/providers

已在 3.2 节定义，关键要求：

```typescript
{
  "providers": [
    {
      "id": "openai-chat",           // ← providerID，匹配 model.providerID
      "name": "Openai-Chat",          // ← UI 显示名称
      "models": {
        "ack-dev": {                   // ← modelID
          "id": "ack-dev",
          "name": "ack-dev",           // ← UI 显示名称
          "capabilities": {
            "reasoning": false         // 是否支持推理
          }
        }
      }
    }
  ],
  "default": {                        // 每个 provider 的默认模型
    "openai-chat": "ack-dev"
  }
}
```

### 9.3 UserMessage 要求

**最后一个 UserMessage** 必须包含正确的 `agent` 和 `model` 字段：

```typescript
{
  "info": {
    "role": "user",
    "agent": "material_assistant",     // ← 必须匹配 /config/agents 返回的某个 agent.name
    "model": {                          // ← 如果不提供，TUI 不会更新 model 显示
      "providerID": "openai-chat",      // ← 必须匹配 /config/providers 返回的 provider.id
      "modelID": "ack-dev"              // ← 该 provider 下的有效 model id
    }
  },
  "parts": [...]
}
```

**检查清单**：

- [ ] `agent` 字段值存在于 `/config/agents` 响应列表中
- [ ] 对应 agent 的 `mode` 为 `"primary"`（不是 `"subagent"`）
- [ ] `model.providerID` 存在于 `/config/providers` 响应列表中
- [ ] `model.modelID` 存在于对应 provider 的 `models` 对象中

### 9.4 配置一致性要求

`GET /config` 返回的默认 model 必须与 providers 列表匹配：

```http
GET /config HTTP/1.1

{
  "model": "openai-chat/ack-dev",     // ← 格式：providerID/modelID
  ...
}
```

TUI 会调用 `Provider.parseModel()` 解析：

```typescript
// provider.ts:1244
export function parseModel(model: string) {
  const [providerID, ...rest] = model.split("/")
  return {
    providerID: providerID,             // "openai-chat"
    modelID: rest.join("/"),            // "ack-dev"
  }
}
```

**常见错误**：
- ❌ `config.model = "anthropic/claude-opus-4-5-20251101"`，但 providers 列表只有 `openai-chat`
- ✅ `config.model = "openai-chat/ack-dev"`，且 providers 包含 `openai-chat` 及其 `ack-dev` 模型

### 9.5 完整数据流

```
1. TUI Bootstrap
   │
   ├─ GET /config/agents → sync.data.agent
   │   └─ 过滤 mode !== "subagent" → local.agent.list()
   │
   ├─ GET /config/providers → sync.data.provider
   │   └─ local.model.parsed() 查找 provider name
   │
   └─ GET /session/{id}/message
       │
       └─ 最后一个 UserMessage
            │
            ├─ msg.agent → local.agent.set()  【仅当 agent 在列表中且 mode=primary】
            └─ msg.model → local.model.set()  【更新 provider/model 显示】

2. UI 渲染
   prompt/index.tsx
   └─ {local.agent.current().name} · {local.model.parsed().provider}
```

### 9.6 故障排查

如果底部显示 "Default · subagent" 或其他不正确值：

| 排查项 | 检查方法 | 预期结果 |
|--------|----------|----------|
| agents 端点 | `xh /config/agents` | 返回包含目标 agent 的数组 |
| agent mode | 检查响应中的 `mode` 字段 | 必须是 `"primary"` |
| providers 端点 | `xh /config/providers` | 返回包含目标 provider 的数组 |
| UserMessage.agent | `xh /session/{id}/message \| jq '.[].info.agent'` | 与 agents 列表中的某个 name 匹配 |
| UserMessage.model | `xh /session/{id}/message \| jq '.[].info.model'` | providerID 和 modelID 有效 |
| config.model | `xh /config \| jq '.model'` | 格式为 `providerID/modelID` |

### 9.7 参考代码路径

| 功能 | 文件路径 | 行号 |
|------|----------|------|
| Agent 列表过滤 | `cli/cmd/tui/context/local.tsx` | 37 |
| Agent 状态初始化 | `cli/cmd/tui/context/local.tsx` | 40-43 |
| Agent 更新逻辑 | `cli/cmd/tui/component/prompt/index.tsx` | 158-165 |
| Model 解析 | `provider/provider.ts` | 1244-1249 |
| Model 显示 | `cli/cmd/tui/context/local.tsx` | 218-234 |
| Providers API | `server/routes/config.ts` | 62-91 |
