"""Make this agent's directory importable for sibling tests.

Tests under ``tests/`` need ``import normalizer`` to resolve to the
``normalizer.py`` next to this conftest. Adding the agent dir to
sys.path is the simplest route — no package shim required.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
