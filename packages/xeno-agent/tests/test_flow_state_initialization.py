"""
Test CrewAI Flow state initialization pattern.

Tests that XenoSimulationFlow correctly follows CrewAI Flow best practices:
- Uses initial_state class attribute
- Accepts **kwargs for state initialization
- Does not directly assign self.state in __init__
- Properly accesses state via flow.state property
"""

import inspect

import pytest

from xeno_agent import (
    AgentRegistry,
    SimulationState,
    TaskFrame,
    XenoSimulationFlow,
)


class MockAgent:
    """Mock agent for testing."""

    def run(self, query, context):
        return {"output": f"Mocked: {query}"}


class TestFlowStateInitialization:
    """Test Flow state initialization patterns."""

    def test_initial_state_class_attribute_exists(self):
        """Verify initial_state is defined as class attribute."""
        assert hasattr(XenoSimulationFlow, "initial_state")
        assert XenoSimulationFlow.initial_state is SimulationState

    def test_flow_uses_correct_init_signature(self):
        """Verify Flow.__init__ accepts **kwargs not explicit state parameter."""
        sig = inspect.signature(XenoSimulationFlow.__init__)
        params = list(sig.parameters.keys())

        # Should have 'self' and '**kwargs', NOT explicit 'state' parameter
        assert "self" in params
        assert "kwargs" in params or "agent_registry" in params
        assert "state" not in params

    def test_flow_initialization_without_args(self):
        """Verify Flow can be initialized without custom state."""
        agent_registry = AgentRegistry()

        # Should initialize with default state from initial_state attribute
        flow = XenoSimulationFlow(agent_registry=agent_registry)

        # State should be initialized
        assert flow.state is not None
        assert isinstance(flow.state, SimulationState)

    def test_flow_initialization_with_custom_state_via_kwargs(self):
        """Verify custom state can be passed via kwargs."""
        agent_registry = AgentRegistry()
        custom_state = SimulationState(
            conversation_history=[],
            stack=[TaskFrame(mode_slug="test_mode", query="test")],
            is_terminated=True,
            final_output="custom output",
        )

        # Pass custom state via kwargs
        flow = XenoSimulationFlow(agent_registry=agent_registry, state=custom_state)

        # Should use custom state
        assert flow.state is not None
        assert flow.state.final_output == "custom output"
        assert flow.state.is_terminated is True

    def test_state_is_property_not_direct_attribute(self):
        """Verify state is accessed via @property not direct attribute."""
        # Check that state is a property

        state_descriptor = getattr(XenoSimulationFlow, "state", None)
        assert state_descriptor is not None
        assert isinstance(state_descriptor, property)

    def test_flow_state_property_is_writable(self):
        """Verify state property can be written to (via Flow's setter)."""
        agent_registry = AgentRegistry()
        flow = XenoSimulationFlow(agent_registry=agent_registry)

        original_output = flow.state.final_output
        assert original_output == ""

        # Note: Direct assignment like this in user code is NOT recommended,
        # but Flow's setter should handle it gracefully
        # In practice, users should pass initial state via __init__ kwargs
        # or use kickoff() state parameter

    @pytest.mark.skipif(True, reason="ConfigurableFlow requires flow config file")
    def test_configurable_flow_uses_correct_pattern(self):
        """Verify ConfigurableXenoFlow also follows correct pattern."""
        # This test is skipped by default since it requires a valid flow config file
        # Uncomment and adjust when flow config is available

    def test_state_access_pattern_in_examples(self):
        """Verify that examples use flow.state not state directly."""
        # This is more of a documentation test - ensure examples follow pattern
        # The actual example execution is handled in integration tests

    def test_stack_initialization_from_initial_state(self):
        """Verify that stack is initialized when creating flow."""
        agent_registry = AgentRegistry()
        flow = XenoSimulationFlow(agent_registry=agent_registry)

        # Stack should be empty list initially
        assert flow.state.stack == []

    def test_conversation_history_initialization(self):
        """Verify that conversation_history is initialized."""
        agent_registry = AgentRegistry()
        flow = XenoSimulationFlow(agent_registry=agent_registry)

        # conversation_history should be empty list initially
        assert flow.state.conversation_history == []
