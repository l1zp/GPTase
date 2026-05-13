"""Unit tests for gptase.utils.config.

Covers FrameworkConfig (field aliasing, MCP cleanup, placeholder secret
detection, env API key fallback, ModelConfig conversion, per-agent
overrides), the top-level load_template_config (raises
ConfigurationError on file/JSON errors) and load_mcp_sidecar_config
(silently returns {} on errors), and the GPTASE_LLM_CONFIG environment
override.

Tests use explicit kwargs to FrameworkConfig() so that the constructor
short-circuits the real-template-loading branch — that branch is
exercised separately via load_template_config.
"""
import json
import logging
from pathlib import Path
import re

import pytest

from gptase.utils import config as config_module
from gptase.utils.config import FrameworkConfig
from gptase.utils.config import load_mcp_sidecar_config
from gptase.utils.config import load_template_config
from gptase.utils.exceptions import ConfigurationError

_SECRET_VALUE_RE = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|"
                              r"QC-[0-9a-f]{32}-[0-9a-f]{32}|"
                              r"AIza[0-9A-Za-z_-]{20,}|"
                              r"github_pat_[0-9A-Za-z_]{20,}|"
                              r"ghp_[0-9A-Za-z_]{20,}|"
                              r"AKIA[0-9A-Z]{16})")


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Strip env vars that affect FrameworkConfig behaviour.

    Without this, a developer's real OPENAI_API_KEY would leak into
    every test and tests of the env-fallback path would be unreliable.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GPTASE_LLM_CONFIG", raising=False)


class TestNormalizeFieldNames:
    """JSON config keys are aliased onto FrameworkConfig llm_* fields."""

    def test_json_aliases_apply_to_llm_fields(self):
        cfg = FrameworkConfig(
            model_name="gpt-4-turbo",
            api_key="sk-test",
            base_url="https://api.example.com",
            temperature=0.7,
            max_tokens=2048,
            timeout=42,
            stream=False,
            enable_thinking=False,
        )

        assert cfg.llm_model == "gpt-4-turbo"
        assert cfg.llm_api_key == "sk-test"
        assert cfg.llm_base_url == "https://api.example.com"
        assert cfg.llm_temperature == 0.7
        assert cfg.llm_max_tokens == 2048
        assert cfg.llm_timeout == 42
        assert cfg.llm_stream is False
        assert cfg.llm_enable_thinking is False

    def test_dict_provider_routes_to_llm_provider(self):
        cfg = FrameworkConfig(model_name="x", provider={"sort": "input_length"})

        assert cfg.llm_provider == {"sort": "input_length"}

    def test_scalar_provider_dropped(self):
        cfg = FrameworkConfig(model_name="x", provider="legacy-string")

        assert cfg.llm_provider is None

    def test_legacy_thinking_and_provider_config_silently_ignored(self):
        # `thinking` and `provider_config` are deprecated keys; they must
        # not raise and must not be set on any field.
        cfg = FrameworkConfig(
            model_name="x",
            thinking={"enabled": True},
            provider_config={"region": "us"},
        )

        assert cfg.llm_model == "x"
        # Pydantic would have raised AttributeError if these had been
        # forwarded as unknown fields.
        assert not hasattr(cfg, "thinking")
        assert not hasattr(cfg, "provider_config")


class TestMcpServerCleanup:
    """The mcp_servers validator drops comment keys + placeholder-secret entries."""

    def test_strips_underscore_prefixed_comment_keys(self):
        cfg = FrameworkConfig(
            model_name="x",
            mcp_servers={
                "_comment": {
                    "note": "example"
                },
                "_example_sse": {
                    "transport": "sse"
                },
                "real-server": {
                    "transport": "stdio",
                    "command": "npx"
                },
            },
        )

        assert "_comment" not in cfg.mcp_servers
        assert "_example_sse" not in cfg.mcp_servers
        assert "real-server" in cfg.mcp_servers

    def test_drops_servers_with_placeholder_env_secrets(self):
        cfg = FrameworkConfig(
            model_name="x",
            mcp_servers={
                "good": {
                    "transport": "stdio",
                    "command": "npx",
                    "env": {
                        "API_KEY": "sk-abc123"
                    },
                },
                "bad": {
                    "transport": "stdio",
                    "command": "npx",
                    "env": {
                        "API_KEY": "YOUR_API_KEY_HERE"
                    },
                },
            },
        )

        assert "good" in cfg.mcp_servers
        assert "bad" not in cfg.mcp_servers

    def test_keeps_servers_with_real_env_values(self):
        cfg = FrameworkConfig(
            model_name="x",
            mcp_servers={
                "tavily": {
                    "transport": "stdio",
                    "command": "npx",
                    "env": {
                        "TAVILY_API_KEY": "tvly-real-key"
                    },
                }
            },
        )

        assert "tavily" in cfg.mcp_servers


class TestPlaceholderSecretDetection:
    """_contains_placeholder_secret static method covers all marker types."""

    def test_placeholder_markers_detected(self):
        # All five markers must trigger detection regardless of case.
        for value in [
                "YOUR_KEY",
                "your_key_here",  # case-insensitive
                "REPLACE_ME",
                "CHANGE_ME_NOW",
                "PLACEHOLDER",
                "<your-api-key>",  # angle bracket placeholder
        ]:
            assert FrameworkConfig._contains_placeholder_secret(
                {"K": value}), f"Failed to flag placeholder: {value!r}"

    def test_none_or_empty_env_value_treated_as_placeholder(self):
        assert FrameworkConfig._contains_placeholder_secret({"K": None})
        assert FrameworkConfig._contains_placeholder_secret({"K": ""})
        assert FrameworkConfig._contains_placeholder_secret({"K": "   "})

    def test_real_secret_not_flagged(self):
        assert not FrameworkConfig._contains_placeholder_secret(
            {"K": "sk-abc123def456"})


class TestApiKeyEnvFallback:
    """OPENAI_API_KEY env var fills llm_api_key when not explicit."""

    def test_explicit_api_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "from-env")
        cfg = FrameworkConfig(model_name="x", api_key="from-explicit")

        assert cfg.llm_api_key == "from-explicit"

    def test_env_api_key_used_when_explicit_missing(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "from-env")
        cfg = FrameworkConfig(model_name="x")

        assert cfg.llm_api_key == "from-env"


class TestToModelConfig:
    """FrameworkConfig.to_model_config() produces a usable ModelConfig."""

    def test_default_timeout_becomes_600(self):
        # llm_timeout is None by default; ModelConfig must receive 600.
        cfg = FrameworkConfig(model_name="x", api_key="sk-test")

        mc = cfg.to_model_config()

        assert cfg.llm_timeout is None
        assert mc.timeout == 600

    def test_provider_routing_carried_through(self):
        cfg = FrameworkConfig(
            model_name="x",
            api_key="sk-test",
            provider={"sort": "input_length"},
        )

        mc = cfg.to_model_config()

        assert mc.provider == {"sort": "input_length"}


class TestGetConfigForAgent:
    """Per-agent overrides resolve via dash/underscore name normalization."""

    def test_returns_none_when_no_agent_match(self):
        cfg = FrameworkConfig(model_name="x", api_key="sk-default")

        assert cfg.get_config_for_agent("unknown-agent") is None

    def test_name_normalization_handles_dash_underscore(self):
        # Stored under dash form; lookup with underscore should still hit.
        cfg = FrameworkConfig(
            model_name="x",
            api_key="sk-default",
            agent_models={"vision-agent": {
                "model_name": "claude-opus-4-7"
            }},
        )

        # underscore-style lookup
        mc1 = cfg.get_config_for_agent("vision_agent")
        # exact match
        mc2 = cfg.get_config_for_agent("vision-agent")

        assert mc1 is not None and mc1.model_name == "claude-opus-4-7"
        assert mc2 is not None and mc2.model_name == "claude-opus-4-7"

    def test_whitelisted_overrides_apply(self):
        cfg = FrameworkConfig(
            model_name="x",
            api_key="sk-default",
            provider={"sort": "latency"},
            agent_models={
                "deep-research": {
                    "temperature": 0.0,
                    "provider": {
                        "sort": "input_length"
                    },
                }
            },
        )

        mc = cfg.get_config_for_agent("deep-research")

        assert mc is not None
        # Overrides applied
        assert mc.temperature == 0.0
        assert mc.provider == {"sort": "input_length"}
        # Defaults preserved for non-overridden fields
        assert mc.model_name == "x"
        assert mc.api_key == "sk-default"

    def test_non_whitelisted_keys_silently_ignored(self):
        # `notes` is not in the override whitelist; must not crash and
        # must not appear on the resulting ModelConfig.
        cfg = FrameworkConfig(
            model_name="x",
            api_key="sk-default",
            agent_models={"agent-1": {
                "notes": "internal docs",
                "temperature": 0.5
            }},
        )

        mc = cfg.get_config_for_agent("agent-1")

        assert mc is not None
        assert mc.temperature == 0.5
        assert not hasattr(mc, "notes")


class TestLoadTemplateConfig:
    """Top-level load_template_config raises on file/JSON errors."""

    def test_missing_file_raises_configuration_error(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GPTASE_LLM_CONFIG", str(tmp_path / "nonexistent.json"))

        with pytest.raises(ConfigurationError, match="missing"):
            load_template_config()

    def test_invalid_json_raises_configuration_error(self, monkeypatch, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        monkeypatch.setenv("GPTASE_LLM_CONFIG", str(bad))

        with pytest.raises(ConfigurationError, match="Invalid template config format"):
            load_template_config()

    def test_valid_template_returned_as_dict(self, monkeypatch, tmp_path):
        good = tmp_path / "good.json"
        good.write_text(json.dumps({"model_name": "loaded", "temperature": 0.3}))
        monkeypatch.setenv("GPTASE_LLM_CONFIG", str(good))

        result = load_template_config()

        assert result == {"model_name": "loaded", "temperature": 0.3}


class TestTemplateSecretHygiene:
    """Tracked template/example configs must not contain live secrets."""

    def test_template_config_does_not_set_api_key(self):
        root = Path(__file__).resolve().parents[2]
        template = root / "config" / "llm_config.template.json"
        data = json.loads(template.read_text(encoding="utf-8"))

        assert "api_key" not in data

    def test_tracked_config_templates_have_no_secret_shaped_values(self):
        root = Path(__file__).resolve().parents[2]
        config_files = [
            *root.glob("config/*.template.json"),
            *root.glob("config/*.example.json"),
        ]

        findings = []
        for path in config_files:
            data = json.loads(path.read_text(encoding="utf-8"))
            findings.extend(f"{path.relative_to(root)}: {value}"
                            for value in _iter_json_strings(data)
                            if _SECRET_VALUE_RE.search(value))

        assert findings == []


def _iter_json_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_json_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_json_strings(child)


class TestLoadMcpSidecarConfig:
    """load_mcp_sidecar_config swallows errors and normalizes type->transport."""

    def test_returns_empty_dict_when_file_missing(self, monkeypatch, tmp_path):
        # Point _get_project_root_dir() at an empty tmp tree so .mcp.json
        # is genuinely missing.
        fake_module_dir = tmp_path / "gptase" / "utils"
        fake_module_dir.mkdir(parents=True)
        monkeypatch.setattr(config_module, "__file__",
                            str(fake_module_dir / "config.py"))

        assert load_mcp_sidecar_config() == {}

    def test_returns_empty_dict_on_invalid_json(self, monkeypatch, tmp_path):
        sidecar = tmp_path / ".mcp.json"
        sidecar.write_text("{not valid json")

        fake_module_dir = tmp_path / "gptase" / "utils"
        fake_module_dir.mkdir(parents=True)
        monkeypatch.setattr(config_module, "__file__",
                            str(fake_module_dir / "config.py"))

        # Must not raise — silent fallback to {}.
        assert load_mcp_sidecar_config() == {}

    def test_normalizes_type_to_transport(self, monkeypatch, tmp_path):
        sidecar = tmp_path / ".mcp.json"
        sidecar.write_text(
            json.dumps({
                "mcpServers": {
                    "tavily": {
                        "type": "stdio",
                        "command": "npx",
                        "args": ["-y", "tavily-mcp"],
                    }
                }
            }))

        fake_module_dir = tmp_path / "gptase" / "utils"
        fake_module_dir.mkdir(parents=True)
        monkeypatch.setattr(config_module, "__file__",
                            str(fake_module_dir / "config.py"))

        loaded = load_mcp_sidecar_config()

        assert loaded["tavily"]["transport"] == "stdio"
        assert "type" not in loaded["tavily"]


class TestCustomConfigPath:
    """GPTASE_LLM_CONFIG env var redirects template loading."""

    def test_gptase_llm_config_env_overrides_template_path(self, monkeypatch, tmp_path):
        custom = tmp_path / "my_config.json"
        custom.write_text(json.dumps({"model_name": "from-env-override"}))
        monkeypatch.setenv("GPTASE_LLM_CONFIG", str(custom))

        result = load_template_config()

        assert result["model_name"] == "from-env-override"


class TestFrameworkConfigTemplateFallback:
    """Bare FrameworkConfig() (no kwargs) triggers _load_template_config.

    Per the 2026-05-09 design discussion (option B): template-load
    failures must NOT raise (back-compat), but they MUST emit a WARNING
    so the user can see what happened rather than silently running on
    defaults forever.
    """

    def test_template_failure_swallowed_with_warning(self, monkeypatch, tmp_path,
                                                     caplog):
        # Point at a path that doesn't exist so load_template_config raises
        # ConfigurationError, which the instance method then swallows.
        monkeypatch.setenv("GPTASE_LLM_CONFIG", str(tmp_path / "nope.json"))

        with caplog.at_level(logging.WARNING):
            cfg = FrameworkConfig()  # bare ctor -> template-load branch

        # Framework defaults applied — no exception propagated:
        assert cfg.llm_model == "gpt-4"

        # The failure is visible at WARNING (not just DEBUG):
        matching = [
            record for record in caplog.records if record.levelno >= logging.WARNING
            and "Could not load template config" in record.message
        ]
        assert matching, (
            "Expected a WARNING log surfacing the template-load failure; "
            "silent fallback would mean a malformed config goes unnoticed.")
