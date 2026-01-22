# Dynamic Skills Loading 方案设计

## 一、问题背景

### 当前状态：静态注册
```python
# main.py - 硬编码注册
skill_registry.register("fault_analysis", tools.fault_analysis, expected_params=["fault_description"])
skill_registry.register("equipment_spec_lookup", tools.equipment_spec_lookup, expected_params=["equipment_id"])
# ... 每个技能都需要手动添加
```

### 痛点
- ❌ 新增技能需要修改代码
- ❌ 无法热重载
- ❌ 缺乏技能元数据管理
- ❌ 没有渐进式披露机制

### 目标状态：动态加载
```python
# 只需配置路径，技能自动发现和注册
skill_loader = SkillDirectoryLoader("./skills")
skill_registry = skill_loader.load_all()
# 自动发现并注册所有技能
```

---

## 二、Claude Skills 动态加载机制

### 渐进式披露架构 (Progressive Disclosure)

Claude Skills 采用三层动态加载架构，实现 **98% token 节省**：

```
┌─────────────────────────────────────────────────────────┐
│  Stage 1: 元数据层 (~100 tokens)                         │
│  • 名称 + 简短描述                                       │
│  • 技能发现阶段加载                                      │
│  • 用于判断是否需要激活此技能                            │
├─────────────────────────────────────────────────────────┤
│  Stage 2: 指令层 (<5k tokens)                            │
│  • 详细使用指南和工作流程                                │
│  • 触发条件满足时加载                                    │
│  • 回答 80% 常见问题                                     │
├─────────────────────────────────────────────────────────┤
│  Stage 3: 资源层 (按需)                                  │
│  • 脚本代码、参考文档、模板                              │
│  • 实际执行时按需读取                                    │
│  • 不占用 context window                                 │
└─────────────────────────────────────────────────────────┘
```

### 标准技能目录结构
```
skill-name/
├── SKILL.md              # 必需 - 元数据 + 核心指令
├── instructions.md       # 可选 - 详细指令
├── CONCEPTS.md          # 可选 - 理论说明
├── OPERATIONS.md        # 可选 - 操作指南
├── scripts/             # 可执行脚本
│   ├── main.py
│   └── utils.py
├── references/          # 参考资料
└── resources/           # 模板和资源
    └── template.json
```

### SKILL.md 标准格式
```markdown
---
name: fault-analysis
description: Analyze equipment faults and provide diagnostic recommendations based on error codes and symptoms
disable-model-invocation: false
allowed-tools: Read, Write, Grep
argument-hint: fault_description
---

# Fault Analysis Skill

## 何时使用
- 当用户描述设备故障症状时
- 当需要根据错误代码诊断问题时
- 收到"设备不工作了"、"出现错误"等请求时

## 快速使用
使用 `fault_analysis` 工具，传入故障描述字符串。

## 详细指南
### 输入参数
- `fault_description`: 故障现象描述，可以包含错误代码、发生时间、操作步骤

### 输出格式
返回包含以下字段的分析结果：
- `root_cause`: 根本原因分析
- `solutions`: 推荐解决方案
- `severity`: 严重程度

[详细说明请参阅 CONCEPTS.md]
```

---

## 三、推荐方案：渐进式披露 + 动态注册

### 3.1 核心架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    应用层                                │
│  AgentFactory → SkillRegistry → SkillLoader            │
├─────────────────────────────────────────────────────────┤
│                    加载层                                │
│  DirectoryScanner → SkillParser → RegistryBuilder      │
├─────────────────────────────────────────────────────────┤
│                    存储层                                │
│  ./skills/                                              │
│  ├── fault-analysis/                                    │
│  │   ├── SKILL.md                                       │
│  │   ├── CONCEPTS.md                                    │
│  │   └── scripts/                                       │
│  ├── equipment-lookup/                                  │
│  └── ...                                                │
└─────────────────────────────────────────────────────────┘
```

### 3.2 核心组件设计

#### 1. SkillDirectoryLoader - 目录加载器
```python
class SkillDirectoryLoader:
    """从指定目录动态加载所有Skills"""
    
    def __init__(self, base_path: str | Path, registry: SkillRegistry | None = None):
        self.base_path = Path(base_path)
        self.registry = registry or SkillRegistry()
    
    def load_all(self) -> SkillRegistry:
        """发现并注册所有Skills"""
        for skill_dir in self.base_path.iterdir():
            if skill_dir.is_dir() and self._is_valid_skill_dir(skill_dir):
                self.load_skill(skill_dir)
        return self.registry
    
    def load_skill(self, skill_dir: Path) -> None:
        """加载单个Skill"""
        # 1. 解析元数据 (SKILL.md frontmatter)
        metadata = self._parse_skill_metadata(skill_dir)
        
        # 2. 解析实现文件
        impl_file = self._find_implementation(skill_dir, metadata.language)
        
        # 3. 注册到Registry
        self.registry.register(
            skill_name=metadata.name,
            func=self._load_implementation(impl_file),
            expected_params=metadata.argument_hint
        )
```

#### 2. SkillMetadata - 元数据模型
```python
from pydantic import BaseModel, Field

class SkillMetadata(BaseModel):
    """Skill元数据定义"""
    name: str = Field(..., description="技能名称")
    description: str = Field(..., description="用途描述 (<200 chars)")
    disable_model_invocation: bool = Field(False, alias="disable-model-invocation")
    allowed_tools: list[str] | None = Field(None, alias="allowed-tools")
    argument_hint: str | None = Field(None, alias="argument-hint")
    language: str = Field("python", description="实现语言")
    
    class Config:
        populate_by_name = True
```

#### 3. EnhancedSkillRegistry - 增强版注册表
```python
class EnhancedSkillRegistry(SkillRegistry):
    """支持动态加载的增强注册表"""
    
    def __init__(self):
        super().__init__()
        self.metadata: dict[str, SkillMetadata] = {}
        self.skill_dirs: dict[str, Path] = {}
    
    def register_with_metadata(
        self,
        skill_name: str,
        func: Callable,
        metadata: SkillMetadata,
        skill_dir: Path | None = None
    ):
        """注册技能及其元数据"""
        self.register(skill_name, func, expected_params=metadata.argument_hint)
        self.metadata[skill_name] = metadata
        if skill_dir:
            self.skill_dirs[skill_name] = skill_dir
    
    def list_skills_with_metadata(self) -> dict[str, SkillMetadata]:
        """列出所有技能及其元数据"""
        return self.metadata.copy()
```

---

## 四、实现步骤

### Phase 1: 基础设施层

#### 1.1 创建动态加载器
**文件**: `src/xeno_agent/pydantic_ai/skill_loader.py`

```python
import os
import sys
import importlib.util
from pathlib import Path
from typing import Any, Callable
from .skills import SkillRegistry

class SkillDirectoryLoader:
    """从目录动态加载Skills"""
    
    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)
        self.registry = SkillRegistry()
    
    def load_all(self) -> SkillRegistry:
        """加载所有Skills"""
        if not self.base_path.exists():
            raise FileNotFoundError(f"Skills directory not found: {self.base_path}")
        
        for skill_dir in self.base_path.iterdir():
            if skill_dir.is_dir():
                self._load_skill(skill_dir)
        
        return self.registry
    
    def _load_skill(self, skill_dir: Path) -> None:
        """加载单个Skill"""
        skill_id = skill_dir.name
        
        # 1. 加载 SKILL.md 解析元数据
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return  # 跳过无效目录
        
        metadata = self._parse_metadata(skill_md)
        
        # 2. 加载实现代码
        impl_file = self._find_implementation(skill_dir, metadata.get("language", "python"))
        if impl_file:
            func = self._load_implementation(impl_file, skill_id)
            expected_params = metadata.get("argument_hint", [])
            self.registry.register(skill_id, func, expected_params=expected_params)
    
    def _parse_metadata(self, skill_md: Path) -> dict[str, Any]:
        """解析SKILL.md的YAML frontmatter"""
        content = skill_md.read_text()
        
        # 简单的frontmatter解析
        if content.startswith("---"):
            frontmatter, _ = content.split("---", 2)
            # 这里可以使用 PyYAML 解析
            # 返回解析后的元数据字典
            return self._yaml_load(frontmatter)
        return {}
    
    def _find_implementation(self, skill_dir: Path, language: str) -> Path | None:
        """查找实现文件"""
        patterns = {
            "python": ["main.py", "skill.py", f"{skill_dir.name}.py"],
            "javascript": ["index.js", "skill.js"],
        }
        
        for pattern in patterns.get(language, []):
            impl = skill_dir / pattern
            if impl.exists():
                return impl
        return None
    
    def _load_implementation(self, impl_file: Path, skill_id: str) -> Callable:
        """动态加载实现代码"""
        # 对于Python，使用importlib动态导入
        spec = importlib.util.spec_from_file_location(skill_id, impl_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[skill_id] = module
        spec.loader.exec_module(module)
        
        # 假设实现中有名为 "execute" 或 "skill" 的函数
        if hasattr(module, "execute"):
            return module.execute
        elif hasattr(module, "skill"):
            return module.skill
        else:
            raise ValueError(f"Skill {skill_id} missing execute() function")
```

#### 1.2 创建示例Skill
**文件**: `skills/fault-analysis/SKILL.md`
**文件**: `skills/fault-analysis/main.py`

### Phase 2: 渐进式披露支持

#### 2.1 创建 SkillPromptLoader
```python
class SkillPromptLoader:
    """加载技能的渐进式提示"""
    
    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)
    
    def get_metadata_prompt(self, skill_id: str) -> str:
        """获取元数据层提示 (~100 tokens)"""
        skill_dir = self.base_path / skill_id
        skill_md = skill_dir / "SKILL.md"
        
        if not skill_md.exists():
            return ""
        
        content = skill_md.read_text()
        
        # 提取元数据
        metadata = self._extract_metadata(content)
        return self._format_metadata_prompt(metadata)
    
    def get_full_instructions(self, skill_id: str) -> str:
        """获取完整指令层提示"""
        skill_dir = self.base_path / skill_id
        skill_md = skill_dir / "SKILL.md"
        
        if not skill_md.exists():
            return ""
        
        # 跳过frontmatter，返回完整内容
        content = skill_md.read_text()
        return self._extract_instructions(content)
```

### Phase 3: 热重载支持 (可选)

#### 3.1 创建 SkillHotReloader
```python
import asyncio
from watchfiles import watch

class SkillHotReloader:
    """支持Skills热重载"""
    
    def __init__(self, loader: SkillDirectoryLoader, poll_interval: float = 1.0):
        self.loader = loader
        self.poll_interval = poll_interval
    
    async def start(self, callback: Callable[[str], None] | None = None):
        """启动文件监控"""
        for changes in watch(self.loader.base_path):
            for change_type, path in changes:
                skill_id = Path(path).parent.name
                if change_type == "modified":
                    # 重新加载
                    self.loader.registry.registry.pop(skill_id, None)
                    self.loader._load_skill(Path(path).parent)
                    
                    if callback:
                        callback(skill_id)
```

---

## 五、目录结构示例

```
iroot-llm/
├── skills/                                    # Skills根目录
│   ├── fault-analysis/                        # 技能1
│   │   ├── SKILL.md                           # 元数据 + 核心指令
│   │   ├── CONCEPTS.md                        # 理论说明
│   │   ├── OPERATIONS.md                      # 操作指南
│   │   └── scripts/
│   │       └── main.py                        # Python实现
│   ├── equipment-lookup/                      # 技能2
│   │   ├── SKILL.md
│   │   └── main.py
│   ├── document-retrieval/                    # 技能3
│   │   ├── SKILL.md
│   │   └── main.py
│   └── ...
│
├── packages/xeno-agent/
│   └── src/xeno_agent/pydantic_ai/
│       ├── skills.py                          # SkillRegistry定义
│       ├── skill_loader.py                    # 动态加载器 (新增)
│       └── main.py                            # 入口点
```

---

## 六、使用示例

### 6.1 最简使用
```python
from xeno_agent.pydantic_ai.skill_loader import SkillDirectoryLoader

# 动态加载所有Skills
loader = SkillDirectoryLoader("./skills")
registry = loader.load_all()

# 检查已注册的技能
print(registry.registry.keys())
# 输出: dict_keys(['fault-analysis', 'equipment-lookup', ...])

# 获取技能
fault_analysis = registry.get("fault-analysis")
```

### 6.2 完整集成到AgentFactory
```python
class AgentFactory:
    def __init__(self, skills_path: str | Path):
        loader = SkillDirectoryLoader(skills_path)
        self.skill_registry = loader.load_all()
    
    def create_agent(self, agent_id: str):
        # ... 创建agent
        for skill_id in agent_config.skills:
            skill_func = self.skill_registry.get(skill_id)
            agent.tool(skill_func)
```

### 6.3 带渐进式披露的集成
```python
class SkillAwareAgentFactory(AgentFactory):
    def __init__(self, skills_path: str | Path):
        super().__init__(skills_path)
        self.prompt_loader = SkillPromptLoader(skills_path)
    
    def create_agent_with_prompts(self, agent_id: str):
        agent = self.create_agent(agent_id)
        
        # 为每个技能添加渐进式提示
        for skill_id in agent_config.skills:
            metadata_prompt = self.prompt_loader.get_metadata_prompt(skill_id)
            # 将metadata_prompt注入到系统提示中
        return agent
```

---

## 七、元数据规范 (SKILL.md)

### 必需字段
```yaml
---
name: fault-analysis                    # 技能标识符 (唯一)
description: Analyze equipment faults   # 用途描述 (<200 chars)
---
```

### 可选字段
```yaml
---
name: skill-name
description: What this skill does
disable-model-invocation: false        # 是否禁止自动调用
allowed-tools: Read, Write, Grep       # 允许的工具列表
argument-hint: fault_description       # 参数提示
language: python                       # 实现语言
version: 1.0.0                         # 版本号
author: Engineering Team               # 作者
tags: [diagnostic, equipment]          # 标签
---
```

---

## 八、迁移路径

### 从静态到动态的迁移步骤

1. **Phase 1: 创建动态加载器** (1-2天)
   - 实现 SkillDirectoryLoader
   - 创建示例Skill目录结构

2. **Phase 2: 并行运行** (1周)
   - 新技能使用动态加载
   - 旧技能保持静态注册
   - 验证功能等价

3. **Phase 3: 迁移现有技能** (2-3天)
   - 为每个现有技能创建SKILL.md
   - 移动实现代码到独立目录
   - 更新Agent配置

4. **Phase 4: 移除静态注册** (1天)
   - 删除main.py中的静态注册
   - 验证所有测试通过

---

## 九、技术选型建议

| 组件 | 推荐方案 | 备选 | 理由 |
|------|---------|------|------|
| 配置文件格式 | YAML Frontmatter | JSON | Claude Skills标准，易读 |
| 代码加载 | importlib | importlib.metadata | 标准库，稳定可靠 |
| 动态导入 | 目录名作为模块名 | 独立命名空间 | 简单直接 |
| 模式验证 | Pydantic | dataclasses | 类型安全，自动验证 |
| 热重载 (可选) | watchfiles | inotify | 跨平台，活跃维护 |

---

## 十、测试策略

### 单元测试
```python
def test_skill_loader():
    loader = SkillDirectoryLoader("./test_skills")
    registry = loader.load_all()
    
    # 验证注册
    assert "fault-analysis" in registry.registry
    assert callable(registry.get("fault-analysis"))
    
    # 验证参数签名
    sig = inspect.signature(registry.get("fault-analysis"))
    assert "fault_description" in sig.parameters
```

### 集成测试
```python
def test_agent_with_dynamic_skills():
    factory = AgentFactory("./skills")
    agent = factory.create_agent("diagnostic-agent")
    
    # 验证Agent可以调用技能
    result = agent.run("分析这个故障: 电机不转")
    assert "fault_analysis" in result
```

---

## 十一、Open Questions

1. **技能版本管理**
   - 需要支持版本号吗？
   - 如何处理版本冲突？

2. **技能依赖**
   - 技能之间有依赖怎么办？
   - 是否需要依赖注入框架？

3. **权限控制**
   - 不同Agent是否需要不同的技能权限？
   - 如何实现细粒度访问控制？

4. **部署方式**
   - 技能目录在代码库内还是独立？
   - 是否支持远程/动态下载技能？

5. **测试基础设施**
   - 需要为动态加载的技能设置测试框架吗？
   - 如何验证动态加载的技能功能正常？
