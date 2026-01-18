"""
Configuration-driven Flow extension of XenoSimulationFlow.
"""

from xeno_agent.utils.logging import get_logger

from ..config_loader import ConfigLoader
from .flow import XenoSimulationFlow

logger = get_logger(__name__)


class ConfigurableXenoFlow(XenoSimulationFlow):
    def __init__(self, agent_registry, config_loader: ConfigLoader, flow_name: str, **kwargs):
        self.config_loader = config_loader
        self.flow_config = self.config_loader.load_flow_config(flow_name)

        # Initialize parent with state via kwargs
        super().__init__(agent_registry=agent_registry, **kwargs)

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
