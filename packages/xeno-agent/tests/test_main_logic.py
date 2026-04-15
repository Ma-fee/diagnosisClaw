from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acp.schema import (
    ClientCapabilities,
    Implementation,
    InitializeRequest,
    ListSessionsRequest,
    LoadSessionRequest,
    NewSessionRequest,
    PromptRequest,
    SetSessionConfigOptionRequest,
    SetSessionModelRequest,
    SetSessionModeRequest,
    TextContentBlock,
)
from agentpool.agents.events import PartDeltaEvent, StreamCompleteEvent
from typer.testing import CliRunner

from xeno_agent.agentpool.core.config import RoleType, XenoConfig, XenoRoleConfig
from xeno_agent.main import XenoACPAgent, app

runner = CliRunner()


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
def mock_connection():
    return AsyncMock()


@pytest.fixture
def xeno_acp_agent(mock_xeno_config, mock_connection):
    return XenoACPAgent(mock_xeno_config, mock_connection)


@pytest.fixture
def tmp_path_fixture(tmp_path):
    """Pytest tmp_path fixture for temporary directory usage."""
    return tmp_path


@pytest.mark.asyncio
async def test_initialize(xeno_acp_agent):
    request = InitializeRequest(protocol_version=1, client_info=Implementation(name="test-client", version="1.0.0"), client_capabilities=ClientCapabilities())
    response = await xeno_acp_agent.initialize(request)
    assert response.agent_info.name == "xeno-agent"
    assert response.agent_info.version == "0.1.0"
    assert response.protocol_version == 1


@pytest.mark.asyncio
async def test_new_session(xeno_acp_agent, tmp_path_fixture):
    request = NewSessionRequest(cwd=str(tmp_path_fixture))

    # Mock XenoAgent.get_modes since it's called inside new_session
    with patch("xeno_agent.main.XenoAgent") as MockXenoAgent:
        mock_agent_instance = MockXenoAgent.return_value
        mock_mode = MagicMock()
        mock_mode.id = "qa"
        mock_mode.name = "QA Agent"
        mock_mode.description = "QA Description"

        mock_category = MagicMock()
        mock_category.id = "role"
        mock_category.current_mode_id = "qa"
        mock_category.available_modes = [mock_mode]

        mock_agent_instance.get_modes = AsyncMock(return_value=[mock_category])

        response = await xeno_acp_agent.new_session(request)

        assert response.session_id is not None
        assert response.modes is not None
        assert response.modes.current_mode_id == "qa"
        assert len(response.modes.available_modes) == 1
        assert response.modes.available_modes[0].id == "qa"


@pytest.mark.asyncio
async def test_prompt(xeno_acp_agent):
    session_id = "test-session"
    xeno_acp_agent.sessions[session_id] = MagicMock()
    mock_agent = xeno_acp_agent.sessions[session_id]

    # Mock run_stream to yield events
    async def mock_stream(prompt):
        # Use class helper methods which handle internal structure
        yield PartDeltaEvent.text(index=0, content="Hello")
        yield PartDeltaEvent.text(index=0, content=" World")
        yield StreamCompleteEvent(message=MagicMock())

    mock_agent.run_stream = mock_stream

    request = PromptRequest(session_id=session_id, prompt=[TextContentBlock(text="Hi")])

    response = await xeno_acp_agent.prompt(request)

    assert response.stop_reason == "end_turn"
    # verify connection.session_update called twice
    assert xeno_acp_agent.connection.session_update.call_count == 2


@pytest.mark.asyncio
async def test_set_session_mode(xeno_acp_agent):
    session_id = "sess1"
    mock_agent = AsyncMock()
    xeno_acp_agent.sessions[session_id] = mock_agent

    req = SetSessionModeRequest(session_id=session_id, mode_id="fault")
    resp = await xeno_acp_agent.set_session_mode(req)

    assert resp is not None
    mock_agent.set_mode.assert_called_with("fault", category_id="role")


@pytest.mark.asyncio
async def test_other_methods(xeno_acp_agent, tmp_path_fixture):
    """Test other methods that return None or empty."""
    assert await xeno_acp_agent.set_session_model(SetSessionModelRequest(session_id="s", model_id="m")) is None
    assert await xeno_acp_agent.set_session_config_option(SetSessionConfigOptionRequest(session_id="s", config_id="c", valueId="v")) is None

    # List sessions
    xeno_acp_agent.sessions["s1"] = MagicMock()
    resp = await xeno_acp_agent.list_sessions(ListSessionsRequest())
    assert len(resp.sessions) == 1
    assert resp.sessions[0].session_id == "s1"

    # Load session
    resp = await xeno_acp_agent.load_session(LoadSessionRequest(session_id="s2", cwd=str(tmp_path_fixture)))
    assert "s2" in xeno_acp_agent.sessions


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "xeno-agent v0.1.0" in result.stdout


def test_cli_serve():
    # Mock acp_serve and XenoConfig loading
    with (
        patch("xeno_agent.main.acp_serve", new_callable=AsyncMock),
        patch("xeno_agent.main.XenoConfig") as MockConfig,
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", new_callable=MagicMock),
    ):
        MockConfig.model_validate.return_value = MagicMock()

        # We need to mock asyncio.run to avoid running of event loop in test
        with patch("asyncio.run") as mock_run:
            result = runner.invoke(app, ["serve", "--config-path", "dummy.yaml"])
            assert result.exit_code == 0
            mock_run.assert_called_once()
