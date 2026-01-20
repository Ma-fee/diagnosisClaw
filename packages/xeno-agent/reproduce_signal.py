from crewai import Agent
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class TestSignal(BaseException):
    pass


class SignalTool(BaseTool):
    name: str = "signal_tool"
    description: str = "Raises a signal."

    class Input(BaseModel):
        msg: str = Field(..., description="Message")

    args_schema: type[BaseModel] = Input

    def _run(self, msg: str) -> None:
        print(f"Raising signal with {msg}")
        raise TestSignal(msg)


def test_signal_propagation():
    tool = SignalTool()

    Agent(
        role="Tester",
        goal="Test signal propagation",
        backstory="I test things.",
        tools=[tool],
        verbose=True,
        llm="gpt-4o-mini",  # Dummy, won't be used if we force tool use?
        # We need a real LLM or a mock that calls the tool.
    )

    # We can test the tool directly wrapped by CrewAI's execution logic if possible,
    # but the Agent.execute_task is where the catching happens.

    # Let's try to run a task. Since we don't have a reliable mock LLM here easily without key,
    # we can try to rely on the fact that if the tool IS called, does it crash?
    # But without an LLM key, Agent creation might fail or execution will fail before tool call.

    # Alternatively, we can inspect CrewAI source code if available, but we can't.

    # We can try to use the configured LLM from environment.


if __name__ == "__main__":
    # Just run the tool directly to verify it raises
    t = SignalTool()
    try:
        t._run("test")
    except TestSignal:
        print("Direct run caught signal")
    except Exception:
        print("Direct run caught Exception")

    # We want to know if Task execution catches it.
    # Without running a full agent, we can't be 100% sure about CrewAI's internal handling.
    # But usually libraries catch 'Exception', not 'BaseException'.
