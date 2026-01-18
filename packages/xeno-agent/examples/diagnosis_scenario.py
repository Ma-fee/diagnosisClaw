"""
Example: Running a fault diagnosis simulation scenario.
"""

import sys
from pathlib import Path

# Add src to path if running from examples
sys.path.append(str(Path(__file__).parent.parent / "src"))

from xeno_agent import (
    AgentRegistry,
    InteractionHandler,
    SimulationState,
    SkillRegistry,
    TaskFrame,
    XenoSimulationFlow,
    create_crewai_llm,
    load_agent_from_yaml,
    register_builtin_skills,
)


def setup_diagnosis_agents(llm, agent_registry, skill_registry):
    """Load all diagnosis-related agents."""
    # Point to config/roles instead of src/xeno_agent/agents
    agents_dir = Path(__file__).parent.parent / "config" / "roles"

    diagnosis_agents = [
        "symptom_collector_agent.yaml",
        "diagnosis_analyst_agent.yaml",
        "rootcause_finder_agent.yaml",
        "solution_generator_agent.yaml",
        "verification_agent.yaml",
    ]

    for agent_file in diagnosis_agents:
        agent_path = agents_dir / agent_file
        if agent_path.exists():
            try:
                load_agent_from_yaml(str(agent_path), agent_registry=agent_registry, skill_registry=skill_registry, llm=llm)
                print(f"✓ Loaded {agent_file}")
            except Exception as e:
                print(f"✗ Failed to load {agent_file}: {e}")
        else:
            print(f"✗ Agent file not found: {agent_path}")


def run_diagnosis_scenario(incident_description: str, auto_approve: bool = True):
    """
    Run a fault diagnosis simulation.

    Args:
        incident_description: Description of the incident/failure
        auto_approve: Whether to auto-approve tool executions
    """
    # Configure HITL
    if auto_approve:
        InteractionHandler.set_auto_approve(True)

    # Create LLM
    # Note: Ensure OPENAI_API_KEY or similar is set in environment
    try:
        llm = create_crewai_llm()
    except Exception as e:
        print(f"Warning: Failed to create LLM ({e}). Using mock/fake LLM might be needed if no API key.")
        # For now, let it fail if no key, or user can set it.
        # But to be safe in offline mode without keys, we might want a fallback.
        # Assuming the environment has keys or we want to test compilation.
        raise e

    # Instantiate registries
    skill_registry = SkillRegistry()
    agent_registry = AgentRegistry()

    # Register built-in skills (includes diagnostic tools)
    register_builtin_skills(skill_registry)

    # Load diagnosis agents
    setup_diagnosis_agents(llm, agent_registry, skill_registry)

    # Create initial state with Symptom Collector as first step
    state = SimulationState(
        stack=[
            TaskFrame(
                mode_slug="symptom_collector",  # Must match the role/mode registered
                task_id="incident_001",
                trigger_message=f"""
故障事件: {incident_description}

请:
1. 收集所有相关的系统指标和日志
2. 识别关键症状和异常
3. 整理成结构化的症状报告
4. 将结果传递给诊断分析师进行分析
                """.strip(),
                caller_mode=None,
                is_isolated=False,
            ),
        ],
        conversation_history=[{"role": "user", "content": incident_description}],
        final_output=None,
        is_terminated=False,
        last_signal=None,
    )

    # Create and run flow
    flow = XenoSimulationFlow(agent_registry=agent_registry)
    # Manually copy state fields since setter is not available
    flow.state.stack = state.stack
    flow.state.conversation_history = state.conversation_history
    flow.state.final_output = state.final_output
    flow.state.is_terminated = state.is_terminated
    flow.state.last_signal = state.last_signal

    print("\n" + "=" * 60)
    print("开始故障诊断模拟")
    print("=" * 60 + "\n")

    try:
        flow.kickoff()

        print("\n" + "=" * 60)
        print("诊断模拟完成")
        print("=" * 60)
        print(f"\n最终输出:\n{state.final_output}")
        return 0

    except KeyboardInterrupt:
        print("\n\n模拟被用户中断。")
        return 130
    except Exception as e:
        print(f"\n\n模拟失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # Example incident
    incident = """
从 10:15 开始，API 网关出现连接超时错误，错误率上升到 0.05。
用户反馈访问缓慢，部分请求失败。监控系统显示 CPU 使用率 85%。
数据库连接池接近上限。
    """

    # Run simulation
    sys.exit(run_diagnosis_scenario(incident, auto_approve=True))
