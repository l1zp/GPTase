"""Shared logging configuration for GPTase."""

import logging


def setup_logging(debug: bool = False) -> None:
    """Configure logging format and level.

    Args:
        debug: If True, set log level to DEBUG; otherwise INFO.
    """
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
