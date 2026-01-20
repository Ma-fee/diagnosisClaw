import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from xeno_agent.agents.registry import AgentRegistry, load_agent_from_yaml
from xeno_agent.core.flow import XenoSimulationFlow
from xeno_agent.core.state import TaskFrame
from xeno_agent.utils.logging import get_logger, setup_logging

# Ensure correct paths
PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "config/roles"
TOOLS_DIR = PROJECT_ROOT / "config/tools"


async def main():
    # Setup Logging
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    setup_logging(level=log_level)
    logger = get_logger("rfc_demo")
    logger.setLevel(log_level)

    # Ensure xeno_agent logs are also visible at the requested level
    logging.getLogger("xeno_agent").setLevel(log_level)

    logger.info(f"Starting RFC 001 Compliant Agent System Demo (Log Level: {log_level_str})")

    # 1. Initialize Registry
    registry = AgentRegistry()

    # 2. Load Roles
    roles_to_load = ["qa_assistant.yaml", "fault_expert.yaml", "equipment_expert.yaml", "material_assistant.yaml"]

    for role_file in roles_to_load:
        yaml_path = ROLES_DIR / role_file
        if not yaml_path.exists():
            logger.error(f"Role file not found: {yaml_path}")
            continue

        logger.info(f"Loading role: {role_file}")
        slug = load_agent_from_yaml(str(yaml_path), registry)
        logger.info(f"Registered agent: {slug}")

    # 3. Create Aliases for RFC Compliance
    aliases = {
        "FaultExpert": "fault_expert",
        "EquipmentExpert": "equipment_expert",
        "MaterialAssistant": "material_assistant",
        "QaAssistant": "qa_assistant",
        "Q&A Assistant": "qa_assistant",
    }

    for alias, slug in aliases.items():
        if slug in registry._agents:
            registry.register(alias, registry._agents[slug])
            logger.info(f"Registered alias: {alias} -> {slug}")

    # 5. Start Simulation
    initial_user_query = "My excavator engine is overheating and emitting black smoke. I need to check the fuel injection pump manual."

    logger.info(f"Starting simulation with query: {initial_user_query}")

    # Initialize Flow with initial state via kwargs
    initial_stack = [TaskFrame(mode_slug="qa_assistant", task_id="root", trigger_message=initial_user_query, is_isolated=False)]

    flow = XenoSimulationFlow(agent_registry=registry, stack=initial_stack)

    # Run the flow
    try:
        # kickoff_async returns a result, usually the final output
        result = await flow.kickoff_async()

        logger.info("Simulation Completed Successfully!")
        logger.info(f"Final Result: {result}")

    except Exception:
        logger.exception("Simulation failed")


if __name__ == "__main__":
    asyncio.run(main())
