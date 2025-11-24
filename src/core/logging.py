"""
Logging configuration for the GPTase framework
"""

import logging
from rich.logging import RichHandler
from rich.console import Console

def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration.
    Configures the root logger with RichHandler and suppresses noisy logs.
    """
    console = Console()

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)]
    )

    # Suppress noisy logs from common HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

# Export a module-level logger for convenient imports
logger = logging.getLogger(__name__)
