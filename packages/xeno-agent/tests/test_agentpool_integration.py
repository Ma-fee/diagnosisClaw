"""
Tests for agentpool integration.
"""

import agentpool
import pytest


def test_agentpool_import():
    """Test that agentpool can be imported."""
    assert agentpool is not None


def test_node_creation():
    """Test that a MessageNode can be created.

    This test will fail initially as part of the TDD RED phase.
    Once agentpool is properly integrated, this test should pass.
    """
    # TODO: Implement MessageNode creation using agentpool
    # This will fail until the integration is complete
    pytest.fail("MessageNode creation not yet implemented")
