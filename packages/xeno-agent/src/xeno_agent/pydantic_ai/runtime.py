from dataclasses import dataclass
from typing import Any

from pydantic_ai import RunContext

from xeno_agent.pydantic_ai.interfaces import AgentResult, AgentRuntime
from xeno_agent.pydantic_ai.trace import TraceID

MAX_DELEGATION_DEPTH = 5


@dataclass
class RuntimeDeps:
    """Dependencies passed to agents."""

    config: Any  # Config object containing allow_delegation_to permissions
    trace: TraceID
    factory: Any  # AgentFactory protocol/instance

    def child(self, target: str) -> "RuntimeDeps":
        """Create a child dependency context."""
        return RuntimeDeps(config=self.config, trace=self.trace.child(target), factory=self.factory)


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
    # Assuming config has allow_delegation_to list or dict logic
    # We'll need to define the Config interface more strictly later
    if hasattr(deps.config, "allow_delegation_to") and target_agent not in deps.config.allow_delegation_to:
        raise PermissionError(f"Delegation to {target_agent} not allowed")

    # 3. Load Target Agent
    agent = deps.factory.load(target_agent)

    # 4. Execute (Recursive Call)
    new_deps = deps.child(target_agent)

    # Pass usage=ctx.usage to track tokens across the chain
    result = await agent.run(task, deps=new_deps, usage=ctx.usage)
    return str(result.data)


class LocalAgentRuntime(AgentRuntime):
    """Local implementation of AgentRuntime using PydanticAI."""

    def __init__(self, factory: Any, config: Any):
        self.factory = factory
        self.config = config

    async def invoke(self, agent_id: str, message: str, **kwargs: Any) -> AgentResult:
        """Invoke the entry point agent."""
        agent = self.factory.load(agent_id)

        # Initialize Trace
        trace = TraceID.new().child(agent_id)

        # Initialize Deps
        deps = RuntimeDeps(config=self.config, trace=trace, factory=self.factory)

        result = await agent.run(message, deps=deps)

        return AgentResult(data=str(result.data), metadata={"trace_id": trace.trace_id, "usage": result.usage()})

    async def delegate(self, target_agent: str, task: str, **kwargs: Any) -> AgentResult:
        """Manual delegation entry point (if needed outside tool)."""
        # This might reuse the same logic as invoke but usually
        # delegation happens inside the tool.
        # If called externally, it acts like a new invocation.
        return await self.invoke(target_agent, task, **kwargs)
