"""
Logging configuration for the GPTase framework
"""

import logging
from rich.logging import RichHandler
from rich.console import Console

def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    console = Console()
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)]
    )
    
    # Suppress noisy logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)