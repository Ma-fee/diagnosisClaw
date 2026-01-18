from crewai.flow.flow import Flow, listen, router, start

from xeno_agent.utils.logging import get_logger

from .hitl import InteractionHandler
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

    def __init__(self, agent_registry, **kwargs):
        super().__init__(**kwargs)
        self.agent_registry = agent_registry

    @start()
    def initialize(self):
        """Initializes the simulation state."""
        # Ensure we have at least one frame if not present
        if not self.state.stack:
            # Default to Q&A Assistant if no initial state
            self.state.stack.append(TaskFrame(mode_slug="qa_assistant", task_id="root", trigger_message="System initialized.", is_isolated=False))
        logger.info(f"[Flow] Initialized in mode: {self.state.stack[-1].mode_slug}")
        return "execute_agent"

    @router(initialize)
    def route(self):
        """
        The Kernel Router.
        Inspects the last signal and determines the next state transition.
        """
        if self.state.is_terminated:
            return "finish"

        last_signal = self.state.last_signal

        # If no signal (first run) or just continuation, execute current agent
        if last_signal is None:
            return "execute_agent"

        # --- Handle Signals ---

        if isinstance(last_signal, SwitchModeSignal):
            # GOTO: Pop current, Push new
            current_frame = self.state.stack.pop()
            new_frame = TaskFrame(
                mode_slug=last_signal.target_mode,
                task_id=f"{current_frame.task_id}_switched",
                trigger_message=f"Switched from {current_frame.mode_slug}. Reason: {last_signal.reason}",
                caller_mode=current_frame.caller_mode,
                is_isolated=current_frame.is_isolated,  # Inherit isolation
            )
            self.state.stack.append(new_frame)
            logger.info(f"[Flow] Switched to {new_frame.mode_slug}")
            self.state.last_signal = None  # Reset signal
            return "execute_agent"

        if isinstance(last_signal, NewTaskSignal):
            # GOSUB: Push new frame
            new_frame = TaskFrame(
                mode_slug=last_signal.target_mode,
                task_id=f"subtask_{len(self.state.stack)}",
                trigger_message=last_signal.message,
                caller_mode=self.state.stack[-1].mode_slug,
                is_isolated=True,  # FORCE ISOLATION
            )
            self.state.stack.append(new_frame)
            logger.info(f"[Flow] New Task delegated to {new_frame.mode_slug}")
            self.state.last_signal = None
            return "execute_agent"

        if isinstance(last_signal, CompletionSignal):
            # RETURN: Pop frame
            result = last_signal.result
            completed_frame = self.state.stack.pop()

            if self.state.stack:
                # Returned to caller
                logger.info(f"[Flow] Subtask completed. Returning to {self.state.stack[-1].mode_slug}")

                # 【新增】将子任务结果注入到父上下文
                if result:
                    # 添加到 conversation_history, 使父任务可见
                    self.state.conversation_history.append(
                        {
                            "role": "assistant",
                            "content": f"[子任务结果] {result}",
                            "metadata": {"source": "new_task", "child_agent": completed_frame.mode_slug, "task_id": completed_frame.task_id},
                        },
                    )
                    logger.info(f"[Flow] Injected subtask result into context: {result[:100]}...")

                self.state.last_signal = None
                return "execute_agent"
            # Root completed
            self.state.final_output = result
            self.state.is_terminated = True
            return "finish"

        if isinstance(last_signal, AskFollowupSignal):
            # HITL Input
            logger.info(f"[Flow] Agent asks: {last_signal.question}")
            answer = InteractionHandler.get_input("Your Answer")

            # Record in history
            self.state.conversation_history.append({"role": "assistant", "content": last_signal.question})
            self.state.conversation_history.append({"role": "user", "content": answer})

            self.state.last_signal = None
            return "execute_agent"

        # Default fallback
        return "execute_agent"

    @listen("execute_agent")
    def execute_agent_step(self):
        """
        Executes the current agent on the top of the stack.
        """
        current_frame = self.state.stack[-1]

        # Retrieve the Agent object from Registry
        agent = self.agent_registry.get(current_frame.mode_slug)

        # Construct inputs based on isolation
        if current_frame.is_isolated:
            # Isolated task: no conversation history, only current trigger
            context = current_frame.trigger_message
        else:
            # Normal task: include conversation history
            history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.state.conversation_history])
            context = f"""
Previous conversation:
{history_text}

Current task:
{current_frame.trigger_message}
""".strip()

        logger.info(f"[Flow] Executing agent: {current_frame.mode_slug}")

        try:
            # Execute the agent with CrewAI
            # Using single task execution via Crew
            from crewai import Crew, Task

            task = Task(
                description=context,
                expected_output="A response that addresses the task appropriately.",
                agent=agent,
            )

            crew = Crew(agents=[agent], tasks=[task], verbose=True)

            # Run the task
            result_obj = crew.kickoff()
            result = str(result_obj)

            # Update conversation history if not isolated
            if not current_frame.is_isolated:
                self.state.conversation_history.append({"role": "assistant", "content": result})

            logger.info(f"[Flow] Agent output: {result[:100]}...")

            # Check if agent raised a signal
            if self.state.last_signal is None:
                # [RFC 002] Agent completed normally without signal
                # 【修改】正常完成 = 继续对话 (不终止)
                # 除非显式调用 attempt_completion, 否则不退出
                logger.info(f"[Flow] Agent {current_frame.mode_slug} completed normally (no signal). Continuing conversation in same mode.")
                # 继续当前模式 (不重新推入agent, 直接等待下一轮用户输入)
                # 在实际使用中, 会由外部触发下一轮执行
                return "agent_completed"
                return "agent_completed"

        except SimulationSignal as e:
            # The agent raised a signal (switch_mode, new_task, etc.)
            self.state.last_signal = e
            logger.info(f"[Flow] Signal caught: {e.__class__.__name__}")
            return "signal_caught"

        except Exception as e:
            # Unexpected error
            logger.exception(f"[Flow] Error executing agent: {e}")
            raise e

        return "agent_completed"

    @router(execute_agent_step)
    def route_after_step(self):
        """
        Routes after agent execution step.
        """
        return self.route()

    @listen("finish")
    def finish(self):
        logger.info("[Flow] Simulation Finished.")
        return self.state.final_output
