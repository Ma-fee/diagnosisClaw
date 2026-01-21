# PydanticAI Multi-Agent SDK

A production-grade Multi-Agent SDK based on [PydanticAI](https://github.com/pydantic/pydantic-ai), replicating the RFC 001 fault diagnosis system using a simplified, **delegation-based architecture** (RFC 006).

## Overview

This SDK enables the creation of multi-agent systems where agents can recursively delegate tasks to each other through a universal delegation tool. It emphasizes:

- **Pure Delegation**: Agents call other agents via tools.
- **Flow-Driven Topology**: Centralized control of agent interactions via YAML configuration.
- **Interface-Driven**: Core components are abstract protocols allowing for local or remote (ACP) implementations.
- **Safety**: Built-in recursion depth limits and cycle detection.

## Core Components

### 1. `AgentRuntime`
The execution engine for agents. `LocalAgentRuntime` provides a local implementation using PydanticAI's recursive tool calling.

### 2. `AgentFactory`
Assembles agents dynamically by merging Agent and Flow configurations. It builds system prompts in 4 layers:
1. **Identity**: Agent's role and backstory.
2. **Flow**: Global instructions for the current SOP.
3. **Delegation**: Computed allow-lists for task delegation.
4. **Skills**: XML-formatted tool definitions.

### 3. `SkillRegistry` & `SkillLoader`
Loads and manages "Skills" (Anthropic-style XML tool definitions). Maps XML descriptions to Python callables with strict signature validation.

### 4. `TraceID`
Provides global session tracking and enforces safety guardrails (Max Depth=5).

## Getting Started

### Installation
```bash
uv pip install packages/xeno-agent
```

### Configuration
Define your agents in `config/agents/` and your flows in `config/flows/`.

**Example Flow (config/flows/fault_diagnosis.yaml):**
```yaml
name: "Fault Diagnosis"
entry_agent: "qa_assistant"
delegation_rules:
  qa_assistant:
    allow_delegation_to: ["fault_expert"]
```

## Usage

### Command Line Interface
The SDK provides a CLI tool for running flows. It is registered as `xeno-agent` in `pyproject.toml`.

**Run a single message:**
```bash
uv run xeno-agent fault_diagnosis "My server has a red light on the PSU"
```

**Run in interactive mode:**
```bash
uv run xeno-agent fault_diagnosis -i
```

**Specify a model:**
```bash
uv run xeno-agent fault_diagnosis -i --model "anthropic:claude-3-5-sonnet-latest"
```

### Python API
```python
from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime
from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader

# 1. Initialize
loader = YAMLConfigLoader(base_path="config")
factory = AgentFactory(config_loader=loader)
flow_config = loader.load_flow_config("fault_diagnosis")

# 2. Setup Runtime
runtime = LocalAgentRuntime(factory=factory, flow_config=flow_config)

# 3. Invoke
result = await runtime.invoke("qa_assistant", "I have a problem with my server...")
logger.info(result.data)
```

## Testing
Run the comprehensive TDD suite:
```bash
uv run pytest packages/xeno-agent/tests/test_pydantic_ai_sdk/
```
