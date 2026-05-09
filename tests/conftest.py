"""Shared pytest fixtures for the rebuilt test suite.

Fixtures here should remain framework-wide. Module-specific fixtures belong
in `tests/<package>/conftest.py` once each layer is rebuilt.
"""
import base64

import pytest

from gptase.models.types import ModelConfig
from gptase.utils.config import FrameworkConfig


@pytest.fixture
def framework_config():
    """Default FrameworkConfig instance for tests that need wiring."""
    return FrameworkConfig()


@pytest.fixture
def mock_model_config():
    """Mock-mode ModelConfig: no real LLM calls."""
    return ModelConfig(
        use_mock=True,
        model_name="test-model",
        api_key="test-api-key",
        temperature=0.1,
        max_tokens=1000,
    )


@pytest.fixture
def sample_image_png(tmp_path):
    """1x1 PNG on disk; returns absolute path string."""
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    image_path = tmp_path / "test_image.png"
    image_path.write_bytes(png_data)
    return str(image_path)


@pytest.fixture
def sample_image_jpeg(tmp_path):
    """Minimal valid JPEG on disk; returns absolute path string."""
    jpeg_hex = (
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c"
        "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27"
        "393d38323c2e333432ffc00011080001000103012200021101031101ffc4001f0000010501010101"
        "0100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d"
        "010203000411050521310612410713227108142832a109233344153b243550619125d13362728290a"
        "07161a283f044582b1c1d1e2f20655578392a2b3c3d3e4f45667778994a5b6c7d8e9f0a1b2c3d4e5f"
        "ffc4001f0100030101010101010101010000000000000102030405060708090a0bffc400b511000201"
        "020404030407050404000102770001020311040521310612410713225108143291a109233344153b2"
        "43550619125d13362728290a07161a283f044582b1c1d1e2f20655578392a2b3c3d3e4f4566777899"
        "4a5b6c7d8e9f0a1b2c3d4e5f0a14ffd9")
    jpeg_data = bytes.fromhex(jpeg_hex)
    image_path = tmp_path / "test_image.jpg"
    image_path.write_bytes(jpeg_data)
    return str(image_path)
