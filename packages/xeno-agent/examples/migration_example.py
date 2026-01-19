# examples/migration_example.py
from crewai.flow.flow import listen, router

from xeno_agent import (
    SimulationState,
    SwitchModeSignal,
    TaskFrame,
    XenoSimulationFlow,
    human_feedback,
)
from xeno_agent.agents.registry import AgentRegistry
from xeno_agent.core.signals import CompletionSignal


# Mock registry for example
class MockRegistry(AgentRegistry):
    def get(self, mode_slug: str):
        from crewai import Agent

        return Agent(role=mode_slug, goal="Test", backstory="Test")


class MigratedFlow(XenoSimulationFlow):
    @router("execute_agent")
    def route_decision(self):
        """Agent 执行后的路由决策"""
        # 保留信号路由
        if isinstance(self.state.last_signal, SwitchModeSignal):
            return "switch_mode"
        if isinstance(self.state.last_signal, CompletionSignal):
            return "completion"

        # 正常完成 - 使用 CrewAI HITL
        return "ask_user_feedback"

    @listen("ask_user_feedback")
    @human_feedback(
        message="Agent 已完成当前任务，下一步操作？",
        emit=["continue_same", "switch_expert", "complete"],
        llm="gpt-4o-mini",
        default_outcome="continue_same",
    )
    def get_user_decision(self):
        """获取用户决策"""
        # 返回当前模式名称（任意值）
        return self.state.stack[-1].mode_slug

    @listen("continue_same")
    def continue_mode(self, result):
        """继续当前模式"""
        print(f"Continuing mode: {result}")
        return "execute_agent"

    @listen("switch_expert")
    def switch_to_expert(self, result):
        """切换到故障专家"""
        # 创建新信号
        self.state.last_signal = SwitchModeSignal(target_mode="fault_expert", reason="用户请求专家介入")
        return "switch_mode"

    @listen("complete")
    def complete_flow(self, result):
        """完成 Flow"""
        self.state.is_terminated = True
        return "finish"


if __name__ == "__main__":
    registry = MockRegistry()
    state = SimulationState(
        stack=[TaskFrame(mode_slug="qa_assistant", task_id="test", trigger_message="hi", is_isolated=False)],
        conversation_history=[],
        final_output=None,
        is_terminated=False,
        last_signal=None,
    )

    # Run flow
    flow = MigratedFlow(agent_registry=registry, state=state)
    flow.kickoff()
