"""
Main entry point for xeno-agent simulation CLI.

Provides a command-line interface for running agent simulations.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Literal

from xeno_agent import (
    SimulationState,
    TaskFrame,
    XenoSimulationFlow,
    create_crewai_llm,
    load_agent_from_yaml,
    test_connection,
)
from xeno_agent.agents.registry import AgentRegistry
from xeno_agent.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def setup_agents(agent_dir: Path, agent_registry: AgentRegistry, llm: Any) -> None:
    """
    Load agents from YAML directory and register them with built-in skills.

    Args:
        agent_dir: Directory containing agent YAML files
        agent_registry: Registry to store agents
        llm: LLM instance to use for agents
    """
    # Load agents from YAML files
    agent_files = list(agent_dir.glob("*_agent.yaml"))

    if not agent_files:
        logger.warning(f"Warning: No agent files found in {agent_dir}")
    else:
        for agent_file in agent_files:
            try:
                agent_file_path = str(agent_file)
                load_agent_from_yaml(agent_file_path, agent_registry, llm=llm)
                logger.info(f"✓ Loaded agent from {agent_file.name}")
            except Exception as e:
                logger.error(f"✗ Failed to load agent from {agent_file.name}: {e}")

    logger.info(f"\nTotal agents registered: {len(agent_registry._agents)}")


def run_simulation(
    prompt: str,
    initial_mode: str,
    agent_registry: AgentRegistry,
    auto_approve: bool = False,
) -> Literal[0, 1, 130]:
    """
    Run a simulation with given prompt.

    Args:
        prompt: The initial user prompt
        initial_mode: The mode/agent to start with
        agent_registry: Registry containing agents
        auto_approve: Whether to auto-approve tool executions

    Returns:
        Exit code: 0 for success, 1 for error, 130 for keyboard interrupt
    """
    if auto_approve:
        logger.info("Auto-approve enabled: Tools will execute without confirmation.\n")

    # Create initial state
    state = SimulationState(
        stack=[
            TaskFrame(
                mode_slug=initial_mode,
                task_id="root_task",
                trigger_message=prompt,
                caller_mode=None,
            ),
        ],
        conversation_history=[],
        is_terminated=False,
        auto_approve=auto_approve,
    )

    # Create and run Flow
    flow = XenoSimulationFlow(
        agent_registry=agent_registry,
        state=state,
    )

    logger.info("=== Starting Simulation ===")
    logger.info(f"Initial mode: {initial_mode}")
    logger.info(f"Prompt: {prompt}\n")

    try:
        flow.kickoff()
        logger.info("\n=== Simulation Complete ===")
        logger.info(f"Final output: {flow.state.final_output}")
        return 0
    except KeyboardInterrupt:
        logger.warning("\n\nSimulation interrupted by user.")
        return 130
    except Exception as e:
        logger.exception(f"\n\nSimulation failed with error: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Xeno-Agent: Multi-agent simulation system")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test LLM connection")
    test_parser.add_argument("--api-base", help="LLM API base URL")
    test_parser.add_argument("--model", help="LLM model name")
    test_parser.add_argument("--api-key", help="LLM API key")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a simulation")
    run_parser.add_argument("prompt", help="The initial prompt for the simulation")
    run_parser.add_argument(
        "--mode",
        "-m",
        default="pm",
        help="Initial mode/agent to use (default: pm)",
    )
    run_parser.add_argument(
        "--agents",
        "-a",
        default=str(Path(__file__).parent / "agents"),
        help="Directory containing agent YAML files",
    )
    run_parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve tool executions without asking (Test Mode)",
    )
    run_parser.add_argument(
        "--disable-hitl",
        action="store_true",
        help="Disable HITL completely (All interactions auto-approved)",
    )
    # LLM configuration
    run_parser.add_argument("--api-base", help="LLM API base URL")
    run_parser.add_argument("--model", help="LLM model name")
    run_parser.add_argument("--api-key", help="LLM API key")

    args = parser.parse_args()

    setup_logging()

    if args.command == "test":
        # Test LLM connection
        success = test_connection(api_base=args.api_base, model=args.model, api_key=args.api_key)
        sys.exit(0 if success else 1)

    elif args.command == "run":
        # Create registries
        agent_registry = AgentRegistry()
        # skill_registry = SkillRegistry() # Removed

        # Create LLM instance
        llm = create_crewai_llm(api_base=args.api_base, model=args.model, api_key=args.api_key)

        # Setup agents
        agent_dir = Path(args.agents)
        if not agent_dir.exists():
            logger.error(f"Error: Agent directory not found: {agent_dir}")
            sys.exit(1)

        setup_agents(agent_dir, agent_registry, llm)

        # Determine auto-approve
        auto_approve = False
        if args.disable_hitl:
            logger.warning("HITL disabled via --disable-hitl. All interactions will be auto-approved.")
            auto_approve = True
        elif args.auto_approve:
            logger.info("Auto-approve enabled via --auto-approve.")
            auto_approve = True

        # Run simulation
        return run_simulation(args.prompt, args.mode, agent_registry, auto_approve=auto_approve)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
