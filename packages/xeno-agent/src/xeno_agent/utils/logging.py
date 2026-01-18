import logging

from rich.logging import RichHandler


def setup_logging(level=logging.INFO, module_name: str | None = None):
    """
    Configure logging with RichHandler.
    """
    logging.basicConfig(level=level, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True, show_path=False)])

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str):
    """
    Get a logger with the given name.
    """
    return logging.getLogger(name)
