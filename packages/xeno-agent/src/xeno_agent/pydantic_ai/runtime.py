import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic_ai import Agent, RunContext

from xeno_agent.pydantic_ai.interfaces import AgentResult, AgentRuntime
from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.trace import TraceID

logger = logging.getLogger(__name__)

MAX_DELEGATION_DEPTH = 5


@runtime_checkable
class AgentFactoryProtocol(Protocol):
    async def create(self, agent_id: str, flow_config: FlowConfig) -> Agent[Any, str]: ...


@dataclass
class RuntimeDeps:
    """Dependencies passed to agents."""

    flow: FlowConfig
    trace: TraceID
    factory: AgentFactoryProtocol

    def child(self, target: str) -> "RuntimeDeps":
        """Create a child dependency context."""
        return RuntimeDeps(flow=self.flow, trace=self.trace.child(target), factory=self.factory)


async def delegate_task(ctx: RunContext[RuntimeDeps], target_agent: str, task: str) -> str:
    """Universal delegation tool."""
    deps = ctx.deps

    # 1. Cycle Detection & Depth Check
    current_depth = len(deps.trace.path)
    if current_depth > MAX_DELEGATION_DEPTH:
        raise RecursionError("Max delegation depth exceeded")

    if deps.trace.has_cycle(target_agent):
        raise RecursionError(f"Cycle detected: {target_agent} already in call stack {deps.trace.path}")

    # 2. Check permissions
    # Get delegation rules for the CURRENT agent (the one calling the tool)
    current_agent_id = deps.trace.path[-1] if deps.trace.path else None

    # Simple whitelist check from flow config
    allowed = []
    if current_agent_id and current_agent_id in deps.flow.delegation_rules:
        allowed = deps.flow.delegation_rules[current_agent_id].get("allow_delegation_to", [])

    if target_agent not in allowed:
        raise PermissionError(f"Delegation from {current_agent_id} to {target_agent} not allowed by flow policy")

    # 3. Load Target Agent
    agent = await deps.factory.create(target_agent, deps.flow)

    # 4. Execute (Recursive Call)
    new_deps = deps.child(target_agent)

    # Pass usage=ctx.usage to track tokens across the chain
    start_time = time.perf_counter()
    async with agent.run_mcp_servers(model=agent.model):
        result = await agent.run(task, deps=new_deps, usage=ctx.usage)
    duration = time.perf_counter() - start_time
    logger.info(f"Agent {target_agent} executed in {duration:.3f}s (Trace: {new_deps.trace.trace_id})")
    return str(result.data)


class LocalAgentRuntime(AgentRuntime):
    """Local implementation of AgentRuntime using PydanticAI."""

    def __init__(self, factory: AgentFactoryProtocol, flow_config: FlowConfig):
        self.factory = factory
        self.flow_config = flow_config

    async def invoke(self, agent_id: str, message: str, **kwargs: Any) -> AgentResult:
        """Invoke the entry point agent."""
        agent = await self.factory.create(agent_id, self.flow_config)

        # Initialize Trace
        trace = TraceID.new().child(agent_id)

        # Initialize Deps
        deps = RuntimeDeps(flow=self.flow_config, trace=trace, factory=self.factory)

        start_time = time.perf_counter()
        async with agent.run_mcp_servers(model=agent.model):
            result = await agent.run(message, deps=deps)
        duration = time.perf_counter() - start_time
        logger.info(f"Entry agent {agent_id} executed in {duration:.3f}s (Trace: {trace.trace_id})")

        return AgentResult(data=str(result.data), metadata={"trace_id": trace.trace_id, "usage": result.usage()})

    async def delegate(self, target_agent: str, task: str, **kwargs: Any) -> AgentResult:
        """Manual delegation entry point."""
        return await self.invoke(target_agent, task, **kwargs)
