"""
CLI for running Xeno Agent flows.
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from xeno_agent import (
    InteractionHandler,
    SimulationState,
    TaskFrame,
    XenoSimulationFlow,
    create_crewai_llm,
    register_builtin_skills,
)
from xeno_agent.agents import AgentRegistry, SkillRegistry, load_agent_from_yaml
from xeno_agent.config_loader import ConfigLoader
from xeno_agent.tool_factory import DynamicToolFactory


def main():
    parser = argparse.ArgumentParser(description="Run Xeno Agent Flow")
    parser.add_argument("--flow", required=True, help="Name of the flow to run")
    parser.add_argument("--config-root", default=str(Path(__file__).parent.parent / "config"), help="Root config directory")
    parser.add_argument("--incident", help="Incident description for diagnosis flow", default="System failure detected.")
    parser.add_argument("--auto-approve", action="store_true", help="Auto approve tool execution")

    args = parser.parse_args()

    # 1. Initialize Config Loader
    loader = ConfigLoader(args.config_root)

    # 2. Load Flow Config
    try:
        flow_config = loader.load_flow_config(args.flow)
    except Exception as e:
        print(f"Error loading flow config: {e}")
        sys.exit(1)

    # 3. Setup Environment
    if args.auto_approve:
        InteractionHandler.set_auto_approve(True)

    try:
        llm = create_crewai_llm()
    except Exception as e:
        print(f"Warning: LLM creation failed ({e}). Proceeding might fail.")
        llm = None

    # 4. Register Tools from Config
    # Instantiate registries
    skill_registry = SkillRegistry()
    agent_registry = AgentRegistry()

    # First register built-ins to ensure base registry is ready
    register_builtin_skills(skill_registry)

    for tool_name in flow_config.get("tools", []):
        try:
            tool_conf = loader.load_tool_config(tool_name)

            # Use factory to create tool
            tool_instance = DynamicToolFactory.create_tool(tool_name, tool_conf)

            if tool_instance:
                skill_registry.register(tool_name, tool_instance, tool_conf.get("description"))
                print(f"✓ Registered tool: {tool_name}")
            else:
                print(f"⚠ Could not instantiate tool {tool_name}")

        except Exception as e:
            print(f"✗ Failed to load tool {tool_name}: {e}")

    # 5. Load Agents from Config
    for agent_name in flow_config.get("agents", []):
        try:
            # We can reuse load_agent_from_yaml but pointing to config/roles
            agent_path = loader.roles_dir / f"{agent_name}.yaml"
            load_agent_from_yaml(str(agent_path), agent_registry=agent_registry, skill_registry=skill_registry, llm=llm)
            print(f"✓ Loaded agent: {agent_name}")
        except Exception as e:
            print(f"✗ Failed to load agent {agent_name}: {e}")

    # 6. Initialize State
    initial_mode = flow_config.get("initial_mode")
    if not initial_mode:
        print("Error: Flow config must specify 'initial_mode'")
        sys.exit(1)

    state = SimulationState(
        stack=[
            TaskFrame(
                mode_slug=initial_mode,
                task_id="cli_task_001",
                trigger_message=args.incident,
                caller_mode=None,
                is_isolated=False,
            ),
        ],
        conversation_history=[{"role": "user", "content": args.incident}],
        final_output=None,
        is_terminated=False,
        last_signal=None,
    )

    # 7. Run Flow
    # Use base class directly to avoid potential decorator inheritance issues
    flow = XenoSimulationFlow(agent_registry=agent_registry)

    # Manual state injection

    flow.state.stack = state.stack
    flow.state.conversation_history = state.conversation_history
    flow.state.final_output = state.final_output
    flow.state.is_terminated = state.is_terminated
    flow.state.last_signal = state.last_signal

    print(f"\nStarting Flow: {args.flow}")
    try:
        flow.kickoff()
        print("\nFlow completed successfully.")
        print(f"Final Output: {flow.state.final_output}")
    except KeyboardInterrupt:
        print("\nFlow interrupted.")
    except Exception as e:
        print(f"\nFlow failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
