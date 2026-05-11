"""Tests for beeja.mcp_server — protocol and read-only tools."""

from __future__ import annotations

import beeja.builder as builder_mod
from beeja.mcp_server import (
    _SESSIONS,
    _evict_stale,
    _handle,
    tool_build_artifact,
    tool_inspect_registry,
    tool_list_shadow_artifacts,
    tool_read_shadow_artifact,
    tool_revise_artifact,
)

# --- MCP protocol ----------------------------------------------------------

class TestMCPProtocol:
    def test_initialize(self):
        resp = _handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert resp["result"]["serverInfo"]["name"] == "beeja"
        assert resp["result"]["protocolVersion"] == "2024-11-05"

    def test_tools_list(self):
        resp = _handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = [t["name"] for t in resp["result"]["tools"]]
        assert "build_artifact" in names
        assert "revise_artifact" in names
        assert "list_shadow_artifacts" in names
        assert "read_shadow_artifact" in names
        assert "inspect_registry" in names

    def test_unknown_tool(self):
        resp = _handle({
            "jsonrpc": "2.0", "id": 3,
            "method": "tools/call",
            "params": {"name": "bogus", "arguments": {}},
        })
        assert resp["error"]["code"] == -32601

    def test_unknown_method(self):
        resp = _handle({
            "jsonrpc": "2.0", "id": 4,
            "method": "totally/unknown",
            "params": {},
        })
        assert resp["error"]["code"] == -32601

    def test_notification_no_response(self):
        resp = _handle({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })
        assert resp is None


# --- read-only tools -------------------------------------------------------

class TestInspectRegistry:
    def test_lists_known_files(self):
        result = tool_inspect_registry()
        assert "transform.toml" in result["templates"]
        assert "interview.v2.md" in result["prompts"]
        assert "draft_acceptance.yaml" in result["evals"]


class TestListShadowArtifacts:
    def test_empty_root(self, tmp_path, monkeypatch):
        monkeypatch.setattr(builder_mod, "shadow_root", lambda: tmp_path / "nonexistent")
        result = tool_list_shadow_artifacts()
        assert result["artifacts"] == []

    def test_skips_underscore_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(builder_mod, "shadow_root", lambda: tmp_path)
        (tmp_path / "_signals").mkdir()
        (tmp_path / "my_artifact").mkdir()
        result = tool_list_shadow_artifacts()
        names = [a["name"] for a in result["artifacts"]]
        assert "my_artifact" in names
        assert "_signals" not in names


class TestReadShadowArtifact:
    def test_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(builder_mod, "shadow_root", lambda: tmp_path)
        result = tool_read_shadow_artifact("nope")
        assert result["status"] == "error"
        assert "no shadow" in result["error"]


# --- session eviction ------------------------------------------------------

class TestSessionEviction:
    def test_stale_sessions_removed(self, monkeypatch):
        import time
        from beeja import mcp_server as mcp
        _SESSIONS.clear()
        now = time.monotonic()
        # "old" must be older than MAX_SESSION_AGE relative to *now*. Using a
        # literal 0.0 fails on a fresh CI runner where time.monotonic() can be
        # smaller than MAX_SESSION_AGE (cutoff goes negative).
        _SESSIONS["old"] = {"created": now - mcp.MAX_SESSION_AGE - 1, "state": None, "system": "", "turns": []}
        _SESSIONS["new"] = {"created": now, "state": None, "system": "", "turns": []}
        _evict_stale()
        assert "old" not in _SESSIONS
        assert "new" in _SESSIONS
        _SESSIONS.clear()


# --- tool_build_artifact edge cases ----------------------------------------

class TestBuildArtifactEdgeCases:
    def test_no_intent_no_session(self):
        result = tool_build_artifact()
        assert result["status"] == "error"
        assert "intent required" in result["error"]

    def test_unknown_session_id(self):
        result = tool_build_artifact(session_id="nonexistent123")
        assert result["status"] == "error"
        assert "unknown session_id" in result["error"]


class TestReviseArtifactEdgeCases:
    def test_missing_fields(self):
        result = tool_revise_artifact("", "some feedback")
        assert result["status"] == "error"

    def test_missing_feedback(self):
        result = tool_revise_artifact("some_name", "")
        assert result["status"] == "error"
