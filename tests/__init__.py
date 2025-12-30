"""
Test suite for the multi-agent framework
"""

import asyncio
from typing import Any

import pytest

# Configure pytest for async tests
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_task():
    """Sample task for testing."""
    return {
        "id": "test_task_001",
        "description": "Test fibonacci calculation",
        "priority": "medium",
    }


@pytest.fixture
def framework_config():
    """Test framework configuration."""
    from agents.config import FrameworkConfig

    return FrameworkConfig(memory={"type": "in_memory"}, tools={"timeout": 5})
