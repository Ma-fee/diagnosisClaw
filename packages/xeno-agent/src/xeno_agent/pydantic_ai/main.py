#!/usr/bin/env python3
import argparse
import asyncio
import logging
from pathlib import Path

from xeno_agent.pydantic_ai import tools
from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime
from xeno_agent.pydantic_ai.skills import AnthropicSkillLoader, SkillRegistry

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def run_flow(flow_id: str, message: str, model: str, interactive: bool, config_path: Path, skills_path: Path):
    """
    Executes a multi-agent flow using the PydanticAI SDK.
    """
    # Ensure paths are Path objects
    config_path = Path(config_path)
    skills_path = Path(skills_path)

    if not config_path.exists():
        logger.error(f"Configuration directory not found at {config_path}")
        return

    # 1. Initialize Loaders & Registry
    loader = YAMLConfigLoader(base_path=config_path)
    skill_loader = AnthropicSkillLoader(base_path=skills_path)
    skill_registry = SkillRegistry()

    # Register tools
    skill_registry.register("fault_analysis", tools.fault_analysis, expected_params=["fault_description"])
    skill_registry.register("equipment_spec_lookup", tools.equipment_spec_lookup, expected_params=["equipment_id"])
    skill_registry.register("document_retrieval", tools.document_retrieval, expected_params=["document_id"])
    skill_registry.register("search", tools.search, expected_params=["query"])
    skill_registry.register("dialogue_management", tools.dialogue_management, expected_params=["history"])
    skill_registry.register("root_cause_investigation", tools.root_cause_investigation, expected_params=["case_id"])

    # 2. Initialize Factory & Runtime
    factory = AgentFactory(config_loader=loader, skill_loader=skill_loader, skill_registry=skill_registry, model=model)

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
        session_id: str | None = None
        while True:
            try:
                user_input = input("\n👤 User: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit"]:
                    break

                logger.info("Thinking...")
                result = await runtime.invoke(flow_config.entry_agent, user_input, session_id=session_id)
                logger.info(f"Agent: {result.data}")

                # Update session_id for subsequent interactions
                session_id = result.metadata.get("session_id")

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
    # Calculate default paths relative to this file
    # File is at: packages/xeno-agent/src/xeno_agent/pydantic_ai/main.py
    # 1: pydantic_ai, 2: xeno_agent, 3: src, 4: xeno-agent
    base_pkg_path = Path(__file__).parents[3]
    default_config_path = base_pkg_path / "config"
    default_skills_path = base_pkg_path / "skills" / "pydantic_ai"

    parser = argparse.ArgumentParser(description="PydanticAI Flow CLI Runner")

    parser.add_argument("flow", help="Flow ID to execute (e.g., fault_diagnosis)")
    parser.add_argument("message", nargs="?", help="Initial message to send", default="")
    parser.add_argument("--model", default="openai:svc/glm-4.7", help="LLM model identifier with litellm backend (default: litellm/openai/gpt-4o)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Enable interactive chat mode")
    parser.add_argument("--config-path", type=Path, default=default_config_path, help=f"Path to configuration directory (default: {default_config_path})")
    parser.add_argument("--skills-path", type=Path, default=default_skills_path, help=f"Path to skills directory (default: {default_skills_path})")

    args = parser.parse_args()

    if not args.interactive and not args.message:
        parser.error("Initial message is required when not in interactive mode.")

    asyncio.run(run_flow(args.flow, args.message, args.model, args.interactive, args.config_path, args.skills_path))


if __name__ == "__main__":
    main()
