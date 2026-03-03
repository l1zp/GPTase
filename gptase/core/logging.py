"""
Logging configuration for the GPTase framework
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration.

    Configures the root logger with standard handlers and suppresses noisy logs.
    This can be called multiple times to adjust the logging level.

    Args:
        level: Logging level string (e.g., "INFO", "DEBUG"). Defaults to "INFO".
    """
    numeric_level = getattr(logging, level.upper())

    # Clear existing handlers from root logger to allow reconfiguration
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(numeric_level)

    # Create and add handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
    handler.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # Update all existing loggers to respect the new level
    for logger_name in logging.root.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        # Only set level for loggers in our package (src.*)
        if logger_name.startswith("src.") and logger.level == logging.NOTSET:
            logger.setLevel(numeric_level)

    # Suppress noisy logs from common HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# Export a module-level logger for convenient imports
logger = logging.getLogger(__name__)
