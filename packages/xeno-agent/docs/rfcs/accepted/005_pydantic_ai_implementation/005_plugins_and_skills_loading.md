# RFC 005.3: 动态插件 & Skills 加载

---

**RFC ID**: RFC-005.3  
**标题**: 动态插件 & Skills 加载  
**状态**: DRAFT  
**作者**: Sisyphus  
**创建日期**: 2026-01-20  
**最后更新**: 2026-02-04  
**相关 RFCs**:
- [RFC 005: 系统架构](./005_system_architecture.md)
- [RFC 005.1: Hook 系统设计](./005_hooks_system_design.md)
- [RFC-0004: Configurable Skills Loading Paths](../../../../../agentpool/docs/rfcs/review/RFC-0004-configurable-skills-loading-paths.md)

---

## 目录

1. [概述](#概述)
2. [设计目标](#设计目标)
3. [术语定义](#术语定义)
4. [插件类型](#插件类型)
5. [架构设计](#架构设计)
6. [核心组件](#核心组件)
7. [Skill 加载详细设计](#skill-加载详细设计)
8. [MCP 集成](#mcp-集成)
9. [文件监视与热重载](#文件监视与热重载)
10. [配置](#配置)
11. [Hook 集成](#hook-集成)
12. [与 AgentPool Skills 的对比](#与-agentpool-skills-的对比)
13. [测试](#测试)
14. [性能优化](#性能优化)
15. [安全考虑](#安全考虑)
16. [开放问题](#开放问题)
17. [参考资料](#参考资料)

---

## 概述

本文档描述 Xeno Agent 的动态插件系统，支持以下三种插件类型的动态加载：

1. **Claude Skills**: Anthropic 官方技能包，包含提示词、资源、脚本
2. **MCP Servers**: Model Context Protocol 服务器，提供标准化工具接口
3. **Custom Python Plugins**: 自定义 Python 模块，直接扩展 Agent 功能

与 [RFC-0004](../../../../../agentpool/docs/rfcs/review/RFC-0004-configurable-skills-loading-paths.md) 中 AgentPool 的 Pool-level Skills 配置不同，Xeno Agent 的插件系统是 **Agent-level**、**运行时动态** 的，支持热重载和命名空间隔离。

---

## 设计目标

| 目标 | 描述 | 优先级 |
|------|------|--------|
| **动态发现** | 自动扫描和发现 Skills/插件，无需重启 Agent | P0 |
| **热重载** | 支持运行时重新加载更新的模块 | P0 |
| **命名空间隔离** | 不同来源的工具使用命名空间区分 (skills:, mcp:, plugin:) | P0 |
| **配置驱动** | 通过 YAML 配置管理插件加载 | P1 |
| **错误恢复** | 单个插件失败不影响整体系统 | P1 |
| **与 AgentPool 兼容** | 支持加载 AgentPool 格式的 Skills | P2 |

---

## 术语定义

| 术语 | 定义 | 对应 AgentPool 术语 |
|------|------|---------------------|
| **Skill** | 基于提示词的能力，存储为带 YAML frontmatter 的 Markdown 文件 | Skill |
| **Plugin** | 更广义的概念，包含 Skills、MCP Servers、Custom Python 模块 | - |
| **Plugin ID** | 插件唯一标识，格式 `{type}:{name}`，如 `skills:pdf_processor` | - |
| **Tool ID** | 工具唯一标识，格式 `{type}:{plugin}:{tool}`，如 `skills:pdf:extract_text` | - |
| **Scope** | Skill 来源范围，决定优先级 | Scope |
| **Hot Reload** | 文件变更时自动重新加载插件 | - |
| **Namespace** | 工具命名空间前缀，防止命名冲突 | - |

---

## 插件类型

### 1. Claude Skills

**描述**: Anthropic 官方技能包，包含提示词、资源、脚本。与 AgentPool Skills 格式兼容。

**文件结构**:
```
.claude/skills/
└── pdf_processor/
    ├── SKILL.md              # 主文件，YAML frontmatter + Markdown 内容
    ├── mcp.json             # (可选) MCP 服务器配置
    ├── scripts/             # (可选) Python 脚本
    │   └── __init__.py
    ├── references/          # (可选) 参考资料
    └── assets/              # (可选) 图片、PDF 等资源
```

**SKILL.md 示例**:
```markdown
---
name: pdf_processor
description: Extract text and analyze PDF documents
version: 1.0.0
author: Anthropic
model: anthropic/claude-opus-4-5
agent: sisyphus
subtask: false
argument-hint: "PDF file path to process"
allowed-tools: ["Read", "Write", "Bash"]

# (可选) 内嵌 MCP 配置
mcp:
  pdf-tools:
    command: npx
    args: ["@example/pdf-mcp-server"]
---

This skill helps you process PDF documents...

## Usage

Use the `extract_text` tool to extract text from PDFs.
```

**模板包装** (参考 oh-my-opencode):

Skill 内容在加载时会被自动包装为标准化格式：

```xml
<skill-instruction>
Base directory for this skill: {resolved_path}/
File references (@path) in this skill are relative to this directory.

{skill_body_content}
</skill-instruction>

<user-request>
$ARGUMENTS
</user-request>
```

注意：`$ARGUMENTS` 占位符由运行时替换，不是插件系统处理。

### 2. MCP Servers

**描述**: Model Context Protocol 服务器，提供标准化工具接口。

**配置方式**:
```yaml
# config/plugins.yaml
mcp:
  enabled: true
  servers:
    - name: filesystem
      command: ["npx", "@modelcontextprotocol/server-filesystem", "/home/user/files"]
      env:
        PATH: "/usr/local/bin:/usr/bin"
    - name: github
      command: ["npx", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_TOKEN: "${GITHUB_TOKEN}"
    - name: http-server
      type: http
      url: "http://localhost:3000/mcp"
```

**连接类型支持**:
- `stdio`: 通过子进程标准输入/输出通信
- `http`/`sse`: 通过 HTTP/SSE 连接远程服务器

### 3. Custom Python Plugins

**描述**: 自定义 Python 模块，直接扩展 Agent 功能。

**文件结构**:
```
plugins/
├── web_search.py           # 单文件插件
└── data_processor/         # 目录插件
    ├── __init__.py
    └── utils.py
```

**示例**:
```python
# plugins/web_search.py
from pydantic_ai import Tool

async def search_web(query: str) -> dict:
    """Search the web for information"""
    # 实现逻辑...
    return {"results": [...]}

# 方式 1: 通过 _PLUGIN_TOOLS 变量导出
_PLUGIN_TOOLS = [
    Tool(
        name="search_web",
        description="Search the web",
        function=search_web,
    )
]

# 方式 2: 直接导出 Tool 实例
web_search_tool = Tool(
    name="web_search",
    description="Web search tool",
    function=search_web,
)
```

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                     Xeno Agent                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Plugin Manager                              │   │
│  │  - 统一插件生命周期管理                                   │   │
│  │  - Hook 集成 (plugin.load.before/after)                  │   │
│  │  - 错误恢复和日志                                         │   │
│  └────────────────────────┬────────────────────────────────┘   │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                  Plugin Loader Interface                        │
│  - discover_plugins() → Dict[type, List[DiscoveredPlugin]]     │
│  - load_plugin(plugin_id) → LoadedPlugin                        │
│  - unload_plugin(plugin_id)                                     │
│  - reload_plugin(plugin_id)                                     │
└────┬─────────────────┬─────────────────┬────────────────────┘
     │                 │                 │
┌────▼────────┐  ┌────▼────────┐  ┌────▼────────────┐
│ SkillLoader │  │ MCPLoader   │  │ CustomPluginLoader│
│             │  │             │  │                   │
│ - discover()│  │ - discover()│  │ - discover()      │
│ - load()    │  │ - load()    │  │ - load()          │
│ - unload()  │  │ - unload()  │  │ - unload()        │
│             │  │             │  │                   │
│ 输入: Path  │  │ 输入: Config│  │ 输入: Path        │
│ 输出: Skill │  │ 输出: Server│  │ 输出: Module      │
└────┬────────┘  └────┬────────┘  └────┬────────────┘
     │                 │                 │
     └─────────────────┼─────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                  Plugin Registry                                 │
│  - register_tool(tool_definition)                                │
│  - unregister_tool(tool_id)                                      │
│  - get_tools(namespace) → List[Tool]                             │
│  - get_tool(tool_id) → Tool | None                               │
│  - list_namespaces() → List[str]                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                   Tool Name Resolution                           │
│                                                                  │
│  skills:pdf_processor:extract_text                              │
│  │      │            │                                          │
│  │      │            └─ 工具名                                  │
│  │      └─ Skill/插件名                                         │
│  └─ 命名空间 (skills/mcp/plugin)                                 │
│                                                                  │
│  简写形式:                                                       │
│  - extract_text → 在当前 namespace 中查找                        │
│  - pdf:extract_text → 在 skills namespace 中查找                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心组件

### 1. Plugin Manager

**职责**: 统一的插件管理器，协调各种 Loader 和 Registry。

```python
from typing import TypeAlias
from pathlib import Path

PluginID: TypeAlias = str  # "skills:pdf_processor"

class PluginManager:
    """插件管理器 - 统一协调各类插件的生命周期"""

    def __init__(self, config: PluginConfig, agent: "XenoAgent"):
        self.config = config
        self.agent = agent
        self.plugins: dict[PluginID, LoadedPlugin] = {}
        self.loaders: dict[str, PluginLoader] = {}
        self._discovery_cache: dict[str, Any] = {}
        self._cache_ttl: int = 300  # 5 minutes

        # 初始化加载器
        self._initialize_loaders()

    def _initialize_loaders(self):
        """初始化内置加载器"""
        self.loaders["skills"] = SkillsLoader(
            paths=self.config.skill_paths,
            include_default=self.config.skills_include_default,
        )
        self.loaders["mcp"] = MCPLoader(
            servers=self.config.mcp_servers,
        )
        self.loaders["custom"] = CustomPluginLoader(
            paths=self.config.custom_plugin_paths,
        )

    async def discover_plugins(
        self,
        use_cache: bool = True,
    ) -> dict[str, list[DiscoveredPlugin]]:
        """
        发现所有可用插件

        Args:
            use_cache: 是否使用缓存

        Returns:
            {loader_type: [plugins]}
        """
        cache_key = "plugins_discovery"

        # 检查缓存
        if use_cache and cache_key in self._discovery_cache:
            cached_time, cached_data = self._discovery_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data

        # 重新发现
        discovered = {}
        for loader_type, loader in self.loaders.items():
            try:
                plugins = await loader.discover()
                discovered[loader_type] = plugins
                logger.info(f"Discovered {len(plugins)} {loader_type} plugins")
            except Exception as e:
                logger.error(f"Failed to discover {loader_type} plugins: {e}")
                discovered[loader_type] = []

        # 更新缓存
        self._discovery_cache[cache_key] = (time.time(), discovered)
        return discovered

    async def load_plugin(
        self,
        plugin_id: PluginID,
    ) -> LoadedPlugin:
        """
        加载插件

        Args:
            plugin_id: 插件 ID (e.g., "skills:pdf_processor")

        Raises:
            PluginNotFoundError: 插件不存在
            PluginLoadError: 插件加载失败
        """
        # 解析插件类型和标识
        if ":" not in plugin_id:
            raise ValueError(f"Invalid plugin_id format: {plugin_id}")

        loader_type, plugin_identifier = plugin_id.split(":", 1)

        if loader_type not in self.loaders:
            raise PluginNotFoundError(f"Unknown loader type: {loader_type}")

        # 触发 before hook
        await self.agent.hooks.execute_before(
            event="plugin.load.before",
            ctx=HookContext(
                agent=self.agent,
                event="plugin.load.before",
                metadata={
                    "plugin_id": plugin_id,
                    "loader_type": loader_type,
                }
            )
        )

        try:
            # 加载插件
            loader = self.loaders[loader_type]
            loaded_plugin = await loader.load(plugin_identifier)

            # 注册工具到 registry
            for tool in loaded_plugin.tools:
                # 添加完整命名空间前缀
                tool.name = f"{loader_type}:{plugin_identifier}:{tool.name}"
                self.agent.tool_registry.register_tool(tool)

            # 保存到内存
            self.plugins[plugin_id] = loaded_plugin

            # 触发 after hook
            await self.agent.hooks.execute_after(
                event="plugin.load.after",
                ctx=HookContext(
                    agent=self.agent,
                    event="plugin.load.after",
                    metadata={
                        "plugin_id": plugin_id,
                        "plugin": loaded_plugin,
                    }
                )
            )

            logger.info(f"Loaded plugin: {plugin_id} with {len(loaded_plugin.tools)} tools")
            return loaded_plugin

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}: {e}")
            raise PluginLoadError(f"Failed to load {plugin_id}: {e}") from e

    async def unload_plugin(self, plugin_id: PluginID) -> None:
        """卸载插件"""
        if plugin_id not in self.plugins:
            logger.warning(f"Plugin not found: {plugin_id}")
            return

        loaded_plugin = self.plugins[plugin_id]
        loader_type = plugin_id.split(":", 1)[0]

        # 触发 before hook
        await self.agent.hooks.execute_before(
            event="plugin.unload.before",
            ctx=HookContext(
                agent=self.agent,
                event="plugin.unload.before",
                metadata={"plugin_id": plugin_id}
            )
        )

        try:
            # 从 registry 移除工具
            for tool in loaded_plugin.tools:
                self.agent.tool_registry.unregister_tool(tool.name)

            # 卸载加载器资源
            await self.loaders[loader_type].unload(loaded_plugin)

            # 移除引用
            del self.plugins[plugin_id]

            # 触发 after hook
            await self.agent.hooks.execute_after(
                event="plugin.unload.after",
                ctx=HookContext(
                    agent=self.agent,
                    event="plugin.unload.after",
                    metadata={"plugin_id": plugin_id}
                )
            )

            logger.info(f"Unloaded plugin: {plugin_id}")

        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}")
            # 继续清理，即使出错

    async def reload_plugin(self, plugin_id: PluginID) -> LoadedPlugin:
        """重新加载插件"""
        await self.unload_plugin(plugin_id)
        return await self.load_plugin(plugin_id)

    async def load_all_auto_load(self) -> list[PluginID]:
        """加载配置中标记为 auto_load 的所有插件"""
        loaded = []

        # Skills
        if self.config.skills_auto_load:
            for skill_name in self.config.skills_auto_load:
                try:
                    await self.load_plugin(f"skills:{skill_name}")
                    loaded.append(f"skills:{skill_name}")
                except Exception as e:
                    logger.error(f"Auto-load failed for skill {skill_name}: {e}")

        # MCP servers
        if self.config.mcp_auto_load:
            for server_name in self.config.mcp_auto_load:
                try:
                    await self.load_plugin(f"mcp:{server_name}")
                    loaded.append(f"mcp:{server_name}")
                except Exception as e:
                    logger.error(f"Auto-load failed for MCP server {server_name}: {e}")

        # Custom plugins
        if self.config.custom_auto_load:
            for plugin_name in self.config.custom_auto_load:
                try:
                    await self.load_plugin(f"custom:{plugin_name}")
                    loaded.append(f"custom:{plugin_name}")
                except Exception as e:
                    logger.error(f"Auto-load failed for custom plugin {plugin_name}: {e}")

        return loaded
```

### 2. Skills Loader

**职责**: Claude Skills 的发现和加载。兼容 AgentPool Skills 格式。

```python
import yaml
import frontmatter
from pathlib import Path
from typing import Literal

SkillScope = Literal[
    "builtin",          # 内置 Skills (优先级: 1)
    "config",           # 配置定义的 Skills (优先级: 2)
    "user",             # ~/.claude/skills/ (优先级: 3)
    "opencode",         # ~/.config/opencode/skills/ (优先级: 4)
    "project",          # .claude/skills/ (优先级: 5)
    "opencode-project", # .opencode/skills/ (优先级: 6)
]

class DiscoveredSkill:
    """发现的 Skill（未加载）"""
    def __init__(
        self,
        path: Path,
        metadata: dict,
        content: str,
        scope: SkillScope,
        resolved_path: Path | None = None,
    ):
        self.path = path
        self.resolved_path = resolved_path or path
        self.name = metadata.get("name", path.parent.name)
        self.description = metadata.get("description", "")
        self.version = metadata.get("version", "1.0.0")
        self.author = metadata.get("author", "Unknown")
        self.metadata = metadata
        self.content = content
        self.scope = scope

class LoadedSkill:
    """已加载的 Skill"""
    def __init__(
        self,
        discovered: DiscoveredSkill,
        tools: list[Tool],
        mcp_config: dict | None = None,
    ):
        self.discovered = discovered
        self.tools = tools
        self.mcp_config = mcp_config

class SkillsLoader(PluginLoader):
    """Claude Skills 加载器 - 兼容 AgentPool Skills 格式"""

    # 与 RFC-0004 一致的默认路径
    DEFAULT_PATHS = [
        "~/.claude/skills",      # user scope
        ".claude/skills",        # project scope
        "~/.config/opencode/skills",  # opencode scope
        ".opencode/skills",      # opencode-project scope
    ]

    def __init__(
        self,
        paths: list[Path] | None = None,
        include_default: bool = True,
    ):
        self.custom_paths = paths or []
        self.include_default = include_default

    async def discover(self) -> list[DiscoveredSkill]:
        """
        发现 Skills

        流程:
        1. 扫描所有路径，查找 SKILL.md 或 {name}.md 文件
        2. 解析 frontmatter YAML 获取元数据
        3. 返回 DiscoveredSkill 列表

        支持的文件结构:
        - skill_dir/SKILL.md
        - skill_dir/skill_name.md
        - skills/skill_name.md (flat)
        """
        discovered = []
        seen_names = set()

        # 确定要扫描的路径
        paths_to_scan = []

        # 自定义路径优先
        for path in self.custom_paths:
            paths_to_scan.append((path, "config"))

        # 默认路径
        if self.include_default:
            for path_str in self.DEFAULT_PATHS:
                path = Path(path_str).expanduser()
                scope = self._get_scope_for_path(path_str)
                paths_to_scan.append((path, scope))

        # 定义允许的根目录（用于路径验证）
        allowed_roots = [p.resolve() for p, _ in paths_to_scan if p.exists()]
        
        # 使用字典跟踪已发现的 skill，键为 (scope_priority, -path_index)
        seen_skills: dict[str, tuple[DiscoveredSkill, int, int]] = {}  # name -> (skill, scope_priority, path_index)
        
        for path_index, (path, scope) in enumerate(paths_to_scan):
            # 验证路径在允许的根目录内
            if not self._validate_path(path, allowed_roots):
                logger.warning(f"拒绝扫描路径 {path}: 不在允许的根目录内或包含路径遍历")
                continue
            
            if not path.exists():
                if scope == "config":
                    logger.warning(f"Custom skills directory not found: {path}")
                else:
                    logger.debug(f"Default skills directory not found: {path}")
                continue

            skills = await self._scan_directory(path, scope, allowed_roots)

            # 优先级处理：高优先级数字覆盖低优先级数字
            # 同 scope 内，先扫描的路径（path_index 小）优先
            scope_priority = SCOPE_PRIORITY[scope]
            for skill in skills:
                existing = seen_skills.get(skill.name)
                if existing:
                    existing_priority, existing_path_idx = existing[1], existing[2]
                    # 比较 (scope_priority, -path_index)，值大的优先级高
                    new_score = (scope_priority, -path_index)
                    existing_score = (existing_priority, -existing_path_idx)
                    if new_score > existing_score:
                        logger.debug(f"Skill '{skill.name}' 被更高优先级版本覆盖: "
                                   f"{scope}(priority={scope_priority}, path_index={path_index}) > "
                                   f"{existing[0].scope}(priority={existing_priority}, path_index={existing_path_idx})")
                        seen_skills[skill.name] = (skill, scope_priority, path_index)
                    else:
                        logger.debug(f"Skill '{skill.name}' 忽略低优先级版本: "
                                   f"{scope}(priority={scope_priority}, path_index={path_index}) <= "
                                   f"{existing[0].scope}(priority={existing_priority}, path_index={existing_path_idx})")
                else:
                    seen_skills[skill.name] = (skill, scope_priority, path_index)

        return [s[0] for s in seen_skills.values()]

    def _get_scope_for_path(self, path_str: str) -> SkillScope:
        """根据路径确定 scope"""
        if ".opencode" in path_str:
            return "opencode-project" if path_str.startswith(".") else "opencode"
        return "project" if path_str.startswith(".") else "user"

    def _validate_path(self, path: Path, allowed_roots: list[Path]) -> bool:
        """
        验证路径在允许的根目录内，防止路径遍历攻击
        
        Args:
            path: 要验证的路径
            allowed_roots: 允许的根目录列表
            
        Returns:
            True if safe, False if potentially malicious
        """
        import re
        
        try:
            # 1. 解析为绝对路径
            resolved = path.resolve()
        except Exception:
            return False
        
        # 2. 检查路径遍历模式
        path_str = str(path)
        if ".." in path_str or "../" in path_str or "..\\" in path_str:
            return False
        
        # 3. 检查 URL 编码的遍历尝试
        if re.search(r'%2e%2e%2f', path_str, re.IGNORECASE):
            return False
        
        # 4. 验证在允许的根目录内
        for root in allowed_roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        
        # 5. 检查是否为允许的根目录本身
        for root in allowed_roots:
            if resolved == root:
                return True
        
        return False

    async def _scan_directory(
        self,
        skills_dir: Path,
        scope: SkillScope,
        allowed_roots: list[Path],
    ) -> list[DiscoveredSkill]:
        """扫描目录发现 Skills"""
        skills = []

        try:
            entries = list(skills_dir.iterdir())
        except Exception as e:
            logger.error(f"Failed to read directory {skills_dir}: {e}")
            return skills

        for entry in entries:
            if entry.name.startswith("."):
                continue

            # 解析符号链接并验证安全性
            resolved_entry = entry.resolve() if entry.is_symlink() else entry
            
            # 验证解析后的路径在允许的根目录内
            if not self._validate_path(resolved_entry, allowed_roots):
                logger.warning(f"拒绝加载 skill: 路径 {resolved_entry} 在允许根目录之外或包含路径遍历")
                continue

            # 目录结构: skill_dir/SKILL.md 或 skill_dir/skill_name.md
            if resolved_entry.is_dir():
                skill = await self._try_load_from_dir(resolved_entry, scope)
                if skill:
                    skills.append(skill)
                    continue

            # 直接 .md 文件: skills/skill_name.md
            if resolved_entry.is_file() and resolved_entry.suffix == ".md":
                skill = await self._try_load_from_file(resolved_entry, scope)
                if skill:
                    skills.append(skill)

        return skills

    async def _try_load_from_dir(
        self,
        skill_dir: Path,
        scope: SkillScope,
    ) -> DiscoveredSkill | None:
        """尝试从目录加载 Skill"""
        dir_name = skill_dir.name

        # 尝试 SKILL.md
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            return await self._parse_skill_file(skill_md, skill_dir, dir_name, scope)

        # 尝试 {name}.md
        named_md = skill_dir / f"{dir_name}.md"
        if named_md.exists():
            return await self._parse_skill_file(named_md, skill_dir, dir_name, scope)

        return None

    async def _try_load_from_file(
        self,
        skill_file: Path,
        scope: SkillScope,
    ) -> DiscoveredSkill | None:
        """尝试从文件加载 Skill"""
        skill_name = skill_file.stem
        return await self._parse_skill_file(skill_file, skill_file.parent, skill_name, scope)

    async def _parse_skill_file(
        self,
        skill_path: Path,
        resolved_path: Path,
        default_name: str,
        scope: SkillScope,
    ) -> DiscoveredSkill | None:
        """解析 Skill 文件"""
        try:
            content = skill_path.read_text(encoding="utf-8")
            data = frontmatter.loads(content)

            return DiscoveredSkill(
                path=skill_path,
                metadata=data.metadata,
                content=data.content,
                scope=scope,
                resolved_path=resolved_path,
            )
        except Exception as e:
            logger.error(f"Failed to parse skill file {skill_path}: {e}")
            return None

    async def load(self, skill_name: str) -> LoadedSkill:
        """
        加载 Skill

        流程:
        1. 查找 Skill
        2. 解析 SKILL.md
        3. 加载 mcp.json (如果存在)
        4. 加载 scripts/ 中的 Python 脚本
        5. 将逻辑转换为 Pydantic AI Tools
        """
        # 查找 Skill
        discovered_list = await self.discover()
        discovered = next((s for s in discovered_list if s.name == skill_name), None)

        if not discovered:
            raise SkillNotFoundError(f"Skill not found: {skill_name}")

        skill_dir = discovered.resolved_path

        # 加载 MCP 配置
        mcp_config = await self._load_mcp_config(skill_dir)

        # 从 content 中提取工具定义
        tools = await self._extract_tools_from_skill(discovered)

        return LoadedSkill(
            discovered=discovered,
            tools=tools,
            mcp_config=mcp_config,
        )

    async def _load_mcp_config(self, skill_dir: Path) -> dict | None:
        """加载 MCP 配置 (mcp.json 或 frontmatter)"""
        # 1. 尝试 mcp.json
        mcp_json = skill_dir / "mcp.json"
        if mcp_json.exists():
            try:
                return json.loads(mcp_json.read_text())
            except Exception as e:
                logger.error(f"Failed to parse mcp.json: {e}")

        # 2. 尝试从 frontmatter 解析 (已在 discover 中完成)
        # 这里可以返回 None，因为 mcp 配置会在 Skill 使用时动态处理
        return None

    async def _extract_tools_from_skill(
        self,
        discovered: DiscoveredSkill,
    ) -> list[Tool]:
        """
        从 Skill 提取工具定义

        策略:
        1. 查找 scripts/ 目录中的 Python 脚本
        2. 解析 Markdown 中的工具声明
        3. 注册为 Pydantic AI Tools
        """
        tools = []
        skill_dir = discovered.resolved_path

        # 加载 scripts/
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            try:
                module = self._load_module_from_scripts(scripts_dir)
                if hasattr(module, "_PLUGIN_TOOLS"):
                    tools.extend(module._PLUGIN_TOOLS)
            except Exception as e:
                logger.error(f"Failed to load scripts from {scripts_dir}: {e}")

        # 解析 content 中的工具声明 (可选)
        # 示例 Markdown 格式:
        # ```tool
        # name: extract_text
        # description: Extract text from PDF
        # parameters: ...
        # ```
        tools_from_markdown = await self._parse_tool_blocks(discovered.content)
        tools.extend(tools_from_markdown)

        return tools

    def _load_module_from_scripts(self, scripts_dir: Path) -> Any:
        """动态加载 Python 模块"""
        import importlib.util

        init_file = scripts_dir / "__init__.py"
        if not init_file.exists():
            raise SkillScriptError(f"No __init__.py found in {scripts_dir}")

        spec = importlib.util.spec_from_file_location(
            f"skill_scripts.{scripts_dir.parent.name}",
            init_file,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module

    async def _parse_tool_blocks(self, content: str) -> list[Tool]:
        """解析 Markdown 中的工具声明块"""
        tools = []
        # 使用正则或其他方式解析 ```tool 代码块
        # TODO: 实现具体的解析逻辑
        return tools

    async def unload(self, skill: LoadedSkill) -> None:
        """卸载 Skill"""
        # 清理缓存的模块等
        pass
```

### 3. MCP Loader

**职责**: MCP 服务器的发现和工具加载。

```python
from pydantic_ai.mcp import MCPServerStdio, MCPServerHTTP
from typing import Literal

ConnectionType = Literal["stdio", "http", "sse"]

class MCPServerConfig(TypedDict):
    name: str
    type: ConnectionType  # "stdio" | "http" | "sse"
    # For stdio
    command: list[str] | None
    env: dict[str, str] | None
    # For http/sse
    url: str | None

class DiscoveredMCPServer:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.name = config["name"]

class LoadedMCPServer:
    def __init__(
        self,
        server: MCPServerStdio | MCPServerHTTP,
        tools: list[Tool],
        config: MCPServerConfig,
    ):
        self.server = server
        self.tools = tools
        self.config = config
        self.process: asyncio.subprocess.Process | None = None
        self._health_check_task: asyncio.Task | None = None
        self._last_health_check: float = 0.0
        self._read_timeout: float = 5 * 60  # 5 minutes default
        
    async def start_health_monitoring(self, check_interval: float = 60.0):
        """启动健康检查监控"""
        self._health_check_task = asyncio.create_task(
            self._health_check_loop(check_interval)
        )
        
    async def stop_health_monitoring(self):
        """停止健康检查监控"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            
    async def _health_check_loop(self, check_interval: float):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(check_interval)
                if not await self._is_healthy():
                    logger.error(f"MCP server {self.config['name']} unhealthy, will reconnect")
                    # 触发重连逻辑（由调用方处理）
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check failed for {self.config['name']}: {e}")
                
    async def _is_healthy(self) -> bool:
        """检查服务器健康状态"""
        try:
            # 检查进程是否存活（stdio 类型）
            if self.process:
                if self.process.returncode is not None:
                    return False
                    
            # 检查连接状态
            if hasattr(self.server, 'is_connected'):
                if not self.server.is_connected():
                    return False
                    
            # 尝试列出工具作为 ping（带超时）
            await asyncio.wait_for(
                self.server.list_tools(),
                timeout=10.0
            )
            self._last_health_check = time.time()
            return True
        except Exception:
            return False
            
    async def ensure_alive(self) -> bool:
        """确保服务器存活，如果不存活返回 False"""
        return await self._is_healthy()

class MCPLoader(PluginLoader):
    """MCP 服务器加载器"""

    def __init__(self, servers: list[MCPServerConfig]):
        self.servers = {s["name"]: s for s in servers}

    async def discover(self) -> list[DiscoveredMCPServer]:
        """发现 MCP 服务器（配置驱动）"""
        return [
            DiscoveredMCPServer(config)
            for config in self.servers.values()
        ]

    def _get_connection_type(self, config: MCPServerConfig) -> ConnectionType:
        """确定连接类型"""
        explicit_type = config.get("type")
        if explicit_type in ("http", "sse"):
            return explicit_type
        if explicit_type == "stdio":
            return "stdio"

        # 从字段推断
        if config.get("url"):
            return "http"
        if config.get("command"):
            return "stdio"

        raise ValueError(f"Cannot determine connection type for server {config['name']}")

    async def load(self, server_name: str) -> LoadedMCPServer:
        """
        加载 MCP 服务器

        流程:
        1. 启动 MCP 服务器进程或建立 HTTP 连接
        2. 列出可用工具
        3. 转换为 Pydantic AI Tools
        """
        config = self.servers.get(server_name)
        if not config:
            raise MCPServerNotFoundError(server_name)

        connection_type = self._get_connection_type(config)

        if connection_type == "stdio":
            return await self._load_stdio_server(server_name, config)
        else:
            return await self._load_http_server(server_name, config)

    async def _load_stdio_server(
        self,
        server_name: str,
        config: MCPServerConfig,
    ) -> LoadedMCPServer:
        """加载 stdio 类型的 MCP 服务器"""
        # 启动 MCP 服务器进程
        process = await asyncio.create_subprocess_exec(
            *config["command"],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **(config.get("env") or {})},
        )

        # 创建 MCPServerStdio 连接
        server = MCPServerStdio(process)

        # 等待就绪
        await server.__aenter__()

        # 列出工具
        tools_list = await server.list_tools()

        # 转换为 Pydantic AI Tools
        tools = []
        for mcp_tool in tools_list:
            tool = Tool(
                name=mcp_tool.name,
                description=mcp_tool.description,
                parameters_json_schema=mcp_tool.input_schema,
            )
            tools.append(tool)

        loaded = LoadedMCPServer(
            server=server,
            tools=tools,
            config=config,
        )
        loaded.process = process

        return loaded

    async def _load_http_server(
        self,
        server_name: str,
        config: MCPServerConfig,
    ) -> LoadedMCPServer:
        """加载 HTTP/SSE 类型的 MCP 服务器"""
        # 创建 HTTP 连接
        server = MCPServerHTTP(config["url"])

        # 等待就绪
        await server.__aenter__()

        # 列出工具
        tools_list = await server.list_tools()

        # 转换为 Pydantic AI Tools
        tools = [
            Tool(
                name=mcp_tool.name,
                description=mcp_tool.description,
                parameters_json_schema=mcp_tool.input_schema,
            )
            for mcp_tool in tools_list
        ]

        return LoadedMCPServer(
            server=server,
            tools=tools,
            config=config,
        )

    async def unload(self, server: LoadedMCPServer) -> None:
        """卸载 MCP 服务器"""
        if server.server:
            await server.server.__aexit__(None, None, None)

        if server.process:
            server.process.terminate()
            try:
                await asyncio.wait_for(server.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                server.process.kill()
                await server.process.wait()
```

### 4. Custom Plugin Loader

```python
class DiscoveredCustomPlugin:
    def __init__(self, path: Path, module_name: str):
        self.path = path
        self.module_name = module_name

class LoadedCustomPlugin:
    def __init__(
        self,
        module: Any,
        tools: list[Tool],
        path: Path,
    ):
        self.module = module
        self.tools = tools
        self.path = path

class CustomPluginLoader(PluginLoader):
    """自定义插件加载器"""

    def __init__(self, paths: list[Path]):
        self.paths = paths

    async def discover(self) -> list[DiscoveredCustomPlugin]:
        """
        发现自定义插件

        扫描路径:
        - plugins/*.py
        - plugins/*/__init__.py
        """
        discovered = []

        for path in self.paths:
            plugins_dir = path / "plugins"
            if not plugins_dir.exists():
                continue

            # 单文件插件
            for py_file in plugins_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue

                module_name = py_file.stem
                discovered.append(
                    DiscoveredCustomPlugin(py_file, module_name)
                )

            # 目录插件
            for plugin_dir in plugins_dir.iterdir():
                if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
                    continue

                init_file = plugin_dir / "__init__.py"
                if init_file.exists():
                    module_name = plugin_dir.name
                    discovered.append(
                        DiscoveredCustomPlugin(plugin_dir, module_name)
                    )

        return discovered

    async def load(self, plugin_name: str) -> LoadedCustomPlugin:
        """加载自定义插件"""
        discovered_list = await self.discover()
        discovered = next(
            (p for p in discovered_list if p.module_name == plugin_name),
            None
        )

        if not discovered:
            raise CustomPluginNotFoundError(plugin_name)

        # 动态导入模块
        module = self._load_module(discovered.path)

        # 提取工具
        tools = []

        # 方法 1: 从 _PLUGIN_TOOLS 变量提取
        if hasattr(module, "_PLUGIN_TOOLS"):
            tools.extend(module._PLUGIN_TOOLS)

        # 方法 2: 扫描所有导出的 Tool
        for name, obj in vars(module).items():
            if isinstance(obj, Tool):
                tools.append(obj)

        return LoadedCustomPlugin(
            module=module,
            tools=tools,
            path=discovered.path,
        )

    def _load_module(self, path: Path) -> Any:
        """动态加载模块"""
        import importlib.util
        import sys

        if path.is_dir():
            init_file = path / "__init__.py"
            module_name = f"plugins.{path.name}"
            spec = importlib.util.spec_from_file_location(
                module_name,
                init_file,
            )
        else:
            module_name = f"plugins.{path.stem}"
            spec = importlib.util.spec_from_file_location(
                module_name,
                path,
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return module

    async def unload(self, plugin: LoadedCustomPlugin) -> None:
        """卸载插件"""
        import sys

        # 移除模块引用
        module_name = plugin.module.__name__
        if module_name in sys.modules:
            del sys.modules[module_name]
```

---

## Skill 加载详细设计

### Skill 来源优先级

与 AgentPool 保持一致，使用 scope-based 优先级。注意：**优先级数字越高，优先级越高**（6 覆盖 1）。

| 优先级数字 | Scope | 路径 | 描述 | 覆盖能力 |
|------------|-------|------|------|----------|
| 6 (最高) | `opencode-project` | `.opencode/skills/` | OpenCode 项目级 Skills | 覆盖所有其他 scope |
| 5 | `project` | `.claude/skills/` | 项目级 Skills | 覆盖 user/opencode/config/builtin |
| 4 | `opencode` | `~/.config/opencode/skills/` | OpenCode 全局 Skills | 覆盖 user/config/builtin |
| 3 | `user` | `~/.claude/skills/` | 用户全局 Skills | 覆盖 config/builtin |
| 2 | `config` | `config.skills.paths` | 配置指定的路径 | 覆盖 builtin |
| 1 (最低) | `builtin` | 代码内置 | 内置 Skills | 最低优先级 |

**优先级规则**: 
- **高优先级数字覆盖低优先级数字** (6 > 5 > 4 > 3 > 2 > 1)
- 例如：`opencode-project` (6) 的 skill 会覆盖 `builtin` (1) 的同名 skill

#### 同 Scope 冲突解决

当多个路径属于同一 scope 时，按以下规则解决：

1. **自定义路径 (`config` scope)**: 列表顺序，**第一个路径优先** (first path wins)
2. **默认路径**: 按固定顺序扫描，后扫描的覆盖先扫描的

**示例**:
```yaml
skills:
  paths:
    - "./project-skills-a"  # 如果冲突，这个路径的 skill 优先
    - "./project-skills-b"
```

**实现逻辑**:
```python
# 同 scope 内，记录每个 skill 第一次出现的路径
for path_index, (path, scope) in enumerate(paths_to_scan):
    skills = await self._scan_directory(path, scope)
    for skill in skills:
        existing = seen_skills.get(skill.name)
        if existing:
            # 比较优先级: (scope_priority, -path_index)
            # path_index 越小（越靠前），优先级越高
            existing_priority = (SCOPE_PRIORITY[existing.scope], -existing.path_index)
            new_priority = (SCOPE_PRIORITY[skill.scope], -path_index)
            if new_priority > existing_priority:
                seen_skills[skill.name] = skill
        else:
            skill.path_index = path_index  # 记录路径索引
            seen_skills[skill.name] = skill
```

### Skill 内容解析

**Frontmatter 字段**:

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `name` | string | No | Skill 名称（默认目录名） |
| `description` | string | No | 描述 |
| `version` | string | No | 版本 |
| `author` | string | No | 作者 |
| `model` | string | No | 偏好模型 |
| `agent` | string | No | 限制特定 Agent 使用 |
| `subtask` | boolean | No | 是否为子任务 Skill |
| `argument-hint` | string | No | 参数使用提示 |
| `license` | string | No | 许可证 |
| `compatibility` | string | No | 兼容性说明 |
| `metadata` | object | No | 自定义元数据 |
| `allowed-tools` | string[] | No | 允许使用的工具白名单 |
| `mcp` | object | No | 内嵌 MCP 配置 |

### Skill 模板包装

参考 oh-my-opencode 的实现，Skill 内容会被包装为标准化格式：

```python
def wrap_skill_template(body: str, resolved_path: Path) -> str:
    """包装 Skill 内容为标准化格式"""
    return f"""<skill-instruction>
Base directory for this skill: {resolved_path}/
File references (@path) in this skill are relative to this directory.

{body.strip()}
</skill-instruction>

<user-request>
$ARGUMENTS
</user-request>"""
```

---

## MCP 集成

### Skill 内嵌 MCP 配置

Skill 可以通过两种方式配置 MCP 服务器：

**方式 1: Frontmatter 内嵌**
```yaml
---
mcp:
  pdf-tools:
    command: npx
    args: ["@example/pdf-mcp-server"]
    env:
      API_KEY: ${PDF_API_KEY}
---
```

**方式 2: 独立的 mcp.json 文件**
```json
{
  "mcpServers": {
    "pdf-tools": {
      "command": "npx",
      "args": ["@example/pdf-mcp-server"]
    }
  }
}
```

### MCP 工具调用流程

```
Agent 执行 Skill
    │
    ├─► Skill 包含 mcpConfig
    │   │
    │   ├─► PluginManager 识别 MCP 配置
    │   │
    │   ├─► MCPLoader.getOrCreateClient()
    │   │   │
    │   │   ├─► 检查缓存 (sessionID:skillName:serverName)
    │   │   │
    │   │   └─► 创建新连接
    │   │       ├─► 展开环境变量 ${VAR}
    │   │       ├─► stdio: 启动子进程
    │   │       └─► http: HTTP 连接
    │   │
    │   ├─► 列出 tools/resources/prompts
    │   │
    │   └─► 格式化为 markdown 附加到 Skill 输出
    │
    └─► 返回完整 Skill 内容
```

---

## 文件监视与热重载

### File Watcher

```python
from watchfiles import awatch

class PluginFileWatcher:
    """插件文件监视器，支持热重载"""

    def __init__(self, manager: PluginManager, paths: list[Path]):
        self.manager = manager
        self.paths = paths
        self.is_running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """启动文件监视"""
        self.is_running = True
        self._task = asyncio.create_task(self._watch_loop())

    async def stop(self):
        """停止文件监视"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _watch_loop(self):
        """监视循环"""
        async for changes in awatch(*self.paths, debounce=100):
            if not self.is_running:
                break
            await self._handle_changes(changes)

    async def _handle_changes(self, changes: set[tuple[Change, str]]):
        """
        处理文件变化

        Changes:
            (Change.added, path) - 创建
            (Change.modified, path) - 修改
            (Change.deleted, path) - 删除
        """
        for change_type, path_str in changes:
            path = Path(path_str)

            # 判断是否是插件文件
            plugin_id = self._identify_plugin(path)
            if not plugin_id:
                continue

            try:
                if change_type == Change.added:
                    logger.info(f"Plugin created: {path}")
                    await self.manager.load_plugin(plugin_id)

                elif change_type == Change.modified:
                    logger.info(f"Plugin modified: {path}")
                    await self.manager.reload_plugin(plugin_id)

                elif change_type == Change.deleted:
                    logger.info(f"Plugin deleted: {path}")
                    await self.manager.unload_plugin(plugin_id)

            except Exception as e:
                logger.error(f"Failed to handle file change for {plugin_id}: {e}")

    # 临时文件模式（需要过滤）
    TEMP_FILE_PATTERNS = {
        '*.swp',        # Vim swap files
        '*.tmp',        # Temporary files
        '*~',           # Backup files
        '*.bak',        # Backup files
        '.DS_Store',    # macOS metadata
        'Thumbs.db',    # Windows thumbnails
        '*.pyc',        # Python bytecode
        '__pycache__',  # Python cache directory
    }

    def _is_temp_file(self, path: Path) -> bool:
        """检查是否为临时文件"""
        path_str = str(path).lower()
        return any(
            path_str.endswith(pattern.lower().lstrip('*'))
            for pattern in self.TEMP_FILE_PATTERNS
        ) or any(
            pattern.strip('*') in path_str
            for pattern in self.TEMP_FILE_PATTERNS
            if '*' in pattern
        )

    def _identify_plugin(self, path: Path) -> str | None:
        """
        识别文件所属的插件

        Returns:
            plugin_id (e.g., "skills:pdf_processor") or None
        """
        # 过滤临时文件
        if self._is_temp_file(path):
            return None

        path_str = str(path)

        # 匹配 Skill
        if "SKILL.md" in path_str or ".md" in path_str:
            # 从路径推断 skill 名称
            if ".claude/skills" in path_str or ".opencode/skills" in path_str:
                skill_name = path.parent.name
                return f"skills:{skill_name}"

        # 匹配 Custom Plugin
        if "plugins" in path_str and path_str.endswith(".py"):
            plugin_name = path.stem
            return f"custom:{plugin_name}"

        # MCP 服务器不通过文件监视触发（配置驱动）
        return None
```

---

## 配置

### 插件配置 Schema

```yaml
# config/plugins.yaml

# Skills 配置
skills:
  enabled: true
  # 自定义路径（与 RFC-0004 兼容）
  paths:
    - "./project-skills"
    - "/shared/company-skills"
  # 是否包含默认路径
  include_default: true
  # 自动加载列表
  auto_load:
    - "pdf_processor"
    - "xlsx_processor"
  # 热重载
  hot_reload: true
  watch: true

# MCP 服务器配置
mcp:
  enabled: true
  auto_load:
    - "filesystem"
    - "github"
  servers:
    - name: "filesystem"
      type: "stdio"
      command: ["npx", "@modelcontextprotocol/server-filesystem", "/home/user/files"]
      env:
        PATH: "/usr/local/bin:/usr/bin"
    - name: "github"
      type: "stdio"
      command: ["npx", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_TOKEN: "${GITHUB_TOKEN}"
    - name: "remote-server"
      type: "http"
      url: "http://localhost:3000/mcp"

# 自定义插件配置
custom:
  enabled: true
  paths:
    - "plugins/"
  auto_load:
    - "web_search"
  hot_reload: true

# 全局配置
global:
  timeout: 30.0
  retry:
    max_attempts: 3
    delay: 1.0
```

### 配置示例

**示例 1: 项目专属 Skills（禁用默认路径）**
```yaml
skills:
  paths:
    - "./skills"
  include_default: false
  auto_load:
    - "project-helper"
```

**示例 2: 共享组织 Skills + 项目 Skills**
```yaml
skills:
  paths:
    - "/shared/company-skills"
    - "./project-specific-skills"
  include_default: true
```

**示例 3: 仅 MCP 服务器**
```yaml
skills:
  enabled: false

mcp:
  enabled: true
  servers:
    - name: "local-tools"
      command: ["python", "mcp_server.py"]
```

---

## Hook 集成

### 插件生命周期 Hooks

```python
# Plugin 加载前
await hooks.execute_before(
    event="plugin.load.before",
    ctx=HookContext(
        agent=agent,
        event="plugin.load.before",
        metadata={
            "plugin_id": plugin_id,
            "loader_type": loader_type,
        }
    )
)

# Plugin 加载后
await hooks.execute_after(
    event="plugin.load.after",
    ctx=HookContext(
        agent=agent,
        event="plugin.load.after",
        metadata={
            "plugin_id": plugin_id,
            "plugin": loaded_plugin,
        }
    )
)

# Plugin 卸载前
await hooks.execute_before(
    event="plugin.unload.before",
    ctx=HookContext(
        agent=agent,
        event="plugin.unload.before",
        metadata={"plugin_id": plugin_id}
    )
)

# Plugin 卸载后
await hooks.execute_after(
    event="plugin.unload.after",
    ctx=HookContext(
        agent=agent,
        event="plugin.unload.after",
        metadata={"plugin_id": plugin_id}
    )
)

# Skill 工具调用前
if tool_name.startswith("skills:"):
    await hooks.execute_before(
        event="skill.tool.before",
        ctx=HookContext(
            agent=agent,
            event="skill.tool.before",
            tool_name=tool_name,
            tool_args=args,
            metadata={
                "skill_name": skill_name,
            }
        )
    )
```

---

## 工具名冲突处理

### 冲突场景

当多个插件定义相同工具名时，可能发生以下冲突：

1. **同插件内冲突**: 一个 Skill 内的两个工具同名
2. **跨插件冲突**: Skill A 和 Skill B 都定义了 `extract_text`
3. **跨类型冲突**: Skill 和 MCP Server 定义了同名工具

### 解决策略

#### 1. 命名空间隔离

所有工具自动添加命名空间前缀：

```
完整格式: {type}:{plugin}:{tool}
示例:     skills:pdf_processor:extract_text
```

**简写规则**:
- 在 Skill 内部调用: `extract_text` → 自动解析为 `skills:pdf_processor:extract_text`
- 跨 Skill 调用: 必须使用完整名称

#### 2. 加载时冲突检测

```python
class PluginManager:
    def _register_tool_with_conflict_check(self, tool: Tool, plugin_id: str):
        """注册工具，检测冲突"""
        full_name = f"{plugin_id}:{tool.name}"
        
        if full_name in self._tools:
            existing = self._tools[full_name]
            logger.warning(
                f"工具名冲突: '{full_name}' 已被 {existing.plugin_id} 定义，"
                f"跳过 {plugin_id} 的定义"
            )
            return
        
        self._tools[full_name] = ToolRegistration(
            tool=tool,
            plugin_id=plugin_id,
        )
```

#### 3. 优先级覆盖

如果允许覆盖（配置 `allow_override: true`）：

```yaml
skills:
  allow_override: true  # 允许高优先级插件覆盖低优先级插件的工具
```

覆盖规则：
- 高 scope 优先（project > user > config）
- 同 scope 内，先加载的优先

#### 4. 运行时冲突处理

```python
async def execute_tool(self, tool_name: str, args: dict):
    """执行工具，处理冲突"""
    # 解析完整名称
    if ":" not in tool_name:
        # 简写形式，需要推断命名空间
        tool_name = self._resolve_tool_name(tool_name)
    
    registration = self._tools.get(tool_name)
    if not registration:
        # 尝试模糊匹配
        matches = self._fuzzy_match_tool(tool_name)
        if len(matches) == 1:
            registration = matches[0]
        elif len(matches) > 1:
            raise ToolConflictError(
                f"工具名 '{tool_name}' 有多个匹配: {', '.join(matches)}"
            )
        else:
            raise ToolNotFoundError(f"工具未找到: {tool_name}")
    
    return await registration.tool.execute(args)
```

### 最佳实践

1. **使用描述性工具名**: `extract_pdf_text` 而非 `extract_text`
2. **避免通用名称**: 不要用 `run`, `execute`, `process` 等过于通用的名称
3. **文档化工具**: 在 Skill.md 中明确说明提供的工具
4. **测试冲突**: 在 CI 中测试多个 Skill 同时加载的场景

---

## 迁移指南

### 从 AgentPool Pool-level Skills 迁移

**场景**: 你已经在使用 AgentPool 的 Pool-level Skills，现在想使用 Xeno Agent 的 Agent-level Skills。

#### 迁移步骤

**1. 评估需求**

```
是否需要运行时动态加载？     → 是 → 使用 Xeno Agent
是否需要热重载？             → 是 → 使用 Xeno Agent
是否需要 MCP 集成？           → 是 → 使用 Xeno Agent
仅需 Pool 启动时加载 Skills？  → 否 → 继续使用 AgentPool
```

**2. 配置文件迁移**

**Before (AgentPool)**:
```yaml
# config.yml (AgentPool manifest)
skills:
  paths:
    - "/shared/company-skills"
    - "./project-skills"
  include_default: true
```

**After (Xeno Agent within AgentPool)**:
```yaml
# config.yml (AgentPool manifest with Xeno Agent)
agents:
  xeno_assistant:
    type: xeno
    model: "openai:gpt-4o"
    # Xeno Agent 特有配置
    skills:
      paths:
        - "/shared/company-skills"
        - "./project-skills"
      include_default: true
      include_pool_skills: false  # 是否继承 Pool-level skills
```

**3. Skill 文件兼容性**

Xeno Agent 完全兼容 AgentPool Skill 格式，无需修改：

```markdown
---
name: my_skill
description: My skill
---

Skill content...
```

**4. 工具调用差异**

| 场景 | AgentPool | Xeno Agent |
|------|-----------|------------|
| 调用 Skill | `skill name=my_skill` | `skill name=my_skill` |
| 调用工具 | `extract_text` | `skills:my_skill:extract_text` |
| MCP 工具 | 独立配置 | Skill 内嵌配置 |

**5. 回滚策略**

如果迁移失败，可以回滚：

```yaml
# 回滚到纯 AgentPool
agents:
  assistant:
    type: native  # 改回 native agent
    model: "openai:gpt-4o"

skills:  # 移回 Pool-level
  paths:
    - "./project-skills"
```

### 从 oh-my-opencode 迁移

**场景**: 你已经在使用 oh-my-opencode 的 Skills，现在想迁移到 Xeno Agent。

#### 迁移步骤

**1. Skill 文件位置**

oh-my-opencode Skills 可以直接使用，无需修改：

```bash
# 方案 A: 保持现有位置
~/.config/opencode/skills/my-skill/SKILL.md

# 方案 B: 移动到标准位置
~/.claude/skills/my-skill/SKILL.md
```

**2. 配置迁移**

**oh-my-opencode**:
```json
// ~/.config/opencode/config.json
{
  "skills": {
    "sources": ["./custom-skills"]
  }
}
```

**Xeno Agent**:
```yaml
# config/plugins.yaml
skills:
  paths:
    - "~/.config/opencode/skills"  # 复用现有路径
    - "./custom-skills"
  include_default: true
```

**3. MCP 配置迁移**

oh-my-opencode 的 MCP 配置在 Skill frontmatter 中，完全兼容：

```markdown
---
name: my-skill
mcp:
  my-server:
    command: npx
    args: ["@example/mcp-server"]
---
```

**4. 差异对照**

| 特性 | oh-my-opencode | Xeno Agent |
|------|----------------|------------|
| Skill 格式 | 相同 | 相同 |
| MCP 配置 | Frontmatter | Frontmatter 或 mcp.json |
| 模板包装 | `<skill-instruction>` | `<skill-instruction>` |
| 热重载 | 不支持 | 支持 |
| 动态加载 | 不支持 | 支持 |

### 从零开始使用 Xeno Agent

**1. 初始化项目**

```bash
mkdir my-xeno-project
cd my-xeno-project
mkdir -p .claude/skills
```

**2. 创建第一个 Skill**

```bash
mkdir .claude/skills/hello_world
cat > .claude/skills/hello_world/SKILL.md << 'EOF'
---
name: hello_world
description: A simple hello world skill
---

This skill says hello to the user.

## Usage

Just ask me to say hello!
EOF
```

**3. 配置 Xeno Agent**

```yaml
# config.yaml
agents:
  assistant:
    type: xeno
    model: "openai:gpt-4o"
    skills:
      paths:
        - "./.claude/skills"
      include_default: true
      auto_load:
        - "hello_world"
```

**4. 运行测试**

```python
from xeno_agent import XenoAgent

async with XenoAgent("config.yaml") as agent:
    result = await agent.run("Use the hello_world skill")
    print(result)
```

---

## 与 AgentPool Skills 的对比

| 特性 | Xeno Agent (RFC 005.3) | AgentPool (RFC-0004) |
|------|------------------------|---------------------|
| **范围** | Agent-level | Pool-level |
| **动态性** | 运行时动态加载/卸载 | Pool 初始化时加载 |
| **热重载** | 支持 | 不支持 |
| **插件类型** | Skills + MCP + Custom Python | 仅 Skills |
| **配置方式** | YAML + 代码混合 | YAML 配置 |
| **命名空间** | 强制命名空间隔离 | 无命名空间 |
| **优先级** | Scope-based | Scope-based |
| **MCP 集成** | 内置支持 | 独立配置 |
| **适用场景** | 交互式 Agent | 批处理/服务化 |

**互补性**:
- Xeno Agent 可以作为 AgentPool 中的一个 Agent 类型
- 两者使用相同的 Skill 文件格式，可以共享 Skills
- AgentPool 的 Pool-level Skills 可以作为 Xeno Agent 的默认 Skills

---

## 测试

### Skills Loader 测试

```python
import pytest
from pathlib import Path

@pytest.mark.asyncio
async def test_skills_discovery(tmp_path: Path):
    """测试 Skill 发现"""
    # 创建测试 Skill
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: test_skill
description: Test skill
version: 1.0.0
---

Test skill content
        """,
        encoding="utf-8"
    )

    # Discover
    loader = SkillsLoader([tmp_path])
    skills = await loader.discover()

    assert len(skills) == 1
    assert skills[0].name == "test_skill"
    assert skills[0].scope == "config"

@pytest.mark.asyncio
async def test_skill_loading(tmp_path: Path):
    """测试 Skill 加载"""
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        """---
name: test_skill
description: Test skill
---

Test content
        """,
        encoding="utf-8"
    )

    # 创建 scripts/__init__.py
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    init_file = scripts_dir / "__init__.py"
    init_file.write_text(
        """from pydantic_ai import Tool

async def test_tool():
    return "test"

_PLUGIN_TOOLS = [Tool(name="test_tool", function=test_tool)]
        """,
        encoding="utf-8"
    )

    # Load
    loader = SkillsLoader([tmp_path])
    skill = await loader.load("test_skill")

    assert skill.discovered.metadata["name"] == "test_skill"
    assert len(skill.tools) > 0

@pytest.mark.asyncio
async def test_scope_priority():
    """测试 Scope 优先级"""
    # 创建同名 Skill 在不同 scope
    # 验证高优先级覆盖低优先级
    pass
```

### MCP Loader 测试

```python
@pytest.mark.asyncio
async def test_mcp_loading():
    """测试 MCP 服务器加载"""
    # Mock MCP 服务器
    config = {
        "name": "test_server",
        "type": "stdio",
        "command": ["echo"],
    }

    loader = MCPLoader([config])

    # Note: 实际测试需要 mock MCPServerStdio
    # 这里只是示例结构
```

### Plugin Manager 测试

```python
@pytest.mark.asyncio
async def test_plugin_lifecycle():
    """测试插件生命周期"""
    # 测试 load/unload/reload
    pass

@pytest.mark.asyncio
async def test_error_recovery():
    """测试错误恢复"""
    # 验证单个插件失败不影响其他插件
    pass
```

---

## 性能优化

### 1. 插件发现缓存

```python
class CachedPluginManager(PluginManager):
    """带缓存的 Plugin Manager"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._discovery_cache: dict[str, Any] = {}
        self._cache_ttl: int = 300  # 5 minutes

    async def discover_plugins(
        self,
        use_cache: bool = True,
    ) -> dict[str, list]:
        """发现插件（带缓存）"""
        cache_key = "plugins_discovery"

        if use_cache and cache_key in self._discovery_cache:
            cached_time, cached_data = self._discovery_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data

        # 重新发现
        discovered = await super().discover_plugins(use_cache=False)

        # 更新缓存
        self._discovery_cache[cache_key] = (time.time(), discovered)
        return discovered

    def invalidate_cache(self):
        """使缓存失效"""
        self._discovery_cache.clear()
```

### 2. 延迟加载

```python
class LazySkillContent:
    """延迟加载的 Skill 内容"""

    def __init__(self, path: Path):
        self.path = path
        self._content: str | None = None

    async def load(self) -> str:
        """延迟加载内容"""
        if self._content is None:
            self._content = await asyncio.to_thread(
                self.path.read_text,
                encoding="utf-8"
            )
        return self._content
```

### 3. MCP 连接池

```python
class MCPConnectionPool:
    """MCP 连接池 - 带最大连接数限制"""

    def __init__(self, max_connections: int = 10):
        self._clients: dict[str, ManagedClient] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._idle_timeout = 5 * 60  # 5 minutes
        self._max_connections = max_connections
        self._semaphore = asyncio.Semaphore(max_connections)

    async def get_or_create(
        self,
        key: str,
        factory: Callable[[], Awaitable[Client]],
    ) -> Client:
        """获取或创建客户端（带连接数限制）"""
        async with self._semaphore:  # 限制并发连接数
            # 检查现有连接
            if key in self._clients:
                client = self._clients[key]
                # 验证连接健康状态
                if await self._is_client_healthy(client):
                    client.last_used = time.time()
                    return client.client
                else:
                    # 连接不健康，关闭并重新创建
                    logger.warning(f"MCP client {key} unhealthy, reconnecting")
                    await self._evict_client(key)

            # 防止竞态条件
            if key in self._pending:
                return await self._pending[key]

            # 检查连接池是否已满
            if len(self._clients) >= self._max_connections:
                # 尝试清理空闲连接
                await self.cleanup_idle()
                
                if len(self._clients) >= self._max_connections:
                    # 清理后仍然满，使用 LRU 淘汰最老的连接
                    await self._evict_oldest_client()

            # 创建新连接
            future = asyncio.Future()
            self._pending[key] = future

            try:
                client = await factory()
                self._clients[key] = ManagedClient(
                    client=client,
                    last_used=time.time(),
                )
                future.set_result(client)
                return client
            except Exception as e:
                future.set_exception(e)
                raise
            finally:
                del self._pending[key]

    async def _is_client_healthy(self, client: ManagedClient) -> bool:
        """检查客户端健康状态"""
        try:
            # 对于 MCP 客户端，尝试 list_tools 作为健康检查
            if hasattr(client.client, 'list_tools'):
                await asyncio.wait_for(
                    client.client.list_tools(),
                    timeout=5.0
                )
            return True
        except Exception:
            return False

    async def _evict_client(self, key: str):
        """驱逐指定客户端"""
        if key in self._clients:
            client = self._clients.pop(key)
            try:
                await client.client.close()
            except Exception as e:
                logger.warning(f"Error closing MCP client {key}: {e}")

    async def _evict_oldest_client(self):
        """LRU 淘汰最久未使用的客户端"""
        if not self._clients:
            return
        
        # 找到最久未使用的
        oldest_key = min(
            self._clients.items(),
            key=lambda item: item[1].last_used
        )[0]
        
        logger.info(f"LRU evicting MCP client: {oldest_key}")
        await self._evict_client(oldest_key)

    async def cleanup_idle(self):
        """清理空闲连接"""
        now = time.time()
        to_remove = [
            key for key, client in self._clients.items()
            if now - client.last_used > self._idle_timeout
        ]
        for key in to_remove:
            await self._evict_client(key)
            logger.debug(f"Cleaned up idle MCP client: {key}")
```

---

## 安全考虑

### 威胁分析

| 威胁 | 影响 | 可能性 | 缓解措施 |
|------|------|--------|----------|
| 恶意 Skill 代码执行 | 高 | 中 | Skills 仅包含提示词，代码放在 scripts/ 中需显式加载 |
| 路径遍历攻击 | 高 | 低 | 使用 Path.resolve() 验证路径 |
| 环境变量泄露 | 中 | 中 | MCP 配置中的 ${VAR} 只在加载时展开，不记录 |
| 资源耗尽 | 中 | 低 | MCP 连接池限制连接数，超时自动清理 |
| 热重载 DoS | 低 | 低 | 文件变化防抖处理 |

### 安全措施

1. **路径验证**
```python
def validate_path(path: Path, allowed_roots: list[Path]) -> bool:
    """验证路径在允许的根目录内"""
    resolved = path.resolve()
    return any(
        resolved.is_relative_to(root.resolve())
        for root in allowed_roots
    )
```

2. **环境变量处理**
```python
def expand_env_vars(config: dict) -> dict:
    """安全展开环境变量"""
    import re

    def expand(value: str) -> str:
        # 只展开 ${VAR} 格式，不支持 $VAR
        pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}'
        return re.sub(pattern, lambda m: os.environ.get(m.group(1), m.group(0)), value)

    # 递归处理配置
    return _deep_transform(config, expand)
```

3. **模块加载隔离**
```python
class SandboxedModuleLoader:
    """受限环境下的模块加载"""

    RESTRICTED_BUILTINS = {
        '__import__',
        'open',
        'file',
        'exec',
        'eval',
        'compile',
    }

    def load(self, path: Path) -> Any:
        """在受限环境中加载模块"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("sandboxed_module", path)
        module = importlib.util.module_from_spec(spec)

        # 限制 builtins
        module.__dict__['__builtins__'] = {
            name: getattr(__builtins__, name)
            for name in dir(__builtins__)
            if name not in self.RESTRICTED_BUILTINS
        }

        spec.loader.exec_module(module)
        return module
```

---

## 开放问题

1. **插件隔离**: 是否为每个插件创建独立的 Python 进程/虚拟环境？
   - 状态: 待讨论
   - 影响: 安全性 vs 性能

2. **版本管理**: 如何处理同一插件的不同版本？
   - 状态: 待讨论
   - 提案: 支持 `skill_name@version` 格式

3. **依赖冲突**: 不同插件之间的 Python 依赖冲突如何解决？
   - 状态: 待讨论
   - 选项: 虚拟环境、容器化、依赖锁定

4. **资源清理**: 插件卸载后，如何确保所有资源（网络连接、文件句柄等）都被清理？
   - 状态: 待实现
   - 方案: 实现 `__aexit__` 协议，强制资源清理

5. **插件市场**: 是否支持从远程仓库自动下载和安装插件？
   - 状态: 未来功能
   - 依赖: 签名验证、版本管理

6. **与 AgentPool 的集成**: Xeno Agent 作为 AgentPool 的 Agent 类型时，如何处理 Skills 冲突？
   - 状态: 待设计
   - 方案: Xeno Agent 优先使用自身 PluginManager，回退到 Pool-level Skills

---

## 参考资料

### 内部文档

- [RFC 005: 系统架构](./005_system_architecture.md)
- [RFC 005.1: Hook 系统设计](./005_hooks_system_design.md)
- [RFC-0004: Configurable Skills Loading Paths](../../../../../agentpool/docs/rfcs/review/RFC-0004-configurable-skills-loading-paths.md)

### 外部文档

- [Claude Skills Specification](https://docs.anthropic.com/claude/docs/skills)
- [MCP Specification](https://modelcontextprotocol.io/)
- [Pydantic AI Tools](https://ai.pydantic.dev/tools/)
- [Python Import Hooks](https://docs.python.org/3/library/importlib.html)

### 参考实现

- oh-my-opencode Skill Loader: `src/features/opencode-skill-loader/`
- oh-my-opencode MCP Manager: `src/features/skill-mcp-manager/`

---

**End of Document**
