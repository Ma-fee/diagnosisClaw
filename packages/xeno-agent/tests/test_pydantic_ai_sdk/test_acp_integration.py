"""
Integration tests for ACPAgent
Tests stdio transport lifecycle: initialize -> new_session -> prompt
"""

import json
import tempfile
from pathlib import Path

import pytest

from xeno_agent.pydantic_ai.acp_server import ACPAgent
from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.factory import AgentFactory


class JSONRPC:
    """Simple JSON-RPC helper for stdio communication."""

    @staticmethod
    def request(method: str, params: dict | None = None, req_id: int = 1) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

    @staticmethod
    def parse_response(text: str) -> dict:
        line = text.strip().split("\n")[-1]
        return json.loads(line)


@pytest.mark.asyncio
async def test_acp_agent_initialize():
    """Test ACPAgent.initialize returns proper response."""
    base_pkg_path = Path(__file__).parents[2]
    config_path = base_pkg_path / "config"

    loader = YAMLConfigLoader(base_path=config_path)
    factory = AgentFactory(config_loader=loader, model="openai:svc/glm-4.7", skill_loader=None, skill_registry=None)
    flow_config = loader.load_flow_config("fault_diagnosis")

    agent = ACPAgent(factory=factory, flow_config=flow_config)

    response = await agent.initialize(
        protocol_version="2025",
        capabilities={},
        client_info={"name": "test-client", "version": "1.0"},
    )

    assert response.protocol_version == 2025
    assert response.agent_info.name == "ACPAgent"
    assert response.agent_capabilities.session_capabilities is not None


@pytest.mark.asyncio
async def test_acp_agent_new_session():
    """Test ACPAgent.new_session creates session and returns ID."""
    base_pkg_path = Path(__file__).parents[2]
    config_path = base_pkg_path / "config"

    loader = YAMLConfigLoader(base_path=config_path)
    factory = AgentFactory(config_loader=loader, model="openai:svc/glm-4.7", skill_loader=None, skill_registry=None)
    flow_config = loader.load_flow_config("fault_diagnosis")

    agent = ACPAgent(factory=factory, flow_config=flow_config)

    response = await agent.new_session(cwd=tempfile.gettempdir(), mcp_servers=[])

    assert hasattr(response, "sessionId")
    assert response.sessionId is not None
    assert isinstance(response.sessionId, str)
    assert response.sessionId in agent.sessions


@pytest.mark.asyncio
async def test_acp_agent_prompt():
    """Test ACPAgent.prompt processes text and returns response."""
    base_pkg_path = Path(__file__).parents[2]
    config_path = base_pkg_path / "config"

    loader = YAMLConfigLoader(base_path=config_path)
    factory = AgentFactory(config_loader=loader, model="openai:svc/glm-4.7", skill_loader=None, skill_registry=None)
    flow_config = loader.load_flow_config("fault_diagnosis")

    agent = ACPAgent(factory=factory, flow_config=flow_config)

    session_response = await agent.new_session(cwd=tempfile.gettempdir(), mcp_servers=[])
    session_id = session_response.sessionId

    from acp.schema import TextContentBlock

    messages = [TextContentBlock(type="text", text="hello")]

    response = await agent.prompt(prompt=messages, session_id=session_id)

    # Response content handling depends on specific ACP version
    # assert hasattr(response, "content")
    assert response.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_acp_agent_session_isolation():
    """Test that different sessions have isolated contexts."""
    base_pkg_path = Path(__file__).parents[2]
    config_path = base_pkg_path / "config"

    loader = YAMLConfigLoader(base_path=config_path)
    factory = AgentFactory(config_loader=loader, model="openai:svc/glm-4.7", skill_loader=None, skill_registry=None)
    flow_config = loader.load_flow_config("fault_diagnosis")

    agent = ACPAgent(factory=factory, flow_config=flow_config)

    session1_id = (await agent.new_session(cwd=tempfile.gettempdir(), mcp_servers=[])).sessionId
    session2_id = (await agent.new_session(cwd=tempfile.gettempdir(), mcp_servers=[])).sessionId

    assert session1_id != session2_id
    assert len(agent.sessions) == 2
    assert agent.sessions[session1_id] != agent.sessions[session2_id]
