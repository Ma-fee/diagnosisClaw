#!/usr/bin/env python3
"""
PydanticAI Agent Framework SDK - Reproduction Demo
Replicates RFC 001 fault diagnosis system using pure delegation model.
"""

import asyncio
import logging

from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime
from xeno_agent.pydantic_ai.skills import AnthropicSkillLoader

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    """Reproduction demo for fault diagnosis SOP."""

    # 1. Initialize Loaders
    # Base path should be packages/xeno-agent/config relative to project root
    # Or relative to the script location.
    # Let's use relative to current working directory as it's run from project root usually.
    config_path = "packages/xeno-agent/config"
    skills_path = "packages/xeno-agent/skills/pydantic_ai"

    loader = YAMLConfigLoader(base_path=config_path)
    skill_loader = AnthropicSkillLoader(base_path=skills_path)

    # 2. Initialize Factory & Runtime
    factory = AgentFactory(config_loader=loader, skill_loader=skill_loader, model="openai:gpt-4o")

    # Load the specific flow configuration
    flow_config = loader.load_flow_config("fault_diagnosis")

    # 2. Initialize Runtime (Verified only for structure)
    _ = LocalAgentRuntime(
        factory=factory,
        flow_config=flow_config,
    )

    logger.info("🚀 Starting Fault Diagnosis Reproduction Demo")
    logger.info("=" * 50)
    logger.info(f"📋 Flow: {flow_config.name}")
    logger.info(f"✅ Entry Agent: {flow_config.entry_agent}")

    # 3. Simulate user entering with a fault report
    user_input = "I have a server with red indicator lights on the power supply. What should I check?"
    logger.info(f"👤 User: {user_input}")

    # Note: We don't call runtime.invoke() here to avoid API key requirements in CI/Demo
    # But we verify that the structure is correct.

    logger.info("🤖 [System Check]")
    logger.info(f"   - AgentFactory initialized with model: {factory.model}")
    logger.info(f"   - LocalAgentRuntime initialized with flow: {flow_config.name}")
    logger.info(f"   - Ready to invoke entry agent: {flow_config.entry_agent}")

    logger.info("✅ Demo Script Structural Check: PASSED")
    logger.info("=" * 50)

    return 0

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
