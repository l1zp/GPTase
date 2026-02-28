"""Sandbox provider singleton for managing sandbox instances.

This module provides a centralized way to configure and access sandbox
instances throughout the application.
"""

import logging
from typing import Optional, Type

from .base import Sandbox

logger = logging.getLogger(__name__)


class SandboxProvider:
    """Singleton provider for sandbox instances.

    Provides a global point of access to sandbox instances, allowing
    configuration to be set once and used throughout the application.

    Usage:
        # Configure at application startup
        SandboxProvider.configure(LocalSandbox, timeout=60)

        # Get sandbox anywhere in the application
        sandbox = SandboxProvider.get_sandbox()
        result = await sandbox.execute("print('hello')")
    """

    _instance: Optional["SandboxProvider"] = None
    _sandbox_class: Optional[Type[Sandbox]] = None
    _sandbox_config: dict = None
    _sandbox_instance: Optional[Sandbox] = None

    def __init__(self):
        """Private constructor to enforce singleton pattern."""
        raise RuntimeError("Use SandboxProvider.configure() and get_sandbox() instead")

    @classmethod
    def configure(cls, sandbox_class: Type[Sandbox], **config) -> None:
        """Configure the sandbox provider.

        Args:
            sandbox_class: The sandbox implementation class to use.
            **config: Configuration options to pass to the sandbox constructor.
        """
        cls._sandbox_class = sandbox_class
        cls._sandbox_config = config
        cls._sandbox_instance = None  # Reset instance when reconfiguring
        logger.info(f"Configured sandbox provider with {sandbox_class.__name__}")

    @classmethod
    def get_sandbox(cls) -> Sandbox:
        """Get the configured sandbox instance.

        Creates the sandbox instance on first access (lazy initialization).

        Returns:
            The configured sandbox instance.

        Raises:
            RuntimeError: If sandbox has not been configured.
        """
        if cls._sandbox_class is None:
            raise RuntimeError(
                "Sandbox not configured. Call SandboxProvider.configure() first.")

        if cls._sandbox_instance is None:
            logger.debug(f"Creating sandbox instance: {cls._sandbox_class.__name__}")
            cls._sandbox_instance = cls._sandbox_class(**cls._sandbox_config)

        return cls._sandbox_instance

    @classmethod
    def reset(cls) -> None:
        """Reset the provider state.

        Useful for testing or reconfiguration. Clears the singleton instance
        and configuration.
        """
        if cls._sandbox_instance is not None:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule cleanup if loop is running
                    asyncio.create_task(cls._sandbox_instance.cleanup())
                else:
                    loop.run_until_complete(cls._sandbox_instance.cleanup())
            except Exception as e:
                logger.warning(f"Error during sandbox cleanup: {e}")

        cls._sandbox_instance = None
        cls._sandbox_class = None
        cls._sandbox_config = None
        logger.debug("Sandbox provider reset")

    @classmethod
    def is_configured(cls) -> bool:
        """Check if sandbox has been configured.

        Returns:
            True if a sandbox class has been configured.
        """
        return cls._sandbox_class is not None

    @classmethod
    async def cleanup(cls) -> None:
        """Clean up the sandbox instance.

        Should be called during application shutdown.
        """
        if cls._sandbox_instance is not None:
            try:
                await cls._sandbox_instance.cleanup()
                logger.info("Sandbox instance cleaned up")
            except Exception as e:
                logger.warning(f"Error during sandbox cleanup: {e}")
            finally:
                cls._sandbox_instance = None


def get_sandbox() -> Sandbox:
    """Convenience function to get the configured sandbox.

    Returns:
        The configured sandbox instance.

    Raises:
        RuntimeError: If sandbox has not been configured.
    """
    return SandboxProvider.get_sandbox()
