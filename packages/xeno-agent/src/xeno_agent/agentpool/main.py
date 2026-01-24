#!/usr/bin/env python3
"""
Xeno-Agent CLI using AgentPool Runtime

This module provides a CLI interface for running multi-agent flows using the
new agentpool-based runtime. It replaces the old pydantic_ai main.py
while maintaining the same CLI interface.
"""

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Any

from pydantic_ai.messages import ModelMessage

from xeno_agent.agentpool.loop import InteractionManager
from xeno_agent.pydantic_ai.acp_server import ACPAgent
from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.events import (
    AgentSwitchEvent,
    ContentEvent,
    ThoughtEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.skills import AnthropicSkillLoader, SkillRegistry
from xeno_agent.pydantic_ai.tool_manager import FlowToolManager
from xeno_agent.pydantic_ai.tools import (
    dialogue_management,
    document_retrieval,
    equipment_spec_lookup,
    fault_analysis,
    root_cause_investigation,
    search,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AgentPoolConfigLoader:
    """Load agentpool_config.yaml which contains both agents and flows."""

    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)

    def load(self) -> tuple[dict[str, Any], FlowConfig]:
        """Load agentpool_config.yaml and return (agents_dict, flow_config).

        Returns:
            A tuple of (agents_dict, flow_config) where:
            - agents_dict: dict of agent_id -> agent_config_dict
            - flow_config: FlowConfig object
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found at {self.config_path}")

        import yaml

        with self.config_path.open() as f:
            data = yaml.safe_load(f)

        if "flows" not in data or not data["flows"]:
            raise ValueError("No flows defined in config")

        # Get first flow (or specified flow)
        # For now, we'll assume single flow mode
        flow_data = next(iter(data["flows"].values()))

        agents_dict = data.get("agents", {})
        flow_config = FlowConfig(**flow_data)

        return agents_dict, flow_config


def _print_event(event: AgentSwitchEvent | ContentEvent | ThoughtEvent | ToolResultEvent | ToolStartEvent):
    """Print an event to console in a user-friendly format.

    Args:
        event: The event to print.
    """
    if isinstance(event, ContentEvent):
        print(f"🤖 Agent: {event.delta}")
    elif isinstance(event, ThoughtEvent):
        # Only show thinking in debug mode
        logger.debug(f"💭 Thinking: {event.delta}")
    elif isinstance(event, ToolStartEvent):
        logger.info(f"🔧 Calling tool: {event.name}({event.args})")
    elif isinstance(event, ToolResultEvent):
        logger.debug(f"✅ Tool result: {event.result[:100]}")
    elif isinstance(event, AgentSwitchEvent):
        print(f"🔄 Switching to agent: {event.name} ({event.agent_id})")


async def run_flow(
    flow_id: str,
    message: str,
    model: str,
    interactive: bool,
    config_path: Path,
    skills_path: Path,
):
    """Execute a multi-agent flow using agentpool runtime.

    Args:
        flow_id: The ID of the flow to run.
        message: Initial message to send.
        model: LLM model identifier.
        interactive: Whether to enable interactive mode.
        config_path: Path to agentpool_config.yaml.
        skills_path: Path to skills directory.
    """
    config_path = Path(config_path)
    skills_path = Path(skills_path)

    if not config_path.exists():
        logger.error(f"Configuration file not found at {config_path}")
        return

    # 1. Initialize Loaders & Registry
    skill_loader = AnthropicSkillLoader(base_path=skills_path)
    skill_registry = SkillRegistry()

    # Register builtin tools
    skill_registry.register("fault_analysis", fault_analysis, expected_params=["fault_description"])
    skill_registry.register("equipment_spec_lookup", equipment_spec_lookup, expected_params=["equipment_id"])
    skill_registry.register("document_retrieval", document_retrieval, expected_params=["document_id"])
    skill_registry.register("search", search, expected_params=["query"])
    skill_registry.register("dialogue_management", dialogue_management, expected_params=["history"])
    skill_registry.register("root_cause_investigation", root_cause_investigation, expected_params=["case_id"])

    # 2. Load agentpool config
    pool_config_loader = AgentPoolConfigLoader(config_path)
    agents_dict, flow_config = pool_config_loader.load()

    logger.info(f"Loaded flow: {flow_config.name}")
    logger.info(f"Entry agent: {flow_config.entry_agent}")

    # 3. Initialize Factory & Flow Config
    # Use agents_dict for loading agent configs (not skill_loader)
    from xeno_agent.pydantic_ai.config_loader import ConfigLoader

    class DictConfigLoader(ConfigLoader):
        """Config loader that reads from loaded agents dict."""

        def __init__(self, agents_dict: dict[str, Any]):
            self.agents_dict = agents_dict

        def load_agent_config(self, agent_id: str):
            from xeno_agent.pydantic_ai.models import AgentConfig

            if agent_id not in self.agents_dict:
                raise FileNotFoundError(f"Agent '{agent_id}' not found in config")

            return AgentConfig(**self.agents_dict[agent_id])

        def load_flow_config(self, flow_id: str):
            # Not used for agentpool config (we pass flow_config directly)
            raise NotImplementedError("load_flow_config not used in agentpool config mode")

        def list_agents(self) -> list[str]:
            return list(self.agents_dict.keys())

    dict_loader = DictConfigLoader(agents_dict)
    factory = AgentFactory(config_loader=dict_loader, skill_loader=skill_loader, skill_registry=skill_registry, model=model)

    # 4. Create FlowToolManager (Flow-Scoped MCP)
    tool_manager = FlowToolManager(flow_config.tools)

    # 5. Initialize MCP connections
    try:
        logger.info(f"Initializing {len(flow_config.tools.mcp_servers)} MCP servers...")
        await tool_manager.initialize()
        logger.info(f"MCP servers initialized: {[s.name for s in flow_config.tools.mcp_servers]}")
    except Exception:
        logger.exception("Failed to initialize MCP servers")
        return

    try:
        # 6. Initialize InteractionManager (agentpool runtime)
        manager = InteractionManager(factory=factory, flow_config=flow_config, tool_manager=tool_manager, model=model)

        logger.info(f"Model: {model}")

        # 7. Execution Loop
        if not interactive:
            # Single-shot run
            logger.info(f"👤 User: {message}")
            logger.info("Thinking...")
            try:
                async for event in manager.stream(flow_config.entry_agent, message):
                    _print_event(event)
                logger.info("✅ Completed")
            except Exception:
                logger.exception("Error during execution")
                return
        else:
            # Interactive mode
            print("\n" + "=" * 50)
            print("🎯 Interactive mode enabled")
            print("Type 'exit' or 'quit' to stop")
            print("=" * 50 + "\n")

            message_history: list[ModelMessage] = []
            session_id: str | None = None

            while True:
                try:
                    user_input = input("👤 User: ").strip()
                    if not user_input:
                        continue
                    if user_input.lower() in ["exit", "quit"]:
                        print("\n👋 Goodbye!")
                        break

                    print("\nThinking...\n")
                    async for event in manager.stream(
                        flow_config.entry_agent,
                        user_input,
                        history=message_history,
                        session_id=session_id,
                    ):
                        _print_event(event)

                    # Update message history and session_id for next interaction
                    # Note: The current implementation doesn't return history directly
                    # This will be enhanced in future versions
                    session_id = f"session_{asyncio.current_task().get_name()}" if asyncio.current_task() else None

                    print()  # Empty line between interactions

                except KeyboardInterrupt:
                    print("\n\n👋 Interrupted by user. Goodbye!")
                    break
                except Exception:
                    logger.exception("Error during execution")

    finally:
        # 8. Cleanup MCP connections
        logger.info("Closing MCP connections...")
        await tool_manager.cleanup()
        logger.info("All connections closed")


async def run_acp(flow_id: str, model: str, config_path: Path, skills_path: Path):
    """Run ACP server with Flow-Scoped MCP support.

    Note: This is currently a placeholder that delegates to the old ACPAgent.
    Future versions will integrate directly with InteractionManager.

    Args:
        flow_id: The ID of the flow to run.
        model: LLM model identifier.
        config_path: Path to config directory.
        skills_path: Path to skills directory.
    """
    config_path = Path(config_path)
    skills_path = Path(skills_path)

    if not config_path.exists():
        logger.error(f"Configuration directory not found at {config_path}")
        return

    # For now, use the old ACP implementation
    # This will be migrated to agentpool in a future task
    logger.warning("ACP mode currently uses legacy implementation. Full agentpool ACP support coming soon.")

    from acp import run_agent

    # 1. Initialize Loaders
    loader = YAMLConfigLoader(base_path=config_path)
    skill_loader = AnthropicSkillLoader(base_path=skills_path)
    skill_registry = SkillRegistry()

    # Register tools
    skill_registry.register("fault_analysis", fault_analysis, expected_params=["fault_description"])
    skill_registry.register("equipment_spec_lookup", equipment_spec_lookup, expected_params=["equipment_id"])
    skill_registry.register("document_retrieval", document_retrieval, expected_params=["document_id"])
    skill_registry.register("search", search, expected_params=["query"])
    skill_registry.register("dialogue_management", dialogue_management, expected_params=["history"])
    skill_registry.register("root_cause_investigation", root_cause_investigation, expected_params=["case_id"])

    # 2. Initialize Factory & Flow Config
    factory = AgentFactory(config_loader=loader, skill_loader=skill_loader, skill_registry=skill_registry, model=model)

    try:
        flow_config = loader.load_flow_config(flow_id)
    except FileNotFoundError:
        logger.exception(f"Flow configuration '{flow_id}.yaml' not found in {config_path}/flows/")
        return

    # 3. Create FlowToolManager
    tool_manager = FlowToolManager(flow_config.tools)

    # 4. Initialize MCP connections
    try:
        logger.info(f"Initializing {len(flow_config.tools.mcp_servers)} MCP servers for ACP...")
        await tool_manager.initialize()
        logger.info(f"MCP servers initialized: {[s.name for s in flow_config.tools.mcp_servers]}")
    except Exception:
        logger.exception("Failed to initialize MCP servers for ACP")
        return

    try:
        # 5. Create ACP Agent with Tool Manager
        acp_agent = ACPAgent(factory=factory, flow_config=flow_config, tool_manager=tool_manager)

        logger.info(f"Starting ACP Agent for flow: {flow_config.name}")
        logger.info(f"Entry Agent: {flow_config.entry_agent}")
        logger.info(f"Model: {model}")

        # 6. Run ACP Server
        await run_agent(acp_agent)

    finally:
        # 7. Cleanup MCP connections
        logger.info("Closing MCP connections...")
        await tool_manager.cleanup()
        logger.info("All connections closed")


def main():
    """Main entry point for xeno-agent CLI."""
    # Calculate default paths relative to this file
    # File is at: packages/xeno-agent/src/xeno_agent/agentpool/main.py
    # 1: agentpool, 2: xeno_agent, 3: src, 4: xeno-agent
    base_pkg_path = Path(__file__).parents[3]
    default_config_path = base_pkg_path / "config" / "agentpool_config.yaml"
    default_skills_path = base_pkg_path / "skills" / "pydantic_ai"

    parser = argparse.ArgumentParser(
        description="Xeno-Agent CLI using AgentPool Runtime - Multi-Agent Flow Execution System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single-shot execution
  uv run xeno-agent fault_diagnosis "My network is down" --model "openai:svc/glm-4.7"

  # Interactive mode
  uv run xeno-agent fault_diagnosis -i

  # ACP server mode
  uv run xeno-agent fault_diagnosis --acp
        """,
    )

    parser.add_argument("flow", help="Flow ID to execute (e.g., fault_diagnosis)")
    parser.add_argument("message", nargs="?", help="Initial message to send", default="")
    parser.add_argument(
        "--model",
        default="openai:svc/glm-4.7",
        help="LLM model identifier with litellm backend (default: openai:svc/glm-4.7)",
    )
    parser.add_argument("-i", "--interactive", action="store_true", help="Enable interactive chat mode")
    parser.add_argument("--acp", action="store_true", help="Run as ACP server instead of CLI mode")
    parser.add_argument(
        "--config-path",
        type=Path,
        default=default_config_path,
        help=f"Path to agentpool_config.yaml (default: {default_config_path})",
    )
    parser.add_argument(
        "--skills-path",
        type=Path,
        default=default_skills_path,
        help=f"Path to skills directory (default: {default_skills_path})",
    )

    args = parser.parse_args()

    if not args.interactive and not args.message:
        parser.error("Initial message is required when not in interactive mode.")

    asyncio.run(
        run_flow(args.flow, args.message, args.model, args.interactive, args.config_path, args.skills_path)
        if not args.acp
        else run_acp(args.flow, args.model, args.config_path, args.skills_path),
    )


if __name__ == "__main__":
    main()
