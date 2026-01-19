from typing import TYPE_CHECKING

from crewai import Agent, Task
from crewai.flow import Flow, human_feedback, listen, or_, router, start

from xeno_agent.utils.logging import get_logger

if TYPE_CHECKING:
    from xeno_agent.agents import AgentRegistry
from .signals import (
    AskFollowupSignal,
    CompletionSignal,
    NewTaskSignal,
    SimulationSignal,
    SwitchModeSignal,
)
from .state import SimulationState, TaskFrame

logger = get_logger(__name__)


class XenoSimulationFlow(Flow[SimulationState]):
    """
    核心仿真流程控制器 - 基于调用栈的多智能体任务编排系统.

    架构说明:
    - 使用调用栈 (stack) 管理任务上下文, 支持 GOTO (switch_mode), GOSUB (new_task), RETURN (complete)
    - 支持隔离上下文 (isolated战斗) 与非隔离上下文的任务执行
    - 通过信号机制 (Signals) 实现模式切换、任务委托、完成和 HITL 交互

    状态初始化规则:
    - 使用类属性 `initial_state` 定义状态类型
    - 通过 **kwargs 传入初始值, 不建议在 __init__ 中直接赋值 self.state
    - Flow 内部会自动调用 _create_initial_state() 初始化状态

    Args:
        Flow[SimulationState]: 使用 SimulationState 作为状态类型
    """

    initial_state = SimulationState

    def __init__(self, agent_registry: "AgentRegistry", **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent_registry = agent_registry

    @start()
    def initialize(self) -> None:
        """Initializes the simulation state."""

        # Ensure we have at least one frame if not present
        if not self.state.stack:
            # Default to Q&A Assistant if no initial state
            self.state.stack.append(TaskFrame(mode_slug="qa_assistant", task_id="root", trigger_message="System initialized.", is_isolated=False))
        logger.info(f"[Flow] Initialized in mode: {self.state.stack[-1].mode_slug}")

    @listen(or_(initialize, "execute_agent"))
    def execute_agent_step(self) -> str:
        """
        Executes current agent on top of stack.

        Returns:
            Next state transition identifier
        """
        current_frame = self.state.stack[-1]
        logger.info(f"[Flow] Executing agent: {current_frame.mode_slug} (Task: {current_frame.task_id})")

        # Get agent from registry
        agent: Agent = self.agent_registry.get(current_frame.mode_slug)

        # Prepare context (conversation history) if not isolated
        context = ""
        if not current_frame.is_isolated:
            context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.state.conversation_history])

        # Create CrewAI task from the current frame
        task = Task(
            description=current_frame.trigger_message + (f"\n\nContext:\n{context}" if context else ""),
            expected_output=f"Result for task {current_frame.task_id}",
            agent=agent,
            tools=agent.tools,
        )

        # Execute task via CrewAI
        try:
            result = task.execute_sync()
            current_frame.result = result.raw if hasattr(result, "raw") else str(result)
            # Store result if needed, but mainly we look for signals raised by tools

        except SimulationSignal as e:
            logger.info(f"[Flow] Caught signal: {type(e).__name__}")
            self.state.last_signal = e
            return "agent_completed"
        except Exception as e:
            logger.exception(f"[Flow] Agent execution failed: {e}")
            raise e
        else:
            # If no signal raised, it means agent finished "normally" (e.g. just chatted)
            # In RFC 002, normal finish = continue conversation or wait for user
            self.state.last_signal = None
            return "agent_completed"

    def route(self) -> str:
        """
        The Kernel Router.
        Inspects last signal and determines next state transition.

        Returns:
            Next state transition identifier
        """
        if self.state.is_terminated:
            return "finish"

        last_signal = self.state.last_signal

        # If no signal (first run) or just continuation, execute current agent
        if last_signal is None:
            # Only ask for approval if we are NOT in the first run (initialization)
            # So if we are here, it MUST be after an agent step.
            return "ask_completion_approval"

        # --- Handle Signals ---

        if isinstance(last_signal, SwitchModeSignal):
            # GOTO: Replace current stack frame (or push new if designed that way? RFC says SwitchMode is GOTO)
            # "Switching the current agent role" usually implies replacing the current handler for the *same* task?
            # Or does it mean "Transfer control"?
            # In RFC 002: "SwitchModeSignal: Switch the current agent role (GOTO)"
            # Implementation: Update mode_slug of top frame
            logger.info(f"[Flow] Switching mode to: {last_signal.target_mode} (Reason: {last_signal.reason})")
            self.state.stack[-1].mode_slug = last_signal.target_mode
            self.state.last_signal = None
            return "execute_agent"

        if isinstance(last_signal, NewTaskSignal):
            # GOSUB: Push new frame
            logger.info(f"[Flow] New subtask: {last_signal.target_mode}")
            new_frame = TaskFrame(
                mode_slug=last_signal.target_mode,
                task_id=f"subtask_{len(self.state.stack)}",
                trigger_message=last_signal.message,
                caller_mode=self.state.stack[-1].mode_slug,
                is_isolated=False,  # Inherit context usually?
            )
            self.state.stack.append(new_frame)
            self.state.last_signal = None
            return "execute_agent"

        if isinstance(last_signal, CompletionSignal):
            # RETURN: Pop frame
            logger.info("[Flow] Task completion signal received")
            # Store result (maybe in history?)
            self.state.conversation_history.append({"role": "assistant", "content": last_signal.result})

            # Pop stack
            if self.state.stack:
                completed_frame = self.state.stack.pop()
                logger.info(f"[Flow] Popped frame: {completed_frame.mode_slug}")

            if not self.state.stack:
                self.state.final_output = last_signal.result
                self.state.is_terminated = True
                return "finish"

            self.state.last_signal = None
            return "execute_agent"

        if isinstance(last_signal, AskFollowupSignal):
            if self.state.auto_approve:
                logger.info(f"[AUTO-APPROVE] Agent asks: {last_signal.question}")
                # Record in history
                self.state.conversation_history.append({"role": "assistant", "content": last_signal.question})
                self.state.conversation_history.append({"role": "user", "content": "(Auto-approved)"})
                self.state.last_signal = None
                return "execute_agent"

            # Route to the feedback collecting state
            return "ask_human_feedback"

        # Default fallback: If no signal, ask for completion approval (HITL)
        return "ask_completion_approval"

    @router(execute_agent_step)
    def route_after_step(self) -> str:
        """
        Routes after agent execution step.

        Returns:
            Next state transition
        """
        return self.route()

    @listen("ask_completion_approval")
    @human_feedback(
        message="Agent 已完成任务，是否继续？",
        emit=["continue", "complete", "restart"],
        llm="gpt-4o-mini",
        default_outcome="continue",
    )
    def get_completion_approval(self) -> str:
        """获取任务完成后的用户决策"""
        # 返回当前模式名称，作为上下文显示给用户
        return self.state.stack[-1].mode_slug

    @listen("continue")
    def continue_in_same_mode(self, result: str) -> str:
        """继续当前模式"""
        # 不做任何操作，重新执行 Agent
        return "execute_agent"

    @listen("complete")
    def finish_current_task(self, result: str) -> str:
        """完成当前任务"""
        current_frame = self.state.stack.pop()
        logger.info(f"[Flow] Completed task: {current_frame.task_id}")

        if not self.state.stack:
            # 根任务完成
            self.state.final_output = current_frame.task_id
            self.state.is_terminated = True
            return "finish"
        return "execute_agent"

    @listen("restart")
    def restart_flow(self, result: str) -> str:
        """重新开始 Flow"""
        # 重置状态
        self.state.stack = [self.state.stack[0]]  # 保留初始帧
        self.state.conversation_history = []
        self.state.last_signal = None
        return "execute_agent"

    @human_feedback(message="Please provide your answer to the agent's question")
    def ask_human_feedback(self):
        """
        Requests feedback from the human when an AskFollowupSignal is received.
        The message will be the question from the signal.
        """
        last_signal = self.state.last_signal
        if isinstance(last_signal, AskFollowupSignal):
            return last_signal.question
        return "The agent has a follow-up question."

    @listen(ask_human_feedback)
    def handle_feedback(self, result):
        """
        Handles the result of the human feedback.
        """
        logger.info(f"[Flow] Received human feedback: {result.feedback}")

        last_signal = self.state.last_signal
        if isinstance(last_signal, AskFollowupSignal):
            # Record in history
            self.state.conversation_history.append({"role": "assistant", "content": last_signal.question})
            self.state.conversation_history.append({"role": "user", "content": result.feedback})

        self.state.last_signal = None
        return "execute_agent"

    @listen("finish")
    def handle_flow_termination(self) -> str | None:
        """
        Terminal handler for 'finish' event.
        Method name differs from event name to avoid infinite loop.
        Flow terminates when no listeners remain.
        """
        logger.info(f"[Flow] Simulation Finished. Final output: {self.state.final_output}")
        # Flow ends naturally here - no listeners waiting for this method
        return self.state.final_output
