# RFC 005.3: 动态插件 & Skills 加载

## 状态
**状态**: Draft
**创建日期**: 2026-01-20
**作者**: Sisyphus
**最后更新**: 2026-01-20

---

## 概述

本文档描述 Xeno Agent 的动态插件系统，支持 Claude Skills 动态加载、MCP 服务器集成以及自定义 Python 模块插件。

---

## 设计目标

1. **动态发现**: 自动扫描和发现 Skills/插件
2. **热重载**: 支持运行时重新加载更新的模块
3. **命名空间隔离**: 不同来源的工具使用命名空间区分
4. **配置驱动**: 通过 YAML 配置管理插件加载
5. **错误恢复**: 单个插件失败不影响整体系统

---

## 插件类型

### 1. Claude Skills

**描述**: Anthropic 官方技能包，包含提示词、资源、脚本

**文件结构**:
```
.claude/skills/
└── pdf_processor/
    ├── SKILL.md (主文件，YAML frontmatter + Markdown 内容)
    ├── scripts/ (可选的 Python 脚本)
    ├── references/ (参考资料)
    └── assets/ (图片、PDF 等资源)
```

**SKILL.md 示例**:
```markdown
---
name: PDF Processor
description: Extract text and analyze PDF documents
version: 1.0.0
author: Anthropic
---

This skill helps you process PDF documents...

## Usage

Use the `extract_text` tool to extract text from PDFs.
```

### 2. MCP Servers

**描述**: Model Context Protocol 服务器，提供标准化工具接口

**启动方式**:
```bash
npx @modelcontextprotocol/server-filesystem /path/to/directory
npx @modelcontextprotocol/server-github
python custom_mcp_server.py
```

### 3. Custom Python Plugins

**描述**: 自定义 Python 模块，直接扩展 Agent 功能

**示例**:
```python
# plugins/web_search.py
from pydantic_ai import Tool

async def search_web(query: str) -> dict:
    """Search the web for information"""
    # 实现逻辑...
    return {"results": [...]}

_PLUGIN_TOOLS = [
    Tool(
        name="search_web",
        description="Search the web",
        function=search_web,
    )
]
```

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                     Xeno Agent                                  │
│  - Dynamic Plugin Manager                                        │
│  - Hook Integration (plugin.load.before/after)                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                  Plugin Loader Interface                        │
│  - discover_plugins()                                          │
│  - load_plugin(plugin_id)                                       │
│  - unload_plugin(plugin_id)                                     │
│  - reload_plugin(plugin_id)                                     │
└────┬─────────────────┬─────────────────┬────────────────────┘
     │                 │                 │
┌────▼────────┐  ┌────▼────────┐  ┌────▼────────────┐
│ SkillLoader │  │ MCPLoader   │  │ CustomPluginLoader│
└────┬────────┘  └────┬────────┘  └────┬────────────┘
     │                 │                 │
┌────▼─────────────────────────────────────────────────────────┐
│                  Plugin Registry                               │
│  - register_tool(tool_definition)                              │
│  - get_tools(namespace)                                        │
│  - get_tool(tool_name)                                         │
└────────────────────────┬──────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                   Dynamic Toolsets                              │
│  - PrefixedToolset (skills:pdf_processor:extract_text)       │
│  - MCPServerToolset (mcp:filesystem:read_file)              │
│  - CustomToolset (plugin:search_web)                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心组件

### 1. Plugin Manager

**职责**: 统一的插件管理器

```python
from typing import TypeAlias
from pathlib import Path

PluginID: TypeAlias = str  # "skills:pdf_processor"

class PluginManager:
    """插件管理器"""

    def __init__(self, config: PluginConfig, agent: "XenoAgent"):
        self.config = config
        self.agent = agent
        self.plugins: dict[PluginID, LoadedPlugin] = {}
        self.loaders: dict[str, PluginLoader] = {}

        # 初始化加载器
        self._initialize_loaders()

    def _initialize_loaders(self):
        """初始化内置加载器"""
        self.loaders["skills"] = SkillsLoader(
            paths=self.config.skill_paths,
        )
        self.loaders["mcp"] = MCPLoader(
            servers=self.config.mcp_servers,
        )
        self.loaders["custom"] = CustomPluginLoader(
            paths=self.config.custom_plugin_paths,
        )

    async def discover_plugins(self) -> dict[str, list[DiscoveredPlugin]]:
        """
        发现所有可用插件

        Returns:
            {loader_type: [plugins]}
        """
        discovered = {}

        for loader_type, loader in self.loaders.items():
            plugins = await loader.discover()
            discovered[loader_type] = plugins
            logger.info(
                f"Discovered {len(plugins)} {loader_type} plugins"
            )

        return discovered

    async def load_plugin(
        self,
        plugin_id: PluginID,
    ) -> LoadedPlugin:
        """
        加载插件

        Args:
            plugin_id: 插件 ID (e.g., "skills:pdf_processor")
        """
        # 解析插件类型和标识
        loader_type, plugin_identifier = plugin_id.split(":", 1)

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

        # 加载插件
        loader = self.loaders[loader_type]
        loaded_plugin = await loader.load(plugin_identifier)

        # 注册到 registry
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

        logger.info(f"Loaded plugin: {plugin_id}")
        return loaded_plugin

    async def unload_plugin(self, plugin_id: PluginID):
        """卸载插件"""
        if plugin_id not in self.plugins:
            logger.warning(f"Plugin not found: {plugin_id}")
            return

        loaded_plugin = self.plugins[plugin_id]

        # 触发 before hook
        await self.agent.hooks.execute_before(
            event="plugin.unload.before",
            ctx=HookContext(
                agent=self.agent,
                event="plugin.unload.before",
                metadata={"plugin_id": plugin_id}
            )
        )

        # 清理
        for tool_id in loaded_plugin.tools:
            # 从 registry 移除工具
            self.agent.tool_registry.unregister_tool(tool_id)

        # 卸载加载器
        loader_type = plugin_id.split(":", 1)[0]
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

    async def reload_plugin(self, plugin_id: PluginID):
        """重新加载插件"""
        await self.unload_plugin(plugin_id)
        await self.load_plugin(plugin_id)
        logger.info(f"Reloaded plugin: {plugin_id}")
```

### 2. Skills Loader

**职责**: Claude Skills 的发现和加载

```python
import yaml
import frontmatter

class DiscoveredSkill:
    def __init__(self, path: Path, metadata: dict):
        self.path = path
        self.name = metadata.get("name")
        self.description = metadata.get("description")
        self.version = metadata.get("version")
        self.author = metadata.get("author")

class LoadedSkill:
    def __init__(self, discovered: DiscoveredSkill, tools: list[Tool]):
        self.discovered = discovered
        self.tools = tools
        self.metadata = discovered.metadata
        self.content = discovered.content

class SkillsLoader(PluginLoader):
    """Claude Skills 加载器"""

    def __init__(self, paths: list[Path]):
        self.paths = paths

    async def discover(self) -> list[DiscoveredSkill]:
        """
        发现 Skills

        流程:
        1. 扫描所有路径，查找 SKILL.md 文件
        2. 解析 frontmatter YAML 获取元数据
        3. 返回 DiscoveredSkill 列表
        """
        discovered = []

        for path in self.paths:
            for skill_dir in path.rglob("*"):
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue

                # 解析 frontmatter
                with open(skill_md, "r", encoding="utf-8") as f:
                    data = frontmatter.load(f)
                    metadata = data.metadata
                    content = data.content

                skill = DiscoveredSkill(
                    path=skill_dir,
                    metadata=metadata,
                    content=content,
                )

                discovered.append(skill)

        return discovered

    async def load(self, skill_name: str) -> LoadedSkill:
        """
        加载 Skill

        流程:
        1. 查找 Skill 目录
        2. 解析 SKILL.md (Level 2 加载)
        3. 解析 scripts/ 中的 Python 脚本
        4. 将逻辑转换为 Pydantic AI Tools
        """
        # 查找 Skill
        discovered = [s for s in await self.discover() if s.name == skill_name]
        if not discovered:
            raise SkillNotFoundError(skill_name)

        skill_dir = discovered[0].path
        skill_md = skill_dir / "SKILL.md"

        # 解析 content
        with open(skill_md, "r", encoding="utf-8") as f:
            data = frontmatter.load(f)

        # 从 content 中提取工具定义
        # 这里可以解析 Markdown 中的工具定义，或者使用预定义的映射
        tools = await self._extract_tools_from_skill(
            skill_dir,
            data.content,
        )

        return LoadedSkill(
            discovered=discovered[0],
            tools=tools,
            metadata=data.metadata,
            content=data.content,
        )

    async def _extract_tools_from_skill(
        self,
        skill_dir: Path,
        content: str,
    ) -> list[Tool]:
        """
        从 Skill content 提取工具定义

        策略:
        1. 查找 scripts/ 目录中的 Python 脚本
        2. 解析 Markdown 中的工具说明
        3. 注册为 Pydantic AI Tools
        """
        tools = []

        # 加载 scripts/
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            # 动态导入脚本
            module = self._load_module(scripts_dir)
            if hasattr(module, "_PLUGIN_TOOLS"):
                tools.extend(module._PLUGIN_TOOLS)

        # 解析 content 中的工具声明
        # 示例 Markdown 格式:
        # ```tool
        # name: extract_text
        # description: Extract text from PDF
        # parameters: ...
        # ```
        tools.extend(
            await self._parse_tool_blocks(content)
        )

        # 添加命名空间前缀
        for tool in tools:
            tool.name = f"skills:{skill_dir.name}:{tool.name}"

        return tools

    def _load_module(self, scripts_dir: Path) -> Any:
        """动态加载 Python 模块"""
        import importlib.util

        # 查找 __init__.py 或 main.py
        init_file = scripts_dir / "__init__.py"
        if not init_file.exists():
            raise SkillScriptError(f"No __init__.py found in {scripts_dir}")

        spec = importlib.util.spec_from_file_location(
            "skill_scripts",
            init_file,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        return module

    async def unload(self, skill: LoadedSkill):
        """卸载 Skill"""
        # 清理缓存的模块等
        pass
```

### 3. MCP Loader

**职责**: MCP 服务器的发现和工具加载

```python
from pydantic_ai.mcp import MCPServerStdio

class MCPServerConfig(TypedDict):
    name: str
    command: list[str]
    env: dict[str, str] | None

class DiscoveredMCPServer:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.name = config["name"]

class LoadedMCPServer:
    def __init__(
        self,
        server: MCPServerStdio,
        tools: list[Tool],
        config: MCPServerConfig,
    ):
        self.server = server
        self.tools = tools
        self.config = config
        self.process: asyncio.subprocess.Process | None = None

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

    async def load(self, server_name: str) -> LoadedMCPServer:
        """
        加载 MCP 服务器

        流程:
        1. 启动 MCP 服务器进程
        2. 列出可用工具
        3. 转换为 Pydantic AI Tools
        4. 包装为 MCPServerStdio
        """
        config = self.servers.get(server_name)
        if not config:
            raise MCPServerNotFoundError(server_name)

        # 启动 MCP 服务器进程
        process = await asyncio.create_subprocess_exec(
            *config["command"],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=config.get("env"),
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
                name=f"mcp:{server_name}:{mcp_tool.name}",
                description=mcp_tool.description,
                # MCP 的 inputSchema 转换为 JSON Schema
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

    async def unload(self, server: LoadedMCPServer):
        """卸载 MCP 服务器"""
        if server.server:
            await server.__aexit__(None, None, None)

        if server.process:
            server.process.terminate()
            await server.process.wait()
```

### 4. Custom Plugin Loader

**职责**: 自定义 Python 模块的动态加载

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
            # 单文件插件
            for py_file in path.glob("plugins/*.py"):
                if py_file.name.startswith("_"):
                    continue

                module_name = py_file.stem
                discovered.append(
                    DiscoveredCustomPlugin(py_file, module_name)
                )

            # 目录插件
            for plugin_dir in path.glob("plugins/*"):
                if plugin_dir.is_file():
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
        # 查找插件
        discovered = [
            p for p in await self.discover()
            if p.module_name == plugin_name
        ]

        if not discovered:
            raise CustomPluginNotFoundError(plugin_name)

        plugin = discovered[0]

        # 动态导入模块
        module = self._load_module(plugin.path)

        # 提取工具
        tools = []

        # 方法 1: 从 _PLUGIN_TOOLS 变量提取
        if hasattr(module, "_PLUGIN_TOOLS"):
            tools.extend(module._PLUGIN_TOOLS)

        # 方法 2: 扫描所有导出的 Tool
        for name, obj in vars(module).items():
            if isinstance(obj, Tool):
                # 添加命名空间前缀
                obj.name = f"plugin:{plugin_name}:{obj.name}"
                tools.append(obj)

        return LoadedCustomPlugin(
            module=module,
            tools=tools,
            path=plugin.path,
        )

    def _load_module(self, path: Path) -> Any:
        """动态加载模块"""
        import importlib.util
        import sys

        if path.is_dir():
            init_file = path / "__init__.py"
            spec = importlib.util.spec_from_file_location(
                f"plugins.{path.name}",
                init_file,
            )
        else:
            spec = importlib.util.spec_from_file_location(
                f"plugins.{path.stem}",
                path,
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        return module

    async def unload(self, plugin: LoadedCustomPlugin):
        """卸载插件"""
        import sys

        # 移除模块引用
        module_name = plugin.module.__name__
        if module_name in sys.modules:
            del sys.modules[module_name]
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

    async def start(self):
        """启动文件监视"""
        self.is_running = True

        async for changes in awatch(*self.paths):
            await self._handle_changes(changes)

    async def stop(self):
        """停止文件监视"""
        self.is_running = False

    async def _handle_changes(self, changes: set[tuple[int, str]]):
        """
        处理文件变化

        Changes:
            (1, path) - Created
            (2, path) - Modified
            (3, path) - Deleted
        """
        for change_type, path_str in changes:
            path = Path(path_str)

            # 判断是否是插件文件
            plugin_id = self._identify_plugin(path)
            if not plugin_id:
                continue

            # 处理文件类型
            if change_type == 1:  # Created
                logger.info(f"Plugin created: {path}")
                await self.manager.load_plugin(plugin_id)

            elif change_type == 2:  # Modified
                logger.info(f"Plugin modified: {path}")
                await self.manager.reload_plugin(plugin_id)

            elif change_type == 3:  # Deleted
                logger.info(f"Plugin deleted: {path}")
                await self.manager.unload_plugin(plugin_id)

    def _identify_plugin(self, path: Path) -> str | None:
        """
        识别文件所属的插件

        Returns:
            plugin_id (e.g., "skills:pdf_processor") or None
        """
        # 匹配 Skill
        if "SKILL.md" in path.parts:
            skill_name = path.parent.name
            return f"skills:{skill_name}"

        # 匹配 Custom Plugin
        if "plugins" in path.parts:
            plugin_name = path.stem if path.is_file() else path.name
            return f"custom:{plugin_name}"

        # MCP 服务器不通过文件监视触发（配置驱动）

        return None
```

---

## 配置

### 插件配置

```yaml
# config/plugins.yaml

# Skills 配置
skills:
  enabled: true
  paths:
    - "~/.claude/skills"
    - ".claude/skills"
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
  servers:
    - name: "filesystem"
      command: ["npx", "@modelcontextprotocol/server-filesystem", "/home/user/files"]
      env:
        PATH: "/usr/local/bin:/usr/bin"
    - name: "github"
      command: ["npx", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_TOKEN: "${GITHUB_TOKEN}"

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

---

## Hook 集成

### 插件生命周期 Hooks

```python
# 在 Plugin Manager 中触发

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

# Tool 调用插件特定 Hook
if tool_name.startswith("skills:"):
    await hooks.execute_before(
        event="skill.tool.before",
        ctx=HookContext(
            agent=agent,
            event="skill.tool.before",
            tool_name=tool_name,
            tool_args=args,
            metadata={
                "skill_name": skill_name.split(":")[1],
            }
        )
    )
```

---

## 测试

### Skills Loader 测试

```python
import pytest
from pathlib import Path

@pytest.mark.asyncio
async def test_skills_discovery(tmp_path: Path):
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

@pytest.mark.asyncio
async def test_skill_loading(tmp_path: Path):
    # (同上，创建测试 Skill)

    # Load
    loader = SkillsLoader([tmp_path])
    skill = await loader.load("test_skill")

    assert skill.metadata["name"] == "test_skill"
    assert len(skill.tools) > 0
```

### MCP Loader 测试

```python
@pytest.mark.asyncio
async def test_mcp_loading():
    # Mock MCP 服务器
    config = {
        "name": "test_server",
        "command": ["echo"],  # 使用 echo 模拟
    }

    loader = MCPLoader([config])

    # Note: 实际测试需要 mock MCPServerStdio
    # 这里只是示例结构

    # loaded = await loader.load("test_server")
    # assert len(loaded.tools) > 0
```

---

## 性能优化

### 1. 插件缓存

```python
class CachedPluginManager(PluginManager):
    """带缓存的 Plugin Manager"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._discovery_cache: dict[str, Any] = {}
        self._cache_ttl: int = 300  # 5 minutes

    async def discover_plugins(self) -> dict[str, list]:
        """发现插件（带缓存）"""
        cache_key = "plugins_discovery"

        # 检查缓存
        if cache_key in self._discovery_cache:
            cached_time, cached_data = self._discovery_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data

        # 重新发现
        discovered = await super().discover_plugins()

        # 更新缓存
        self._discovery_cache[cache_key] = (time.time(), discovered)

        return discovered
```

### 2. 延迟加载

```python
class LazyPluginManager(PluginManager):
    """延迟加载插件"""

    async def load_plugin(self, plugin_id: str) -> LoadedPlugin:
        # 延迟配置中标记为 "lazy" 的插件
        if self._is_lazy_plugin(plugin_id):
            # 首次使用时才加载
            return await self._lazy_load(plugin_id)

        return await super().load_plugin(plugin_id)
```

---

## 安全考虑

### 1. 插件沙箱

```python
class SandboxedPluginLoader(PluginLoader):
    """沙箱加载器，限制插件权限"""

    def _load_module(self, path: Path) -> Any:
        # 限制模块访问
        import sys
        original_modules = sys.modules.copy()

        try:
            # 在受限环境中加载模块
            return super()._load_module(path)
        finally:
            # 恢复 sys.modules
            sys.modules.clear()
            sys.modules.update(original_modules)
```

### 2. 插件签名验证

```python
class SignedPluginLoader(PluginLoader):
    """签名验证加载器"""

    def __init__(self, public_keys: list[str]):
        self.public_keys = public_keys

    async def load(self, plugin_id: str):
        # 1. 加载插件
        # 2. 验证签名
        # 3. 如果签名无效，拒绝加载

        if not self._verify_signature(plugin_id):
            raise InvalidPluginSignatureError(plugin_id)

        return await super().load(plugin_id)
```

---

## 开放问题

1. **插件隔离**: 是否为每个插件创建独立的 Python 进程/虚拟环境？
2. **版本管理**: 如何处理同一插件的不同版本？
3. **依赖冲突**: 不同插件之间的 Python 依赖冲突如何解决？
4. **资源清理**: 插件卸载后，如何确保所有资源（网络连接、文件句柄等）都被清理？
5. **插件市场**: 是否支持从远程仓库自动下载和安装插件？

---

## 参考资料

- [RFC 005: 系统架构](./005_system_architecture.md)
- [RFC 005.1: Hook 系统设计](./005_hooks_system_design.md)
- [Claude Skills Specification](https://docs.anthropic.com/claude/docs/skills)
- [MCP Specification](https://modelcontextprotocol.io/)
- [Python Import Hooks](https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly)
