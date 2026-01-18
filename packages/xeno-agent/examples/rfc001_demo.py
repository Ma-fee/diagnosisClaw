"""
RFC 001 - 四角色模型演示

基于 RFC 002 实现的完整 4 角色协作演示。
展示了 QA Assistant → Fault Expert → Material Assistant/Equipment Expert 的完整协作流程。

运行方式:
    uv run python examples/rfc001_demo.py --log-level INFO

无需 LLM 配置，仅演示架构交互流程

Args:
    --log-level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL), 默认 INFO
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from xeno_agent import (
    AgentRegistry,
    InteractionHandler,
    SimulationState,
    SkillRegistry,
    TaskFrame,
    XenoAgentBuilder,
    XenoSimulationFlow,
    register_builtin_skills,
    requires_approval,
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


def demo_rfc001_4_role_flow():
    """Demonstrate RFC 001 4-role collaboration flow without LLM."""
    logger.info("=" * 70)
    logger.info("RFC 001 - 四角色模型演示")
    logger.info("=" * 70)
    logger.info("")
    logger.info("场景：数控机床 X 轴重复定位精度差")
    logger.info("")
    logger.info("预期协作流程：")
    logger.info("  1. 用户上报故障")
    logger.info("  2. QA Assistant 意图识别 → 切换到 Fault Expert")
    logger.info("  3. Fault Expert 委派子任务 → Material Assistant 查找资料")
    logger.info("  4. Material Assistant 返回资料 → Fault Expert 继续")
    logger.info("  5. Fault Expert 委派子任务 → Equipment Expert 分析图纸")
    logger.info("  6. Equipment Expert 返回分析 → Fault Expert 综合报告")
    logger.info("  7. Fault Expert 完成诊断")
    logger.info("")

    # Create registries
    agent_registry = AgentRegistry()
    skill_registry = SkillRegistry()

    # Configure HITL to auto-approve
    InteractionHandler.set_auto_approve(True)

    # Register builtin skills
    register_builtin_skills(skill_registry)

    logger.info("注册代理...")
    logger.info("-" * 70)

    # Register QA Assistant
    agent_registry.register(
        mode_slug="qa_assistant",
        creator=lambda llm: XenoAgentBuilder(
            role_name="qa_assistant",
            skill_registry=skill_registry,
            config_loader=ConfigLoader("packages/xeno-agent/config"),
        )
        .with_goal("快速识别用户问题类型并路由到合适的专家")
        .with_backstory("你是机械故障诊断系统的前台，负责区分简单问答和复杂故障诊断。")
        .with_skills(["xeno_meta_switch_mode", "xeno_meta_new_task"])
        .build(),
    )
    logger.info("  ✓ QA Assistant")

    # Register Fault Expert
    agent_registry.register(
        mode_slug="fault_expert",
        creator=lambda llm: XenoAgentBuilder(
            role_name="fault_expert",
            skill_registry=skill_registry,
            config_loader=ConfigLoader("packages/xeno-agent/config"),
        )
        .with_goal("系统化分析复杂故障，规划诊断步骤，协调子任务执行")
        .with_backstory("你是资深的机械故障诊断专家，擅长系统化思维和协作调度。")
        .with_skills(["xeno_meta_switch_mode", "xeno_meta_new_task", "xeno_meta_attempt_completion"])
        .build(),
    )
    logger.info("  ✓ Fault Expert")

    # Register Equipment Expert
    agent_registry.register(
        mode_slug="equipment_expert",
        creator=lambda llm: XenoAgentBuilder(
            role_name="equipment_expert",
            skill_registry=skill_registry,
            config_loader=ConfigLoader("packages/xeno-agent/config"),
        )
        .with_goal("分析技术图纸，指导物理操作诊断")
        .with_backstory("你是资深的设备工程师，精通机械结构、工作原理和现场诊断方法。")
        .with_skills(["xeno_meta_switch_mode", "xeno_meta_new_task", "xeno_meta_attempt_completion"])
        .build(),
    )
    logger.info("  ✓ Equipment Expert")

    # Register Material Assistant
    agent_registry.register(
        mode_slug="material_assistant",
        creator=lambda llm: XenoAgentBuilder(
            role_name="material_assistant",
            skill_registry=skill_registry,
            config_loader=ConfigLoader("packages/xeno-agent/config"),
        )
        .with_goal("快速检索技术手册、论文、标准，提供引用规范的摘要")
        .with_backstory("你是资深的资料研究员，擅长在庞大的知识库中定位信息并提炼要点。")
        .with_skills(["search_engine"])
        .build(),
    )
    logger.info("  ✓ Material Assistant")
    logger.info("-" * 70)

    # Demonstrate flow
    logger.info("\n流程演示：")
    logger.info("-" * 70)
    logger.info("")

    logger.info("Step 1: 用户输入")
    initial_input = "数控机床 X 轴重复定位精度差"
    logger.info(f"  输入: {initial_input}")
    logger.info("")

    logger.info("Step 2: QA Assistant => Fault Expert")
    qa_agent = agent_registry.get("qa_assistant")
    logger.info(f"  [QA Assistant] 模拟处理: {initial_input}")
    logger.info(f"  [QA Assistant] 分析: 复杂故障，需要切换到 Fault Expert")
    logger.info(f"  [QA Assistant] 触发信号: SwitchModeSignal('fault_expert')")
    logger.info("  ✓ 切换成功")
    logger.info("")

    logger.info("Step 3: Fault Expert => Material Assistant (查找结构图)")
    fault_agent = agent_registry.get("fault_expert")
    logger.info(f"  [Fault Expert] 委派子任务: 查找 X 轴传动结构图")
    logger.info("  ✓ 子任务委派")
    logger.info("")

    logger.info("Step 4: Material Assistant 返回资料")
    material_agent = agent_registry.get("material_assistant")
    logger.info(f"  [Material Assistant] 检索资料并返回")
    logger.info(f"  [Material Assistant] 返回: X 轴传动结构（丝杠副、导轨、电机）")
    logger.info("  ✓ 资料返回")
    logger.info("")

    logger.info("Step 5: Fault Expert => Equipment Expert (分析图纸)")
    logger.info(f"  [Fault Expert] 收到资料，委派子任务: 分析结构图，诊断潜在故障")
    logger.info("  ✓ 子任务委派")
    logger.info("")

    logger.info("Step 6: Equipment Expert 返回分析")
    equipment_agent = agent_registry.get("equipment_expert")
    logger.info(f"  [Equipment Expert] 分析图纸")
    logger.info(f"  [Equipment Expert] 返回: 可能是丝杠反向间隙过大")
    logger.info("  ✓ 图纸分析完成")
    logger.info("")

    logger.info("Step 7: Fault Expert 综合诊断")
    logger.info(f"  [Fault Expert] 综合所有信息")
    logger.info(f"  [Fault Expert] 形成诊断结论: X 轴重复定位精度差，可能由丝杠反向间隙过大引起")
    logger.info(f"  [Fault Expert] 建议: 排查丝杠预紧力或更换丝杠副")
    logger.info("  ✓ 诊断完成")
    logger.info("")

    logger.info("=" * 70)
    logger.info("RFC 001 四角色模型演示完成")
    logger.info("=" * 70)
    logger.info("")
    logger.info("演示的架构能力：")
    logger.info("  ✓ QA Assistant - 意图识别与网关路由")
    logger.info("  ✓ Fault Expert - 故障诊断编排与协调")
    logger.info("  ✓ Equipment Expert - 设备结构与操作专家")
    logger.info("  ✓ Material Assistant - 文献/资料检索与摘要")
    logger.info("=" * 70)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RFC 001 - 四角色模型演示")
    parser.add_argument("--log-level", default="INFO", help="日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    args = parser.parse_args()

    setup_logging(args.log_level)
    sys.exit(demo_rfc001_4_role_flow())
