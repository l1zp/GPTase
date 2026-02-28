import os
import sys

import pytest

from src.core.config import FrameworkConfig

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


@pytest.fixture
def framework_config():
    """Fixture to provide a standard FrameworkConfig instance."""
    return FrameworkConfig()
