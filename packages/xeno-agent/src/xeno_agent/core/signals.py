class SimulationSignal(BaseException):
    """Base class for flow control signals raised by tools."""


class SwitchModeSignal(SimulationSignal):
    """Signal to switch the current agent role (GOTO)."""

    def __init__(self, target_mode: str, reason: str):
        self.target_mode = target_mode
        self.reason = reason


class NewTaskSignal(SimulationSignal):
    """Signal to create a sub-task (GOSUB)."""

    def __init__(self, target_mode: str, message: str, expected_output: str):
        self.target_mode = target_mode
        self.message = message
        self.expected_output = expected_output


class CompletionSignal(SimulationSignal):
    """Signal to complete the current task (RETURN)."""

    def __init__(self, result: str):
        self.result = result


class AskFollowupSignal(SimulationSignal):
    """Signal to ask the user a follow-up question."""

    def __init__(self, question: str, options: list[str] | None = None):
        self.question = question
        self.options = options


class UpdateTodoListSignal(SimulationSignal):
    """Signal to update the todo list."""

    def __init__(self, todos: list[dict[str, str]]):
        self.todos = todos
