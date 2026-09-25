"""Structured logging setup for the Autonomous Codebase Agent."""

import logging
import sys

from config.settings import get_settings


def setup_logger(name: str = "codebase_agent") -> logging.Logger:
    """Create and configure a logger with console output.

    Args:
        name: Logger name (default: ``codebase_agent``).

    Returns:
        Configured ``logging.Logger`` instance.
    """
    settings = get_settings()
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    return logger
