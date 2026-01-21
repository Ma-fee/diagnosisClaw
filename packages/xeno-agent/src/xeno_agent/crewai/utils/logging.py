import logging

from rich.logging import RichHandler


def setup_logging(level: int = logging.INFO, module_name: str | None = None) -> None:
    """
    Configure logging with RichHandler.

    Args:
        level: Logging level (default: INFO)
        module_name: Module to restrict logging to (default: all modules)
    """
    logging.basicConfig(level=level, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True, show_path=False)])

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with given name.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
