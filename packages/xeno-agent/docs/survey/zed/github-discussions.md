# Zed Elicitation 相关 GitHub 讨论汇总

**调研日期**: 2026-03-06  
**搜索关键词**: elicitation, MCP elicitation, agent client protocol, agent-client-protocol

---

## 1. 直接相关 Issues

### Issue #37307 - AI: MCP requests no longer visible in Agent UI

**链接**: https://github.com/zed-industries/zed/issues/37307  
**状态**: ✅ Closed (completed)  
**创建时间**: 2025-09-01  
**关闭时间**: 2026-01-06  
**作者**: @pi3ch

#### 问题描述

在 Zed v0.201.8 版本中，观察到 MCP 工具交互显示方式的回归问题：

- **预期行为**: MCP 请求应该在 Agent UI 中显示，然后才显示响应
- **实际行为**: 
  - 请求不再显示在 Agent 面板中
  - 只显示来自 MCP 工具的最终响应
  - 这**破坏了 elicitation flows**（工具似乎停滞或超时）

#### 关键点

这是目前唯一一个明确提到 "elicitation" 的已关闭 Issue，说明：
1. Zed 曾经有某种形式的 elicitation 支持（或至少有相关的 UI 流程）
2. 该功能在某个版本中出现了回归
3. 问题已被标记为 "completed" 关闭

#### 标签

- `area:ai` - AI 相关功能
- `area:ai/mcp` - Model Context Protocol
- `state:needs repro` - 需要复现步骤

#### 评论数: 6 | 点赞数: 4

---

## 2. 直接相关 Pull Requests

**搜索结果**: 0 个 PR

使用关键词搜索 `repo:zed-industries/zed elicitation` 没有找到专门实现或修改 Elicitation 功能的 PR。

---

## 3. 相关搜索尝试

| 搜索查询 | 结果数量 | 说明 |
|---------|---------|------|
| "elicitation" | 1 | 只有 Issue #37307 |
| "MCP elicitation" | 1 | 同上 |
| "agent client protocol" | 较多（被截断） | 需要更精确搜索 |
| "agent-client-protocol" | 较多（被截断） | 需要更精确搜索 |

### MCP 相关整体讨论

虽然没有直接关于 Elicitation 的 PR，但 Zed 有活跃的 MCP 开发和讨论：

- MCP 功能在 Zed 中是一个活跃的开发领域
- 有多个关于 MCP server/tool 的 issues 和 PRs
- Elicitation 作为 MCP 的一部分，可能在未来的开发计划中

---

## 4. 观察与推断

### 4.1 当前状态

1. **无专门实现 PR**: 没有找到专门实现 ACP Elicitation 规范的 PR
2. **零星提及**: 仅在 Issue #37307 中明确提到 Elicitation
3. **文档声明**: 官方文档明确说明 Elicitation 未实现

### 4.2 可能的原因

1. **优先级**: Elicitation 可能不是当前开发优先级
2. **替代方案**: Zed 的 Tool Authorization 可能已经满足大部分需求
3. **等待规范稳定**: ACP Elicitation 规范可能还在发展中（当前是 RFD - Request for Discussion）

### 4.3 社区需求

从 Issue #37307 可以看出：
- 有用户期望使用 elicitation flows
- UI 显示问题影响了 elicitation 的用户体验
- 社区对 MCP 完整功能集有需求

---

## 5. 建议的后续跟踪

### 5.1 需要关注的领域

1. **MCP 标签 Issues**: 关注 `area:ai/mcp` 标签下的新 issue
2. **ACP crate 版本**: 监控 `agent-client-protocol` 依赖的版本更新
3. **官方 Roadmap**: 查看 Zed 官方是否有 MCP 功能路线图

### 5.2 贡献机会

根据文档说明：
> "We welcome contributions that help advance Zed's MCP feature coverage (Discovery, Sampling, Elicitation, etc)"

这是一个明确的贡献邀请，意味着：
- 团队接受 Elicitation 的实现贡献
- 有技术能力和时间的开发者可以提交 PR

---

## 6. 相关仓库

### 6.1 agentclientprotocol 组织

**地址**: https://github.com/agentclientprotocol

该组织维护 ACP 规范，包括：
- **agent-client-protocol**: 协议规范和文档
- 相关的 SDK 和实现示例

### 6.2 Model Context Protocol

**地址**: https://github.com/modelcontextprotocol

MCP 是 Elicitation 的设计基础，Zed 的 MCP 功能开发可能参考该组织的规范。

---

## 7. 总结

| 类型 | 数量 | 说明 |
|------|------|------ |
| 直接相关 Issues | 1 | Issue #37307（已关闭） |
| 直接相关 PRs | 0 | 暂无专门实现 |
| 活跃讨论 | 低 | Elicitation 不是当前热点 |
| 贡献机会 | 高 | 官方明确欢迎贡献 |

**总体评估**: Zed Elicitation 功能目前处于「未实现但接受贡献」的状态。没有正在进行的开发活动，但社区有需要，官方也明确欢迎外部贡献。
