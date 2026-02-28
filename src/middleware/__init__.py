"""Middleware module for request/response processing.

This module provides middleware components that process data before and
after agent execution. Middleware can be chained to create processing
pipelines for tasks like file management, title generation, and logging.

Quick Start:
    from src.middleware import MiddlewareChain, ThreadDataMiddleware

    # Create chain
    chain = MiddlewareChain()
    chain.add(ThreadDataMiddleware(base_dir="data/threads"))

    # Process data
    context = MiddlewareContext(thread_id="thread_001")
    result = await chain.process(context, {"message": "hello"})

Classes:
    MiddlewareContext: Context object passed through middleware.
    BaseMiddleware: Abstract base class for middleware.
    MiddlewareChain: Chain for executing multiple middleware.
    ThreadDataMiddleware: Manages thread-level data directories.
    TitleMiddleware: Auto-generates thread titles.
    UploadsMiddleware: Tracks and manages file uploads.
"""

from .base import BaseMiddleware
from .base import MiddlewareChain
from .base import MiddlewareContext
from .thread_data import ThreadDataMiddleware
from .title import TitleMiddleware
from .uploads import FileInfo
from .uploads import UploadsMiddleware

__all__ = [
    # Base classes
    "MiddlewareContext",
    "BaseMiddleware",
    "MiddlewareChain",
    # Implementations
    "ThreadDataMiddleware",
    "TitleMiddleware",
    "UploadsMiddleware",
    "FileInfo",
]
