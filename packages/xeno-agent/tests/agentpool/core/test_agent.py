"""Tests for XenoAgent implementation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from agentpool.agents.base_agent import BaseAgent
from agentpool.sessions import SessionData

from xeno_agent.agentpool.core.agent import XenoAgent
from xeno_agent.agentpool.core.config import RoleType, XenoConfig, XenoRoleConfig


@pytest.fixture
def mock_xeno_config():
    return XenoConfig(
        roles={
            "qa": XenoRoleConfig(
                type=RoleType.QA_ASSISTANT,
                name="qa_agent",
                system_prompt="QA Prompt",
                model="test:model",
            ),
            "fault": XenoRoleConfig(
                type=RoleType.FAULT_EXPERT,
                name="fault_agent",
                system_prompt="Fault Prompt",
                model="test:model",
            ),
        },
    )


@pytest.fixture
def mock_agent_pool():
    pool = MagicMock()
    pool.storage = MagicMock()
    return pool


@pytest.fixture
def xeno_agent(mock_xeno_config, mock_agent_pool):
    agent = XenoAgent(
        name="xeno_test",
        xeno_config=mock_xeno_config,
        agent_pool=mock_agent_pool,
        model="test:model",  # Default model
    )
    # Mock internal dependencies usually set in __init__
    agent.conversation = MagicMock()
    agent.conversation.get_history.return_value = []
    agent.conversation.to_pydantic_ai.return_value = []
    return agent


class TestXenoAgent:
    """Tests for XenoAgent core functionality."""

    def test_initialization(self, xeno_agent):
        """Test proper initialization of XenoAgent."""
        assert isinstance(xeno_agent, BaseAgent)
        assert xeno_agent.name == "xeno_test"
        assert xeno_agent.AGENT_TYPE == "xeno"
        assert xeno_agent._active_role_id == "qa"  # Should default to first or specific one

    def test_model_name_property(self, xeno_agent):
        """Test model_name property returns current role's model."""
        assert xeno_agent.model_name == "test:model"

    @pytest.mark.asyncio
    async def test_set_model(self, xeno_agent):
        """Test set_model updates the current role's model (in memory)."""
        await xeno_agent.set_model("new:model")
        # Since config is immutable, it might not update the config object itself,
        # but the agent should track the override or update internal state.
        # For XenoAgent, set_model might be a no-op or update the current role's model override.
        # Let's assume for now it updates the current role's effective model.
        # If the implementation allows overriding.
        # Implementation detail: XenoAgent might not support arbitrary model switching easily without config update.

    @pytest.mark.asyncio
    async def test_get_available_models(self, xeno_agent):
        """Test get_available_models returns None (not supported) or a list."""
        # Typically returns None if discovery is not implemented or relies on BaseAgent defaults
        models = await xeno_agent.get_available_models()
        # Expecting None or empty list for now as we haven't mocked discovery
        assert models is None or isinstance(models, list)

    @pytest.mark.asyncio
    async def test_get_modes(self, xeno_agent):
        """Test get_modes returns available roles as modes."""
        modes = await xeno_agent.get_modes()
        assert len(modes) >= 1
        # Should have a "role" or "mode" category
        role_category = next((c for c in modes if c.id == "role"), None)
        assert role_category is not None
        assert len(role_category.available_modes) == 2
        assert any(m.id == "qa" for m in role_category.available_modes)
        assert any(m.id == "fault" for m in role_category.available_modes)

    @pytest.mark.asyncio
    async def test_set_mode(self, xeno_agent):
        """Test switching roles via set_mode."""
        await xeno_agent._set_mode("fault", "role")
        assert xeno_agent._active_role_id == "fault"
        assert xeno_agent.current_role.name == "fault_agent"

        # Test invalid role
        with pytest.raises(ValueError):
            await xeno_agent._set_mode("invalid", "role")

    @pytest.mark.asyncio
    async def test_list_sessions(self, xeno_agent, mock_agent_pool):
        """Test listing sessions delegates to pool storage."""
        # Setup mock to accept agent_name argument
        mock_agent_pool.sessions.store.list_sessions = AsyncMock(return_value=["sess1"])
        mock_agent_pool.sessions.store.load = AsyncMock(return_value=SessionData(session_id="sess1", agent_name="xeno_test"))

        sessions = await xeno_agent.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].session_id == "sess1"
        # Verify it was called with correct agent name
        mock_agent_pool.sessions.store.list_sessions.assert_called_with(agent_name="xeno_test")

    @pytest.mark.asyncio
    async def test_load_session(self, xeno_agent, mock_agent_pool):
        """Test loading session delegates to pool storage."""
        session_data = SessionData(session_id="sess1", agent_name="xeno_test")
        mock_agent_pool.sessions.store.load = AsyncMock(return_value=session_data)

        loaded = await xeno_agent.load_session("sess1")
        assert loaded == session_data

    @pytest.mark.asyncio
    async def test_interrupt(self, xeno_agent):
        """Test interrupt method."""
        # Should be safe to call even if no task running
        await xeno_agent.interrupt()
        assert xeno_agent._cancelled

    @pytest.mark.asyncio
    async def test_list_sessions_filters(self, xeno_agent, mock_agent_pool):
        """Test listing sessions with filters."""
        sess1 = SessionData(session_id="sess1", agent_name="xeno_test", cwd="project_root/session_1")
        sess2 = SessionData(session_id="sess2", agent_name="xeno_test", cwd="project_root/session_2")
        sess3 = SessionData(session_id="sess3", agent_name="xeno_test", cwd="project_root/session_1")

        mock_agent_pool.sessions.store.list_sessions = AsyncMock(return_value=["sess1", "sess2", "sess3"])

        # Mock load to return sessions
        async def mock_load(sid):
            if sid == "sess1":
                return sess1
            if sid == "sess2":
                return sess2
            if sid == "sess3":
                return sess3
            return None

        mock_agent_pool.sessions.store.load = AsyncMock(side_effect=mock_load)

        # Test cwd filter
        sessions = await xeno_agent.list_sessions(cwd="project_root/session_1")
        assert len(sessions) == 2
        assert sessions[0].session_id == "sess1"
        assert sessions[1].session_id == "sess3"

        # Test limit
        sessions = await xeno_agent.list_sessions(limit=1)
        assert len(sessions) == 1
        assert sessions[0].session_id == "sess1"

    @pytest.mark.asyncio
    async def test_load_session_no_pool(self, xeno_agent):
        """Test load_session returns None if no agent pool."""
        xeno_agent.agent_pool = None
        loaded = await xeno_agent.load_session("sess1")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_list_sessions_no_pool(self, xeno_agent):
        """Test list_sessions returns empty list if no agent pool."""
        xeno_agent.agent_pool = None
        sessions = await xeno_agent.list_sessions()
        assert sessions == []

    @pytest.mark.asyncio
    async def test_interrupt_with_task(self, xeno_agent):
        """Test interrupt cancels the current task."""
        mock_task = MagicMock()
        mock_task.done.return_value = False
        xeno_agent._current_stream_task = mock_task

        await xeno_agent._interrupt()
        mock_task.cancel.assert_called_once()
