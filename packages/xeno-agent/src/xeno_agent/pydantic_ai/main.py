#!/usr/bin/env python3
import argparse
import asyncio
import logging
from pathlib import Path

from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.factory import AgentFactory

# Import SDK components
from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime
from xeno_agent.pydantic_ai.skills import AnthropicSkillLoader

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def run_flow(flow_id: str, message: str, model: str, interactive: bool):
    """
    Executes a multi-agent flow using the PydanticAI SDK.
    """
    # Find project root (6 levels up from this file)
    # File is at: packages/xeno-agent/src/xeno_agent/pydantic_ai/main.py
    # 1: pydantic_ai, 2: xeno_agent, 3: src, 4: xeno-agent, 5: packages, 6: root
    project_root = Path(__file__).parents[5]

    # Configuration paths relative to project root
    config_path = project_root / "packages" / "xeno-agent" / "config"
    skills_path = project_root / "packages" / "xeno-agent" / "skills" / "pydantic_ai"

    if not config_path.exists():
        logger.error(f"Configuration directory not found at {config_path}")
        return

    # 1. Initialize Loaders
    loader = YAMLConfigLoader(base_path=config_path)
    skill_loader = AnthropicSkillLoader(base_path=skills_path)

    # 2. Initialize Factory & Runtime
    factory = AgentFactory(config_loader=loader, skill_loader=skill_loader, model=model)

    try:
        flow_config = loader.load_flow_config(flow_id)
    except FileNotFoundError:
        logger.exception(f"Flow configuration '{flow_id}.yaml' not found in {config_path}/flows/")
        return

    runtime = LocalAgentRuntime(factory=factory, flow_config=flow_config)

    logger.info(f"Started Flow: {flow_config.name} (Entry Agent: {flow_config.entry_agent})")
    logger.info(f"Model: {model}")

    # 3. Execution Loop
    if interactive:
        logger.info("Interactive mode enabled (type 'exit' or 'quit' to stop)")
        while True:
            try:
                user_input = input("\n👤 User: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit"]:
                    break

                logger.info("Thinking...")
                result = await runtime.invoke(flow_config.entry_agent, user_input)
                logger.info(f"Agent: {result.data}")

                if "trace_id" in result.metadata:
                    logger.info(f"TraceID: {result.metadata['trace_id']}")

            except KeyboardInterrupt:
                break
            except Exception:
                logger.exception("Error during execution")
    else:
        # Single-shot run
        logger.info(f"User: {message}")
        logger.info("Thinking...")
        try:
            result = await runtime.invoke(flow_config.entry_agent, message)
            logger.info(f"Agent: {result.data}")
            logger.info(f"Completed | TraceID: {result.metadata.get('trace_id')}")
        except Exception:
            logger.exception("Error during execution")


def main():
    parser = argparse.ArgumentParser(description="PydanticAI Flow CLI Runner")

    parser.add_argument("flow", help="Flow ID to execute (e.g., fault_diagnosis)")
    parser.add_argument("message", nargs="?", help="Initial message to send", default="")
    parser.add_argument("--model", default="openai:gpt-4o", help="LLM model identifier (default: openai:gpt-4o)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Enable interactive chat mode")

    args = parser.parse_args()

    if not args.interactive and not args.message:
        parser.error("Initial message is required when not in interactive mode.")

    asyncio.run(run_flow(args.flow, args.message, args.model, args.interactive))


if __name__ == "__main__":
    main()
