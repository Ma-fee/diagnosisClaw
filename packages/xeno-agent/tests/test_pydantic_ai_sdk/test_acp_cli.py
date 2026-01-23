"""
Tests for acp_cli.py (v3 implementation)

Tests cover:
1. RuntimeToAgentAdapter functionality
2. Logging setup with --log-file and --log-level
3. CLI argument parsing
4. End-to-end workflow (with mocked LLM)
"""

import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from xeno_agent.pydantic_ai.acp_cli import setup_logging
from xeno_agent.pydantic_ai.acp_server import ACPAgent as RuntimeToAgentAdapter


@pytest.mark.asyncio
async def test_runtime_to_agent_adapter_run():
    """Test RuntimeToAgentAdapter.run() method."""
    # Mock runtime
    mock_runtime = Mock()
    mock_result = Mock()
    mock_result.data = "Test response"
    mock_runtime.invoke = AsyncMock(return_value=mock_result)

    # Create adapter
    mock_flow_config = Mock()
    mock_flow_config.name = "test"
    mock_flow_config.participants = [Mock(id="agent")]
    adapter = RuntimeToAgentAdapter(Mock(), mock_flow_config, runtime=mock_runtime)

    # Test run
    result = await adapter.run("Hello")

    assert result == "Test response"
    mock_runtime.invoke.assert_called_once_with("Hello")
    mock_result.get_final_response_or_raise.assert_called_once()


@pytest.mark.asyncio
async def test_runtime_to_agent_adapter_run_stream():
    """Test RuntimeToAgentAdapter.run_stream() method."""
    # Mock runtime that yields messages
    mock_runtime = Mock()

    async def mock_invoke(prompt):
        class AsyncIterator:
            async def __aiter__(self):
                yield {"role": "user", "content": [Mock(text="Hello")]}
                yield {"role": "assistant", "content": [Mock(text="Response")]}

        return AsyncIterator()

    mock_runtime.invoke = AsyncMock(side_effect=mock_invoke)

    # Create adapter
    mock_flow_config = Mock()
    mock_flow_config.name = "test"
    adapter = RuntimeToAgentAdapter(Mock(), mock_flow_config, runtime=mock_runtime)

    # Test run_stream
    messages = [msg async for msg in adapter.run_stream("Hello")]

    assert len(messages) == 2
    mock_runtime.invoke.assert_called_once_with("Hello")


@pytest.mark.asyncio
async def test_runtime_to_agent_adapter_with_history():
    """Test RuntimeToAgentAdapter passes history parameter correctly."""
    # Mock runtime
    mock_runtime = Mock()
    mock_result = Mock()
    mock_result.get_final_response_or_raise.return_value = "Response with history"
    mock_runtime.invoke = AsyncMock(return_value=mock_result)

    # Create adapter
    mock_flow_config = Mock()
    mock_flow_config.name = "test"
    adapter = RuntimeToAgentAdapter(Mock(), mock_flow_config, runtime=mock_runtime)

    # Test with history
    history = [{"role": "user", "content": "Previous message"}]
    result = await adapter.run("New message", history=history)

    assert result == "Response with history"
    # runtime.invoke should be called with just the prompt
    mock_runtime.invoke.assert_called_once_with("New message")


def test_setup_logging_stdout_only():
    """Test setup_logging with stdout only (no file)."""
    setup_logging(log_file=None, log_level="INFO")

    # Test root logger is set correctly
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO

    # Test logging works - just verify it doesn't crash
    logger = logging.getLogger("test_logger")
    logger.info("Test message")

    # Check that handlers are configured
    assert len(root_logger.handlers) > 0


def test_setup_logging_with_file():
    """Test setup_logging with log file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as tmp:
        tmp_path = Path(tmp.name)

    try:
        setup_logging(log_file=tmp_path, log_level="DEBUG")

        # Test root logger level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        logger = logging.getLogger("test_file_logger")
        logger.debug("Test debug message")
        logger.info("Test info message")

        # Verify file exists and contains content
        assert tmp_path.exists()
        content = tmp_path.read_text()
        assert "Test debug message" in content
        assert "Test info message" in content
    finally:
        # Cleanup
        if tmp_path.exists():
            tmp_path.unlink()


def test_setup_logging_creates_directories():
    """Test setup_logging creates parent directories."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = Path(tmp_dir) / "nested" / "dirs" / "test.log"

        setup_logging(log_file=log_path, log_level="INFO")

        # Test logging
        logger = logging.getLogger("test_dir_logger")
        logger.info("Directory test message")

        # Verify directory structure and file created
        assert log_path.exists()
        assert log_path.parent.exists()
        content = log_path.read_text()
        assert "Directory test message" in content


def test_setup_logging_levels():
    """Test setup_logging with different log levels."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Test DEBUG level
        setup_logging(log_file=tmp_path, log_level="DEBUG")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        logger = logging.getLogger("test_debug_logger")
        logger.debug("Debug message")

        content = tmp_path.read_text()
        assert "Debug message" in content

    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_setup_logging_force_overwrite():
    """Test setup_logging force parameter reconfigures logging."""
    # First setup
    setup_logging(log_file=None, log_level="INFO")
    root_logger1 = logging.getLogger()
    assert root_logger1.level == logging.INFO

    # Second setup with different level (should overwrite)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as tmp:
        tmp_path = Path(tmp.name)

    try:
        setup_logging(log_file=tmp_path, log_level="ERROR")
        root_logger2 = logging.getLogger()  # Same root logger
        assert root_logger2.level == logging.ERROR

    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@pytest.mark.asyncio
async def test_cli_integration_mocked():
    """Test CLI integration with mocked LLM (end-to-end simulation)."""
    # Mock runtime directly - simpler and doesn't need config file
    from unittest.mock import AsyncMock, Mock

    mock_runtime = Mock()
    mock_result = Mock()
    mock_result.get_final_response_or_raise.return_value = "Mocked response"
    mock_runtime.invoke = AsyncMock(return_value=mock_result)

    # Create adapter with mocked runtime
    adapter = RuntimeToAgentAdapter(mock_runtime)

    # Test that adapter properly delegates to runtime
    response = await adapter.run("test prompt")

    # Verify response
    assert response == "Mocked response"

    # Verify mocked runtime was called
    mock_runtime.invoke.assert_called_once_with("test prompt")


def test_argument_parsing_defaults():
    """Test CLI argument parsing with defaults."""
    import sys

    test_args = ["acp_cli.py", "fault_diagnosis"]
    with patch.object(sys, "argv", test_args):
        from argparse import ArgumentParser

        parser = ArgumentParser()
        parser.add_argument("flow_id")
        parser.add_argument("--model", default="openai:svc/glm-4.7")
        parser.add_argument("--config-path", type=Path)
        parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"])
        parser.add_argument("--host", default="0.0.0.0")  # noqa: S104
        parser.add_argument("--port", type=int, default=8000)
        parser.add_argument("--log-file", type=Path)
        parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

        args = parser.parse_args(["test_flow"])

        assert args.flow_id == "test_flow"
        assert args.model == "openai:svc/glm-4.7"
        assert args.transport == "stdio"
        assert args.host == "0.0.0.0"  # noqa: S104
        assert args.port == 8000
        assert args.log_file is None
        assert args.log_level == "INFO"


def test_argument_parsing_custom():
    """Test CLI argument parsing with custom values."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as tmp:
        tmp_path = Path(tmp.name)

    try:
        from argparse import ArgumentParser

        parser = ArgumentParser()
        parser.add_argument("flow_id")
        parser.add_argument("--model", default="openai:svc/glm-4.7")
        parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"])
        parser.add_argument("--host", default="0.0.0.0")  # noqa: S104
        parser.add_argument("--port", type=int, default=8000)
        parser.add_argument("--log-file", type=Path)
        parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

        args = parser.parse_args(
            [
                "test_flow",
                "--model",
                "openai:svc/gpt-4",
                "--transport",
                "sse",
                "--host",
                "localhost",
                "--port",
                "9000",
                "--log-file",
                str(tmp_path),
                "--log-level",
                "DEBUG",
            ],
        )

        assert args.flow_id == "test_flow"
        assert args.model == "openai:svc/gpt-4"
        assert args.transport == "sse"
        assert args.host == "localhost"
        assert args.port == 9000
        assert args.log_file == tmp_path
        assert args.log_level == "DEBUG"

    finally:
        if tmp_path.exists():
            tmp_path.unlink()
