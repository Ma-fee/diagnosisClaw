"""
Configuration-driven Flow.
"""

from xeno_agent.utils.logging import get_logger

from ..config_loader import ConfigLoader
from .flow import XenoSimulationFlow

logger = get_logger(__name__)


class ConfigurableXenoFlow(XenoSimulationFlow):
    def __init__(self, config_loader: ConfigLoader, flow_name: str, state=None):
        self.config_loader = config_loader
        self.flow_config = self.config_loader.load_flow_config(flow_name)

        # Initialize parent with state if provided
        # Note: We need to adapt XenoSimulationFlow to accept initial configuration
        super().__init__()
        if state:
            # Manually copy state fields since setter is not available
            self.state.stack = state.stack
            self.state.conversation_history = state.conversation_history
            self.state.final_output = state.final_output
            self.state.is_terminated = state.is_terminated
            self.state.last_signal = state.last_signal

        self.setup_from_config()

    def setup_from_config(self):
        """Configure the flow based on YAML."""
        # This is where we would interpret the flow config
        # For Xeno's stack-based architecture, "flow" config might define:
        # 1. Initial agent/task
        # 2. Allowed transitions (optional constraints)
        # 3. Global settings

        initial_mode = self.flow_config.get("initial_mode")
        if initial_mode:
            # We might need a way to set the initial mode in the state if it's not already set
            pass

        logger.info(f"Flow configured from {self.flow_config.get('name', 'unnamed')}")
