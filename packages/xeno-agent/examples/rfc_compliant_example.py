"""
RFC 002 Compliant Demonstration: 4-Role Collaborative Fault Diagnosis

This script demonstrates 4-role collaboration model defined in RFC 001/002:
1. Q&A Assistant - Gateway routing (simple → material, complex → fault expert)
2. Fault Expert - Diagnostic orchestration with subtask delegation
3. Equipment Expert - dual mode (Worker for analysis, Active for guidance)
4. Material Assistant - document retrieval with citations

Scenario: Numerical control (NC) machine X-axis position accuracy issues

运行方式:
    uv run python examples/rfc_compliant_example.py --log-level INFO

Args:
    --log-level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL), 默认 INFO
"""

import argparse
import logging
import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from xeno_agent import (
    AgentRegistry,
    InteractionHandler,
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


def load_rfc_compliant_agents(llm, agent_registry, skill_registry):
    """
    Load RFC 002 compliant roles (4-role collaboration model).
    Uses new XenoAgentBuilder.from_yaml() method.
    """
    # ConfigLoader needs config_root parameter
    config_root = str(Path(__file__).parent.parent / "config")
    config_loader = ConfigLoader(config_root)
    agents_dir = Path(config_root) / "roles"

    rfc_roles = [
        "qa_assistant",
        "fault_expert",
        "equipment_expert",
        "material_assistant",
    ]

    for role_name in rfc_roles:
        role_path = agents_dir / f"{role_name}.yaml"
        if role_path.exists():
            try:
                # Use factory to capture loop variables correctly
                def make_agent_creator(rn=role_name, rp=str(role_path)):
                    def agent_creator(llm=None):
                        return (
                            XenoAgentBuilder(
                                role_name=rn,
                                skill_registry=skill_registry,
                                config_loader=config_loader,
                            )
                            .from_yaml(rp)
                            .with_llm(llm)
                            .build()
                        )

                    return agent_creator

                # Register with correct API: (mode_slug, creator)
                agent_registry.register(mode_slug=role_name, creator=make_agent_creator())
                logger.info(f"✓ Loaded RFC role: {role_name}.yaml")
            except Exception as e:
                logger.error(f"✗ Failed to load {role_name}.yaml: {e}")
                traceback.print_exc()
        else:
            logger.error(f"✗ RFC role file not found: {role_path}")


def run_rfc_compliant_demo(auto_approve: bool = True):
    """
    Run RFC 002 compliant demonstration scenario.

    Scenario flow:
    1. User reports NC machine X-axis accuracy issue
    2. QA Assistant detects complex fault → switches to Fault Expert
    3. Fault Expert delegates subtasks:
       - Material Assistant: retrieve mechanical structure drawings
       - Material Assistant: retrieve servo motor specifications
    4. Equipment Expert analyzes drawings (Worker mode)
    5. Fault Expert synthesizes results → needs on-site guidance
    6. Fault Expert switches to Equipment Expert (Active mode)
    7. Equipment Expert provides step-by-step guidance
    8. Equipment Expert returns/ Fault Expert completes
    """
    # Configure HITL
    if auto_approve:
        InteractionHandler.set_auto_approve(True)

    # Create LLM
    try:
        llm = create_crewai_llm()
    except Exception as e:
        logger.warning(f"Failed to create LLM ({e}).")
        raise e

    # Instantiate registries
    skill_registry = SkillRegistry()
    agent_registry = AgentRegistry()

    # Register built-in skills
    register_builtin_skills(skill_registry)

    # Load RFC 002 compliant agents
    load_rfc_compliant_agents(llm, agent_registry, skill_registry)

    # Setup initial QA Assistant session
    incident_description = """
    【故障描述】
    设备型号: Fanuc 0i-MD 数控机床
    部位: X轴 ( X-Axis )
    症状: 重复定位精度差（反复移动后位置偏差 ±0.03mm）
    检查结果: 初步检查无明显松动或异常
    """

    # Create initial state starting with QA Assistant
    flow = XenoSimulationFlow(
        agent_registry=agent_registry,
        stack=[
            TaskFrame(
                mode_slug="qa_assistant",  # Matches qa_assistant.yaml name
                task_id="diagnosis_demo_001",
                trigger_message=incident_description,
                caller_mode=None,
                is_isolated=False,
            ),
        ],
        conversation_history=[
            {
                "role": "user",
                "content": incident_description,
            },
        ],
        final_output=None,
        is_terminated=False,
        last_signal=None,
    )

    logger.info(f"\n{'=' * 70}")
    logger.info("            RFC 002 Compliant 4-Role Collaboration Demo")
    logger.info(f"{'=' * 70}\n")
    logger.info("角色:")
    logger.info("  1. Q&A Assistant    - 意图识别与网关分发")
    logger.info("  2. Fault Expert      - 故障诊断编排与协调")
    logger.info("  3. Equipment Expert - 设备结构与操作专家 (双模式)")
    logger.info("  4. Material Assistant - 文献/资料检索与摘要")
    logger.info("")
    logger.info("预期流程:")
    logger.info("  User → QA Assistant → Fault Expert")
    logger.info("        Fault Expert → Material Assistant (查找结构图)")
    logger.info("        Fault Expert → Material Assistant (查找电机规格)")
    logger.info("        Fault Expert → Equipment Expert (Worker: 图纸分析)")
    logger.info("        Fault Expert → Equipment Expert (Active: 现场指导)")
    logger.info("        Equipment Expert (Active) → Fault Expert (或完成)")
    logger.info("")
    logger.info(f"{'-' * 70}\n")

    try:
        flow.kickoff()

        logger.info(f"\n{'=' * 70}")
        logger.info("                        演示完成")
        logger.info("=" * 70)
        logger.info(f"\n最终诊断报告:\n{flow.state.final_output}")
        logger.info(f"\n{'=' * 70}")
        return 0

    except KeyboardInterrupt:
        logger.error("\n\n演示被用户中断。")
        return 130
    except Exception as e:
        logger.error(f"\n\n演示失败: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RFC 002 Compliant 4-Role Demo")
    parser.add_argument("--log-level", default="INFO", help="日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--auto-approve", action="store_true", help="自动批准所有 HITL 交互（无需手动输入）")
    args = parser.parse_args()

    setup_logging(args.log_level)
    sys.exit(run_rfc_compliant_demo(auto_approve=args.auto_approve))
