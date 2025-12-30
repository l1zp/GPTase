"""
Logging configuration for the GPTase framework
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration.
    Configures the root logger with standard handlers and suppresses noisy logs.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logging.basicConfig(level=getattr(logging, level.upper()), handlers=[handler])

    # Suppress noisy logs from common HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# Export a module-level logger for convenient imports
logger = logging.getLogger(__name__)
