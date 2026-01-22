import asyncio
import pytest
from contextlib import asynccontextmanager

from unittest.mock import AsyncMock, MagicMock

from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime, RuntimeDeps, delegate_task, AgentFactoryProtocol
from xeno_agent.pydantic_ai.trace import TraceID
from xeno_agent.pydantic_ai.models import FlowConfig
from pydantic_ai import RunContext


@asynccontextmanager
async def null_mcp_servers(*args, **kwargs):
    yield


class MockDeps:
    def __init__(self, flow=None, trace=None, factory=None, message_history=None, session_id=None):
        self.flow = flow or FlowConfig(
            name="Test",
            description="Test",
            entry_agent="a",
            participants=["a"],
            global_instructions="",
            delegation_rules={},
        )
        self.trace = trace or TraceID.new()
        self.factory = factory
        self.message_history = message_history or []
        self.session_id = session_id

    def child(self, target: str) -> "MockDeps":
        return MockDeps(flow=self.flow, trace=self.trace.child(target), factory=self.factory, message_history=self.message_history, session_id=self.session_id)


@pytest.mark.asyncio
async def test_invoke_creates_session():
    mock_agent = AsyncMock()
    result_mock = MagicMock()
    result_mock.data = "Hello response"
    result_mock.all_messages.return_value = []
    result_mock.usage.return_value = {"prompt_tokens": 10}
    mock_agent.run.return_value = result_mock
    mock_agent.run_mcp_servers = null_mcp_servers

    mock_factory = MagicMock(spec=AgentFactoryProtocol)
    mock_factory.create.return_value = mock_agent

    flow = FlowConfig(name="Test", description="Test", entry_agent="agent_a", participants=["agent_a"], global_instructions="", delegation_rules={})
    runtime = LocalAgentRuntime(factory=mock_factory, flow_config=flow)

    result = await runtime.invoke("agent_a", "Hello")

    assert result.metadata["session_id"] is not None
    message_count = result.metadata.get("message_count", 0)
    assert message_count >= 0
    assert result.metadata["session_id"] in runtime._active_sessions
    mock_factory.create.assert_called_once()


@pytest.mark.asyncio
async def test_invoke_reuses_session():
    mock_agent = AsyncMock()
    result_mock = MagicMock()

    messages = []
    result_mock.data = "Response 1"
    result_mock.all_messages.return_value = messages
    result_mock.usage.return_value = {"prompt_tokens": 10}
    mock_agent.run.return_value = result_mock
    mock_agent.run_mcp_servers = null_mcp_servers

    mock_factory = MagicMock(spec=AgentFactoryProtocol)
    mock_factory.create.return_value = mock_agent

    flow = FlowConfig(name="Test", description="Test", entry_agent="agent_a", participants=["agent_a"], global_instructions="", delegation_rules={})
    runtime = LocalAgentRuntime(factory=mock_factory, flow_config=flow)

    result1 = await runtime.invoke("agent_a", "First turn")
    session_id = result1.metadata["session_id"]
    count1 = result1.metadata.get("message_count", 0)

    messages.append(magic_message("user", "First turn"))
    messages.append(magic_message("assistant", "Response 1"))
    result_mock.data = "Response 2"
    mock_agent.run.reset_mock()
    result2 = await runtime.invoke("agent_a", "Second turn", session_id=session_id)

    assert result2.metadata["session_id"] == session_id
    count2 = result2.metadata.get("message_count", 0)
    assert count2 >= count1


@pytest.mark.asyncio
async def test_invokes_different_agent_same_session():
    mock_agent = AsyncMock()
    result_mock = MagicMock()

    messages = []
    result_mock.data = "Agent A response"
    result_mock.all_messages.return_value = messages
    result_mock.usage.return_value = {"prompt_tokens": 10}
    mock_agent.run.return_value = result_mock
    mock_agent.run_mcp_servers = null_mcp_servers

    mock_factory = MagicMock(spec=AgentFactoryProtocol)
    mock_factory.create.return_value = mock_agent

    flow = FlowConfig(name="Test", description="Test", entry_agent="agent_a", participants=["agent_a", "agent_b"], global_instructions="", delegation_rules={})
    runtime = LocalAgentRuntime(factory=mock_factory, flow_config=flow)

    result1 = await runtime.invoke("agent_a", "Hello")
    session_id = result1.metadata["session_id"]
    messages.append(magic_message("user", "Hello"))
    messages.append(magic_message("assistant", "Agent A response"))

    result2 = await runtime.invoke("agent_b", "Continue", session_id=session_id)
    assert result2.metadata["session_id"] == session_id


@pytest.mark.asyncio
async def test_three_turn_conversation():
    mock_agent = AsyncMock()
    result_mock = MagicMock()

    messages = []

    turn1_count = len(messages)
    result_mock.data = "Turn 1 response"
    result_mock.all_messages.return_value = messages
    result_mock.usage.return_value = {"prompt_tokens": 10}
    mock_agent.run.return_value = result_mock
    mock_agent.run_mcp_servers = null_mcp_servers

    mock_factory = MagicMock(spec=AgentFactoryProtocol)
    mock_factory.create.return_value = mock_agent

    flow = FlowConfig(name="Test", description="Test", entry_agent="agent_a", participants=["agent_a"], global_instructions="", delegation_rules={})
    runtime = LocalAgentRuntime(factory=mock_factory, flow_config=flow)

    r1 = await runtime.invoke("agent_a", "Turn 1")
    sid1 = r1.metadata["session_id"]
    messages.append(magic_message("user", "Turn 1"))
    messages.append(magic_message("assistant", "Response 1"))
    cnt1 = r1.metadata.get("message_count", 0)

    result_mock.all_messages.return_value = messages
    r2 = await runtime.invoke("agent_a", "Turn 2", session_id=sid1)
    sid2 = r2.metadata["session_id"]
    messages.append(magic_message("user", "Turn 2"))
    messages.append(magic_message("assistant", "Response 2"))
    cnt2 = r2.metadata.get("message_count", 0)

    result_mock.all_messages.return_value = messages
    r3 = await runtime.invoke("agent_a", "Turn 3", session_id=sid1)
    sid3 = r3.metadata["session_id"]
    cnt3 = r3.metadata.get("message_count", 0)

    assert sid1 == sid2 == sid3
    assert cnt1 <= cnt2 <= cnt3


@pytest.mark.asyncio
async def test_different_session_ids():
    mock_agent = AsyncMock()
    result_mock = MagicMock()

    result_mock.data = "Response"
    result_mock.all_messages.return_value = []
    result_mock.usage.return_value = {"prompt_tokens": 10}
    mock_agent.run.return_value = result_mock
    mock_agent.run_mcp_servers = null_mcp_servers

    mock_factory = MagicMock(spec=AgentFactoryProtocol)
    mock_factory.create.return_value = mock_agent

    flow = FlowConfig(name="Test", description="Test", entry_agent="agent_a", participants=["agent_a"], global_instructions="", delegation_rules={})
    runtime = LocalAgentRuntime(factory=mock_factory, flow_config=flow)

    r1 = await runtime.invoke("agent_a", "Message 1")
    sid1 = r1.metadata["session_id"]

    mock_agent.reset_mock()
    r2 = await runtime.invoke("agent_a", "Message 2")
    sid2 = r2.metadata["session_id"]

    assert sid1 != sid2
    assert sid1 in runtime._active_sessions
    assert sid2 in runtime._active_sessions


def magic_message(role: str, content: str):
    msg = MagicMock()
    msg.role = role
    msg.content = content
    return msg
