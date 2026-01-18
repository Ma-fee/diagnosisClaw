"""
Example: RFC 002 Compliant 4-Role Fault Diagnosis Scenario.

This is an updated version using new 4-role collaboration model.
运行方式:
    uv run python examples/diagnosis_scenario.py --log-level INFO

Args:
    --log-level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL), 默认 INFO
"""

import argparse
import logging
import sys
import traceback
from pathlib import Path

# Add src to path if running from examples
sys.path.append(str(Path(__file__).parent.parent / "src"))

from xeno_agent import (
    AgentRegistry,
    InteractionHandler,
    SimulationState,
    SkillRegistry,
    TaskFrame,
    XenoAgentBuilder,
    XenoSimulationFlow,
    create_crewai_llm,
    register_builtin_skills,
)
from xeno_agent.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO"):
    """配置日志系统。"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def setup_diagnosis_agents(llm, agent_registry, skill_registry):
    """Load all diagnosis-related agents using RFC 002 4-role model."""
    # Point to config/roles instead of src/xeno_agent/agents
    config_root = str(Path(__file__).parent.parent / "config")
    config_loader = ConfigLoader(config_root)
    agents_dir = Path(config_root) / "roles"

    # RFC 002 compliant 4-role model
    rfc_agents = [
        "qa_assistant",
        "fault_expert",
        "equipment_expert",
        "material_assistant",
    ]

    # Optional: also load legacy agents for compatibility testing
    legacy_agents = [
        "symptom_collector_agent",
        "diagnosis_analyst_agent",
        "rootcause_finder_agent",
        "solution_generator_agent",
        "verification_agent",
    ]

    all_agents = rfc_agents + legacy_agents

    for role_name in all_agents:
        role_path = agents_dir / f"{role_name}.yaml"
        if role_path.exists():
            try:
                # Use factory to capture loop variables correctly
                def make_agent_creator(rn=role_name, rp=str(role_path)):
                    def agent_creator(llm_param=None):
                        return (
                            XenoAgentBuilder(
                                role_name=rn,
                                skill_registry=skill_registry,
                                config_loader=config_loader,
                            )
                            .from_yaml(rp)
                            .with_llm(llm_param or llm)
                            .build()
                        )

                    return agent_creator

                agent_registry.register(mode_slug=role_name, creator=make_agent_creator())

                logger.info(f"✓ Loaded RFC 002 role: {role_name}.yaml")
            except Exception as e:
                logger.error(f"✗ Failed to load {role_name}.yaml: {e}")
        else:
            logger.error(f"✗ Agent file not found: {role_path}")


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
        logger.warning(f"Failed to create LLM ({e}). Using mock/fake LLM might be needed if no API key.")
        # For now, let it fail if no key, or user can set it.
        # But to be safe in offline mode without keys, we might want a fallback.
        # Assuming environment has keys or we want to test compilation.
        raise e

    # Instantiate registries
    skill_registry = SkillRegistry()
    agent_registry = AgentRegistry()

    # Register built-in skills (includes diagnostic tools)
    register_builtin_skills(skill_registry)

    # Load diagnosis agents
    setup_diagnosis_agents(llm, agent_registry, skill_registry)

    # Create initial state with QA Assistant as first step (RFC 002 4-role model)
    # Use identifier not display name for mode_slug
    state = SimulationState(
        stack=[
            TaskFrame(
                mode_slug="qa_assistant",  # Must match role identifier for registry
                task_id="incident_001",
                trigger_message=incident,
                caller_mode=None,
                is_isolated=False,
            ),
        ],
        conversation_history=[{"role": "user", "content": incident}],
        final_output=None,
        is_terminated=False,
        last_signal=None,
    )

    flow = XenoSimulationFlow(agent_registry=agent_registry, state=state)

    logger.info(f"\n{'=' * 60}")
    logger.info("开始故障诊断模拟")
    logger.info(f"{'=' * 60}\n")

    try:
        flow.kickoff()

        logger.info(f"\n{'=' * 60}")
        logger.info("诊断模拟完成")
        logger.info(f"{'=' * 60}\n")
        logger.info(f"\n最终输出:\n{flow.state.final_output}")
        return 0

    except KeyboardInterrupt:
        logger.error("\n\n模拟被用户中断。")
        return 130
    except Exception as e:
        logger.error(f"\n\n模拟失败: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RFC 002 - 故障诊断模拟")
    parser.add_argument("--log-level", default="INFO", help="日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--auto-approve", type=bool, default=True, help="是否自动批准工具执行 (默认 True)")
    args = parser.parse_args()

    setup_logging(args.log_level)

    # Example incident - mechanical diagnosis scenario (fits 4-role model)
    incident = """
【故障描述】
设备型号: Fanuc 0i-MD 数控机床
部位: X轴 ( X-Axis )
症状: 重复定位精度差（反复移动后位置偏差 ±0.03mm）
检查结果: 初步检查无明显松动或异常
"""

    # Run simulation
    sys.exit(run_diagnosis_scenario(incident, auto_approve=args.auto_approve))
