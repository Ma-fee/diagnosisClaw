from collections.abc import Callable

from xeno_agent.utils.logging import get_logger

logger = get_logger(__name__)


class InteractionHandler:
    """
    Handles user interaction (input/output) for the simulation.
    Can be configured for interactive console mode or automated test mode.
    """

    _instance = None
    _auto_approve: bool = False
    _input_provider: Callable[[str], str] | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_auto_approve(cls, auto: bool):
        cls._auto_approve = auto

    @classmethod
    def set_input_provider(cls, provider: Callable[[str], str] | None):
        cls._input_provider = provider

    @classmethod
    def ask_approval(cls, message: str) -> bool:
        """
        Asks the user for approval.

        Args:
            message: The approval message to display

        Returns:
            True if user approves, False otherwise
        """
        if cls._auto_approve:
            logger.info(f"[AUTO-APPROVE] {message}")
            return True

        prompt = f"[APPROVAL REQUIRED] {message} (y/n): "
        if cls._input_provider:
            response = cls._input_provider(prompt)
        else:
            response = input(prompt)

        return response.strip().lower() in ("y", "yes")

    @classmethod
    def get_input(cls, prompt: str) -> str:
        """
        Gets text input from user.
        """
        if cls._auto_approve:
            return ""

        if cls._input_provider:
            return cls._input_provider(prompt)

        return input(f"[INPUT REQUIRED] {prompt}: ").strip()


def requires_approval(method):
    """
    Decorator for tool methods that require user approval before execution.
    """
    from functools import wraps

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        # Format the request description
        request_desc = f"Tool '{self.name}' called with arguments: {kwargs}"

        # Ask for approval
        if InteractionHandler.ask_approval(request_desc):
            return method(self, *args, **kwargs)
        # Return rejection message directly to the agent
        return f"ACTION DENIED: User rejected the request to use '{self.name}'. Please propose an alternative action or ask for clarification."

    return wrapper
