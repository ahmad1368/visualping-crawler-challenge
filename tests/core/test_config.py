"""Unit tests for the config module: env var resolution and regex constants."""

import importlib
import os

import pytest

from core import config


def _reload_config():
    """Reload the config module so module-level constants pick up env changes."""
    return importlib.reload(config)


class TestEnvHelpers:
    """Success and failure scenarios for the env-var parsing helpers."""

    def test_get_env_str_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("ROOT_URL", "https://example.com")
        assert config._get_env_str("ROOT_URL", "default") == "https://example.com"

    def test_get_env_str_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("ROOT_URL", raising=False)
        assert config._get_env_str("ROOT_URL", "default") == "default"

    def test_get_env_str_returns_default_when_blank(self, monkeypatch):
        monkeypatch.setenv("ROOT_URL", "   ")
        assert config._get_env_str("ROOT_URL", "default") == "default"

    def test_get_env_int_returns_parsed_value_when_valid(self, monkeypatch):
        monkeypatch.setenv("APP_PORT", "9090")
        assert config._get_env_int("APP_PORT", 8000) == 9090

    def test_get_env_int_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("APP_PORT", raising=False)
        assert config._get_env_int("APP_PORT", 8000) == 8000

    def test_get_env_int_returns_default_when_invalid(self, monkeypatch):
        monkeypatch.setenv("APP_PORT", "not-a-number")
        assert config._get_env_int("APP_PORT", 8000) == 8000

    def test_get_env_float_returns_parsed_value_when_valid(self, monkeypatch):
        monkeypatch.setenv("CONNECT_TIMEOUT", "2.5")
        assert config._get_env_float("CONNECT_TIMEOUT", 5.0) == 2.5

    def test_get_env_float_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("CONNECT_TIMEOUT", raising=False)
        assert config._get_env_float("CONNECT_TIMEOUT", 5.0) == 5.0

    def test_get_env_float_returns_default_when_invalid(self, monkeypatch):
        monkeypatch.setenv("CONNECT_TIMEOUT", "not-a-float")
        assert config._get_env_float("CONNECT_TIMEOUT", 5.0) == 5.0


class TestModuleLevelSettings:
    """Success and failure scenarios for the resolved module-level constants."""

    def test_defaults_used_when_env_unset(self, monkeypatch):
        for var in ("ROOT_URL", "APP_PORT", "CONNECT_TIMEOUT", "READ_TIMEOUT", "MAX_RETRIES"):
            monkeypatch.delenv(var, raising=False)
        reloaded = _reload_config()
        assert reloaded.ROOT_URL == reloaded.DEFAULT_ROOT_URL
        assert reloaded.APP_PORT == reloaded.DEFAULT_APP_PORT
        assert reloaded.CONNECT_TIMEOUT == reloaded.DEFAULT_CONNECT_TIMEOUT
        assert reloaded.READ_TIMEOUT == reloaded.DEFAULT_READ_TIMEOUT
        assert reloaded.MAX_RETRIES == reloaded.DEFAULT_MAX_RETRIES

    def test_env_overrides_applied(self, monkeypatch):
        monkeypatch.setenv("ROOT_URL", "https://target.example")
        monkeypatch.setenv("APP_PORT", "3000")
        monkeypatch.setenv("CONNECT_TIMEOUT", "1.5")
        monkeypatch.setenv("READ_TIMEOUT", "20")
        monkeypatch.setenv("MAX_RETRIES", "5")
        reloaded = _reload_config()
        assert reloaded.ROOT_URL == "https://target.example"
        assert reloaded.APP_PORT == 3000
        assert reloaded.CONNECT_TIMEOUT == 1.5
        assert reloaded.READ_TIMEOUT == 20.0
        assert reloaded.MAX_RETRIES == 5

    def test_invalid_numeric_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("APP_PORT", "invalid")
        monkeypatch.setenv("CONNECT_TIMEOUT", "invalid")
        reloaded = _reload_config()
        assert reloaded.APP_PORT == reloaded.DEFAULT_APP_PORT
        assert reloaded.CONNECT_TIMEOUT == reloaded.DEFAULT_CONNECT_TIMEOUT

    @pytest.fixture(autouse=True)
    def _restore_config(self):
        """Reload config after each test so later tests see unmodified defaults."""
        yield
        for var in ("ROOT_URL", "APP_PORT", "CONNECT_TIMEOUT", "READ_TIMEOUT", "MAX_RETRIES"):
            os.environ.pop(var, None)
        _reload_config()


class TestSecretPattern:
    """Success and failure scenarios for the VISUALPING secret regex."""

    @pytest.mark.parametrize(
        "text",
        [
            "VISUALPING{0123456789abcdef}",
            "prefix VISUALPING{FEDCBA9876543210} suffix",
            "VISUALPING{aAbBcCdDeEfF0011}",
        ],
    )
    def test_matches_valid_secret(self, text):
        assert config.SECRET_PATTERN.search(text) is not None

    @pytest.mark.parametrize(
        "text",
        [
            "VISUALPING{}",
            "VISUALPING{0123456789abcde}",  # 15 hex chars, too short
            "VISUALPING{0123456789abcdef0}",  # 17 hex chars, too long
            "VISUALPING{ghijklmno1234567}",  # non-hex characters
            "visualping{0123456789abcdef}",  # lowercase keyword
            "just some regular text",
        ],
    )
    def test_does_not_match_invalid_secret(self, text):
        assert config.SECRET_PATTERN.search(text) is None


class TestRoutePattern:
    """Success and failure scenarios for the relative-route regex."""

    @pytest.mark.parametrize(
        "text",
        [
            "/api/v1/users",
            'fetch("/internal/status")',
            "const path = '/assets/app.js';",
        ],
    )
    def test_matches_relative_route(self, text):
        assert config.ROUTE_PATTERN.search(text) is not None

    @pytest.mark.parametrize(
        "text",
        [
            "no route here",
            "https://example.com/api",  # not a bare relative route (preceded by ':')
            "",
        ],
    )
    def test_does_not_match_when_no_relative_route(self, text):
        assert config.ROUTE_PATTERN.search(text) is None
