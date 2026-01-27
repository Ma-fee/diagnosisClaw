"""Test configuration for xeno-agent."""

import os

# Disable observability in tests
os.environ["LOGFIRE_DISABLE"] = "true"
os.environ["OBSERVABILITY_ENABLED"] = "false"

# Configure pytest-asyncio to work with anyio
import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest for async testing."""
    # Set asyncio mode to auto to avoid strict mode conflicts
    config.option.asyncio_mode = "auto"


pytest_plugins = ("pytest_asyncio",)
