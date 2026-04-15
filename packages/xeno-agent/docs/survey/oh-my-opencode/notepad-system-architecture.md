# Oh-My-OpenCode Notepad 系统架构图

## 数据流图

```mermaid
sequenceDiagram
    participant User
    participant Atlas as Atlas (Orchestrator)
    participant Hook as sisyphus-junior-notepad Hook
    participant Worker as Sisyphus-Junior (Worker)
    participant FS as File System (.sisyphus/notepads/)

    User->>Atlas: 提供任务 /start-work
    
    rect rgb(240, 248, 255)
        Note over Atlas: Phase 1: 初始化 Notepad
        Atlas->>FS: mkdir -p .sisyphus/notepads/{plan}/
        Atlas->>FS: 创建 learnings.md, issues.md
    end

    loop 每个子任务
        rect rgb(255, 248, 240)
            Note over Atlas,Worker: Phase 2: 委托前读取知识
            Atlas->>FS: Read(notepads/{plan}/learnings.md)
            FS-->>Atlas: 返回已记录的约定、模式
            Atlas->>FS: Read(notepads/{plan}/issues.md)
            FS-->>Atlas: 返回已知的问题、坑
        end

        rect rgb(240, 255, 240)
            Note over Atlas,Hook: Phase 3: Hook 注入指令
            Atlas->>Hook: task(prompt="执行任务...")
            Hook->>Hook: 检查：是 Atlas 调用的 task？
            Hook->>Hook: 注入 NOTEPAD_DIRECTIVE
            Note right of Hook: 在 prompt 前添加：<br/>"你应该将 finding 追加到 notepad..."
        end

        rect rgb(255, 240, 255)
            Note over Worker,FS: Phase 4: 子 Agent 执行并记录
            Worker->>Worker: 执行任务
            Worker->>FS: Write(notepads/{plan}/learnings.md, "追加新发现...")
            Note right of Worker: 使用追加模式，<br/>不是覆盖！
        end

        rect rgb(240, 240, 255)
            Note over Atlas,Worker: Phase 5: 验证并继续
            Atlas->>FS: Read(notepads/{plan}/*.md)
            FS-->>Atlas: 确认 finding 已记录
            Atlas->>Atlas: 决定下一个任务
        end
    end

    Atlas->>User: 所有任务完成
```

## 组件关系图

```mermaid
graph TB
    subgraph "Atlas Agent (Orchestrator)"
        A1[default.ts / gpt.ts]
        A2[System Prompt]
        A3[工作流：读取→委托→验证]
    end

    subgraph "Hook Layer"
        H1[sisyphus-junior-notepad Hook]
        H2[tool.execute.before]
        H3[NOTEPAD_DIRECTIVE 注入]
    end

    subgraph "Worker Agent (Sisyphus-Junior)"
        W1[接收带 Notepad 指令的 Prompt]
        W2[执行任务]
        W3[记录 Finding 到文件]
    end

    subgraph "File System"
        F1[".sisyphus/notepads/{plan}/"]
        F2[learnings.md]
        F3[issues.md]
        F4[decisions.md]
        F5[problems.md]
    end

    A1 -->|Prompt 定义| A2
    A2 -->|包含| A3
    A3 -->|调用 task()| H1
    
    H1 -->|触发| H2
    H2 -->|修改 args| H3
    H3 -->|增强后的 prompt| W1
    
    W1 --> W2
    W2 -->|追加| W3
    W3 -->|写入| F1
    
    F1 --> F2
    F1 --> F3
    F1 --> F4
    F1 --> F5
    
    F1 -->|读取| A3
    
    style A1 fill:#e1f5fe
    style H1 fill:#f3e5f5
    style W1 fill:#e8f5e9
    style F1 fill:#fff3e0
```

## Prompt 与 Hook 分工图

```mermaid
flowchart TD
    subgraph "Prompt 驱动的行为（Soft Constraint）"
        P1[Atlas Prompt 要求:<br/>委托前读取 Notepad]
        P2[Atlas Prompt 要求:<br/>指令子 Agent 记录 Finding]
        P3[Worker Prompt 要求:<br/>追加 Finding 到 notepad]
        P4[Worker Prompt 要求:<br/>永不覆盖，只追加]
    end

    subgraph "Hook 驱动的行为（Hard Constraint）"
        H1[Hook 自动注入:<br/>NOTEPAD_DIRECTIVE]
        H2[Hook 自动注入:<br/>Read-Only Plan 提醒]
        H3[Hook 确保:<br/>每个子 Agent 都获得指令]
    end

    P1 -->|Prompt 指导| R1[模型"应该"读取]
    P2 -->|Prompt 指导| R2[模型"应该"要求记录]
    P3 -->|Prompt 指导| R3[模型"应该"追加]
    P4 -->|Prompt 指导| R4[模型"应该"不覆盖]
    
    H1 -->|Hook 强制执行| R3
    H2 -->|Hook 强制执行| R5[模型知道 Plan 只读]
    H3 -->|Hook 确保一致性| R6[所有子 Agent 统一行为]

    style P1 fill:#e3f2fd
    style P2 fill:#e3f2fd
    style P3 fill:#e3f2fd
    style P4 fill:#e3f2fd
    style H1 fill:#fce4ec
    style H2 fill:#fce4ec
    style H3 fill:#fce4ec
```

## Notepad 状态流转图

```mermaid
stateDiagram-v2
    [*] --> Empty
    
    Empty: 空的 Notepad
    Empty: mkdir 后初始化
    
    Empty --> Populated: 第一个任务完成
    
    Populated: 包含 Finding 的 Notepad
    Populated: learnings.md 有内容
    Populated: issues.md 可能有内容
    
    Populated --> Populated: 新任务追加 Finding
    Populated --> Inherited: 传递给下一个子 Agent
    
    Inherited: 通过 Prompt 注入
    Inherited: 子 Agent 的 Context 包含<br/>之前的 Finding
    
    Inherited --> Populated: 子 Agent 记录新 Finding
    
    Populated --> Completed: 所有任务完成
    
    Completed: 完整的历史记录
    Completed: 可供未来项目参考
    
    Completed --> [*]
```

## 示例：Finding 的生命周期

```mermaid
sequenceDiagram
    participant Task1 as Task 1: 分析代码
    participant FS as .sisyphus/notepads/auth-refactor/learnings.md
    participant Task2 as Task 2: 实现功能
    participant Task3 as Task 3: 添加测试

    Note over Task1: 发现：Controllers 使用 async/await
    Task1->>FS: 追加 Finding
    Note right of FS: learnings.md 内容：<br/>## Task 1<br/>- Controllers 使用 async/await

    Task2->>FS: 读取 learnings.md
    FS-->>Task2: 返回 Task 1 的 finding
    Note over Task2: 知道要使用 async/await
    
    Task2->>Task2: 发现：错误处理使用 next(new AppError())
    Task2->>FS: 追加新 Finding
    Note right of FS: learnings.md 内容：<br/>## Task 1<br/>- Controllers 使用 async/await<br/><br/>## Task 2<br/>- 错误处理使用 next(new AppError())

    Task3->>FS: 读取 learnings.md
    FS-->>Task3: 返回 Task 1+2 的所有 findings
    Note over Task3: 知道：<br/>- 使用 async/await<br/>- 使用 next(new AppError())<br/>- 按约定编写测试
```

## 对比：传统方式 vs Notepad 方式

```mermaid
flowchart LR
    subgraph "传统方式（Context Passing）"
        T1[Task 1] -->|返回结果| T2[Task 2]
        T2 -->|返回结果| T3[Task 3]
        
        %% note right of T1
        %%     问题：
        %%     - 上下文窗口限制
        %%     - 信息截断
        %%     - 找不到历史约定
        %% end note
    end

    subgraph "Notepad 方式（External Memory）"
        N1["Task 1"] -->|"写入"| NP[(Notepad)]
        NP -->|读取| N2[Task 2]
        N2 -->|写入| NP
        NP -->|读取| N3[Task 3]
        N3 -->|写入| NP
        
        %% note right of NP
        %%     "优势：
        %%     - 持久化存储
        %%     - 结构化记录
        %%     - 可复查、可调试
        %%     - 人类可读"
        %% end note
    end

    style NP fill:#e8f5e9
    style T1 fill:#ffebee
    style T2 fill:#ffebee
    style T3 fill:#ffebee
```
