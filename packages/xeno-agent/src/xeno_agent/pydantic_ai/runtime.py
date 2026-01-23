import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage

from xeno_agent.pydantic_ai.interfaces import AgentResult, AgentRuntime
from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.tool_manager import FlowToolManager
from xeno_agent.pydantic_ai.trace import TraceID

logger = logging.getLogger(__name__)

MAX_DELEGATION_DEPTH = 5


@runtime_checkable
class AgentFactoryProtocol(Protocol):
    async def create(
        self,
        agent_id: str,
        flow_config: FlowConfig,
        tool_manager: FlowToolManager,
        use_cache: bool = True,
    ) -> Agent[Any, str]: ...


@dataclass
class RuntimeDeps:
    """Dependencies passed to agents."""

    flow: FlowConfig
    trace: TraceID
    factory: AgentFactoryProtocol
    tool_manager: FlowToolManager
    message_history: list[ModelMessage] = field(default_factory=list)
    session_id: str | None = None

    def child(self, target: str) -> "RuntimeDeps":
        """Create a child dependency context."""
        return RuntimeDeps(
            flow=self.flow,
            trace=self.trace.child(target),
            factory=self.factory,
            tool_manager=self.tool_manager,
            message_history=self.message_history,
            session_id=self.session_id,
        )


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
    # Note: Accessing delegation_rules assuming it exists on FlowConfig at runtime
    if current_agent_id and getattr(deps.flow, "delegation_rules", None) and current_agent_id in deps.flow.delegation_rules:
        allowed = deps.flow.delegation_rules[current_agent_id].get("allow_delegation_to", [])

    if target_agent not in allowed:
        raise PermissionError(f"Delegation from {current_agent_id} to {target_agent} not allowed by flow policy")

    # 3. Load Target Agent
    agent = await deps.factory.create(target_agent, deps.flow, tool_manager=deps.tool_manager)

    # 4. Execute (Recursive Call)
    new_deps = deps.child(target_agent)

    # Pass usage=ctx.usage to track tokens across the chain
    start_time = time.perf_counter()
    # Note: FlowToolManager handles lifecycle, no context manager needed here
    result = await agent.run(task, deps=new_deps, usage=ctx.usage, message_history=new_deps.message_history)
    duration = time.perf_counter() - start_time

    all_messages = result.all_messages()
    if len(all_messages) > len(new_deps.message_history):
        new_messages = all_messages[len(new_deps.message_history) :]
        new_deps.message_history.extend(new_messages)

    logger.info(f"Agent {target_agent} executed in {duration:.3f}s (Trace: {new_deps.trace.trace_id}, Session: {new_deps.session_id}, Messages: {len(new_deps.message_history)})")
    return str(result.data)


class LocalAgentRuntime(AgentRuntime):
    """Local implementation of AgentRuntime using PydanticAI."""

    def __init__(self, factory: AgentFactoryProtocol, flow_config: FlowConfig, tool_manager: FlowToolManager | None = None):
        self.factory = factory
        self.flow_config = flow_config
        self._active_sessions: dict[str, RuntimeDeps] = {}
        self.tool_manager = tool_manager or FlowToolManager(flow_config.tools)

    async def __aenter__(self) -> "LocalAgentRuntime":
        await self.tool_manager.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.tool_manager.cleanup()

    async def invoke(self, agent_id: str, message: str, session_id: str | None = None, **kwargs: Any) -> AgentResult:
        # Note: If not using context manager, tool_manager might not be initialized.
        # But we assume usage via async with or caller handles initialization if they access tool_manager directly?
        # To be safe, invoke could check if initialized? FlowToolManager doesn't seem to have is_initialized.
        # But standard pattern is async with.

        agent = await self.factory.create(agent_id, self.flow_config, tool_manager=self.tool_manager)

        if session_id and session_id in self._active_sessions:
            deps = self._active_sessions[session_id]
            trace = TraceID.new(root_trace_id=deps.trace.trace_id).child(agent_id)
        else:
            session_id = session_id or str(uuid.uuid4())
            trace = TraceID.new().child(agent_id)
            deps = RuntimeDeps(
                flow=self.flow_config,
                trace=trace,
                factory=self.factory,
                tool_manager=self.tool_manager,
                session_id=session_id,
            )

        start_time = time.perf_counter()
        result = await agent.run(message, deps=deps, message_history=deps.message_history)
        duration = time.perf_counter() - start_time
        logger.info(f"Entry agent {agent_id} executed in {duration:.3f}s (Trace: {trace.trace_id}, Session: {session_id})")

        all_messages = result.all_messages()
        if len(all_messages) > len(deps.message_history):
            new_messages = all_messages[len(deps.message_history) :]
            deps.message_history.extend(new_messages)

        if session_id not in self._active_sessions:
            self._active_sessions[session_id] = deps
        else:
            self._active_sessions[session_id].message_history = deps.message_history

        return AgentResult(
            data=str(result.data),
            metadata={"trace_id": trace.trace_id, "usage": result.usage(), "session_id": session_id, "message_count": len(deps.message_history)},
        )

    async def delegate(self, target_agent: str, task: str, **kwargs: Any) -> AgentResult:
        """Manual delegation entry point."""
        return await self.invoke(target_agent, task, **kwargs)
