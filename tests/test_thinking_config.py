#!/usr/bin/env python3
"""Test thinking mode configuration."""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.models.providers import OpenAIProvider
from src.models.types import ModelConfig


def test_thinking_config():
    """Test that enable_thinking adds extra_body to params."""

    print("\n" + "=" * 60)
    print("🧪 Testing Thinking Mode Configuration")
    print("=" * 60 + "\n")

    # Test 1: Default config (thinking disabled)
    print("📋 Test 1: Default Config (enable_thinking=False)")
    config1 = ModelConfig(model_name="Qwen3-235B-A22B",
                          api_key="test-key",
                          base_url="https://test.com")
    provider1 = OpenAIProvider(config1)
    params1 = provider1._build_request_params([{"role": "user", "content": "test"}])

    print(f"  enable_thinking: {config1.enable_thinking}")
    print(f"  extra_body in params: {'extra_body' in params1}")
    assert "extra_body" not in params1, "extra_body should not be in params when enable_thinking=False"
    print("  ✅ PASS: No extra_body when thinking disabled\n")

    # Test 2: Thinking enabled
    print("📋 Test 2: Thinking Enabled (enable_thinking=True)")
    config2 = ModelConfig(model_name="Qwen3-235B-A22B",
                          api_key="test-key",
                          base_url="https://test.com",
                          enable_thinking=True)
    provider2 = OpenAIProvider(config2)
    params2 = provider2._build_request_params([{"role": "user", "content": "test"}])

    print(f"  enable_thinking: {config2.enable_thinking}")
    print(f"  extra_body in params: {'extra_body' in params2}")
    assert "extra_body" in params2, "extra_body should be in params when enable_thinking=True"
    assert params2["extra_body"][
        "enable_thinking"] == True, "extra_body should have enable_thinking=True"
    print(f"  extra_body content: {params2['extra_body']}")
    print("  ✅ PASS: extra_body correctly added when thinking enabled\n")

    # Test 3: Thinking with provider_config
    print("📋 Test 3: Thinking with provider_config")
    config3 = ModelConfig(model_name="Qwen3-235B-A22B",
                          api_key="test-key",
                          base_url="https://test.com",
                          enable_thinking=True,
                          provider_config={
                              "stream": True,
                              "custom_param": "value"
                          })
    provider3 = OpenAIProvider(config3)
    params3 = provider3._build_request_params([{"role": "user", "content": "test"}])

    print(f"  enable_thinking: {config3.enable_thinking}")
    print(f"  extra_body in params: {'extra_body' in params3}")
    print(f"  stream from provider_config: {params3.get('stream')}")
    print(f"  custom_param from provider_config: {params3.get('custom_param')}")
    assert params3["extra_body"][
        "enable_thinking"] == True, "extra_body should be preserved"
    assert params3["stream"] == True, "provider_config should be merged"
    assert params3[
        "custom_param"] == "value", "custom provider_config should be preserved"
    print("  ✅ PASS: extra_body and provider_config coexist correctly\n")

    print("=" * 60)
    print("✨ All Tests Passed!")
    print("=" * 60)
    print("\n📝 Summary:")
    print("  ✅ enable_thinking=False → no extra_body")
    print("  ✅ enable_thinking=True → extra_body={'enable_thinking': True}")
    print("  ✅ provider_config merged correctly")
    print("\n💡 Usage Example:")
    print("  config = ModelConfig(enable_thinking=True)")
    print("  params = provider._build_request_params(messages)")
    print("  # params will include: extra_body={'enable_thinking': True}")
    print()


if __name__ == "__main__":
    test_thinking_config()
