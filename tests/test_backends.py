"""Tests for beeja.backends — factory and discovery logic."""

from __future__ import annotations

import pytest

from beeja.backends import (
    VSCodeBridgeBackend,
    _discover_bridge_url,
    get_backend,
)


class TestGetBackend:
    def test_vscode_backend(self, monkeypatch):
        monkeypatch.setenv("BEEJA_LLM_BACKEND", "vscode")
        b = get_backend()
        assert isinstance(b, VSCodeBridgeBackend)
        assert b.name == "vscode"

    def test_copilot_alias(self, monkeypatch):
        monkeypatch.setenv("BEEJA_LLM_BACKEND", "copilot")
        b = get_backend()
        assert isinstance(b, VSCodeBridgeBackend)

    def test_invalid_backend(self, monkeypatch):
        monkeypatch.setenv("BEEJA_LLM_BACKEND", "openai")
        with pytest.raises(ValueError, match="Unknown"):
            get_backend()

    def test_custom_model(self, monkeypatch):
        monkeypatch.setenv("BEEJA_LLM_BACKEND", "vscode")
        monkeypatch.setenv("BEEJA_MODEL", "gpt-4o")
        b = get_backend()
        assert b._model == "gpt-4o"


class TestDiscoverBridgeUrl:
    def test_env_var_wins(self, monkeypatch):
        monkeypatch.setenv("BEEJA_VSCODE_BRIDGE_URL", "http://localhost:9999/")
        assert _discover_bridge_url() == "http://localhost:9999"

    def test_port_file(self, tmp_path, monkeypatch):
        import beeja.backends as bk
        port_file = tmp_path / "bridge.port"
        port_file.write_text("12345")
        monkeypatch.setattr(bk, "BRIDGE_PORT_FILE", port_file)
        monkeypatch.delenv("BEEJA_VSCODE_BRIDGE_URL", raising=False)
        assert _discover_bridge_url() == "http://127.0.0.1:12345"

    def test_default(self, monkeypatch, tmp_path):
        import beeja.backends as bk
        monkeypatch.delenv("BEEJA_VSCODE_BRIDGE_URL", raising=False)
        # Point BRIDGE_PORT_FILE at a guaranteed-missing path so we hit the default.
        monkeypatch.setattr(bk, "BRIDGE_PORT_FILE", tmp_path / "nonexistent")
        assert _discover_bridge_url() == "http://127.0.0.1:21847"

    def test_non_numeric_port_file(self, tmp_path, monkeypatch):
        import beeja.backends as bk
        port_file = tmp_path / "bridge.port"
        port_file.write_text("not_a_number")
        monkeypatch.setattr(bk, "BRIDGE_PORT_FILE", port_file)
        monkeypatch.delenv("BEEJA_VSCODE_BRIDGE_URL", raising=False)
        # Falls through to default
        assert _discover_bridge_url() == "http://127.0.0.1:21847"
