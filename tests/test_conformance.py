"""Conformance tests — verify CLI, MCP, and ops all use the same code path.

ops.py is the single source of truth. CLI and MCP are presentation layers.
These tests verify:
  1. ops functions return correct structured data.
  2. MCP tool wrappers delegate to ops (not re-implementing).
  3. CLI main() delegates to ops (not re-implementing).
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest

import skill.builder as builder
import skill.mcp_server as mcp
import skill.ops as ops

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def shadow_with_artifacts(tmp_path, monkeypatch):
    """Create a shadow root with two artifacts and one underscore dir."""
    root = tmp_path / "shadow"
    root.mkdir()

    art1 = root / "alpha"
    art1.mkdir()
    (art1 / "main.py").write_text("print('alpha')", encoding="utf-8")
    (art1 / "config.toml").write_text("[a]\nb = 1", encoding="utf-8")

    art2 = root / "beta"
    art2.mkdir()
    (art2 / "run.sh").write_text("#!/bin/bash\necho hi", encoding="utf-8")

    signals = root / "_signals"
    signals.mkdir()
    (signals / "builder.jsonl").write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(builder, "shadow_root", lambda: root)
    return root


# ---------------------------------------------------------------------------
# ops.list_artifacts — single source
# ---------------------------------------------------------------------------

class TestListArtifacts:
    def test_returns_artifacts(self, shadow_with_artifacts):
        result = ops.list_artifacts()
        names = sorted(a["name"] for a in result["artifacts"])
        assert names == ["alpha", "beta"]

    def test_skips_underscore_dirs(self, shadow_with_artifacts):
        names = [a["name"] for a in ops.list_artifacts()["artifacts"]]
        assert "_signals" not in names

    def test_includes_file_count(self, shadow_with_artifacts):
        arts = {a["name"]: a for a in ops.list_artifacts()["artifacts"]}
        assert arts["alpha"]["files"] == 2
        assert arts["beta"]["files"] == 1

    def test_empty_root(self, tmp_path, monkeypatch):
        monkeypatch.setattr(builder, "shadow_root", lambda: tmp_path / "nonexistent")
        result = ops.list_artifacts()
        assert result["artifacts"] == []

    def test_mcp_delegates_to_ops(self, shadow_with_artifacts):
        """MCP tool_list_shadow_artifacts returns exactly ops.list_artifacts()."""
        assert mcp.tool_list_shadow_artifacts() == ops.list_artifacts()

    def test_cli_uses_ops_data(self, shadow_with_artifacts):
        """CLI --list output contains the same artifact names as ops."""
        result = ops.list_artifacts()
        buf = StringIO()
        with patch("sys.stdout", buf):
            with patch("sys.argv", ["builder", "--list"]):
                builder.main()
        output = buf.getvalue()
        for a in result["artifacts"]:
            assert a["name"] in output


# ---------------------------------------------------------------------------
# ops.read_artifact — single source
# ---------------------------------------------------------------------------

class TestReadArtifact:
    def test_reads_files(self, shadow_with_artifacts):
        result = ops.read_artifact("alpha")
        files_norm = {k.replace("\\", "/"): v for k, v in result["files"].items()}
        assert files_norm["main.py"] == "print('alpha')"
        assert "config.toml" in files_norm

    def test_nonexistent_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(builder, "shadow_root", lambda: tmp_path)
        with pytest.raises(FileNotFoundError):
            ops.read_artifact("nope")

    def test_mcp_delegates_to_ops(self, shadow_with_artifacts):
        """MCP wraps ops — success case matches."""
        mcp_result = mcp.tool_read_shadow_artifact("alpha")
        ops_result = ops.read_artifact("alpha")
        assert mcp_result == ops_result

    def test_mcp_wraps_error(self, tmp_path, monkeypatch):
        """MCP catches FileNotFoundError and returns error dict."""
        monkeypatch.setattr(builder, "shadow_root", lambda: tmp_path)
        result = mcp.tool_read_shadow_artifact("nope")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# ops.inspect_registry — single source
# ---------------------------------------------------------------------------

class TestInspectRegistry:
    def test_lists_known_files(self):
        result = ops.inspect_registry()
        assert "transform.toml" in result["templates"]
        assert "interview.v2.md" in result["prompts"]
        assert "draft_acceptance.yaml" in result["evals"]

    def test_mcp_delegates_to_ops(self):
        assert mcp.tool_inspect_registry() == ops.inspect_registry()

    def test_cli_uses_ops_data(self):
        result = ops.inspect_registry()
        buf = StringIO()
        with patch("sys.stdout", buf):
            with patch("sys.argv", ["builder", "--inspect"]):
                builder.main()
        output = buf.getvalue()
        for t in result["templates"]:
            assert t in output


# ---------------------------------------------------------------------------
# ops.revise_artifact — validation parity
# ---------------------------------------------------------------------------

class TestReviseValidation:
    def test_mcp_rejects_empty_name(self):
        result = mcp.tool_revise_artifact("", "feedback")
        assert result["status"] == "error"

    def test_mcp_rejects_empty_feedback(self):
        result = mcp.tool_revise_artifact("name", "")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Write → read roundtrip via ops
# ---------------------------------------------------------------------------

class TestWriteReadRoundtrip:
    def test_write_then_read(self, tmp_path, monkeypatch):
        monkeypatch.setattr(builder, "shadow_root", lambda: tmp_path)
        bundle = {"skill/main.py": "import os", "meta.toml": "[artifact]\nname='test'"}
        builder.write_bundle(bundle, "roundtrip_test", root=tmp_path)

        result = ops.read_artifact("roundtrip_test")
        files_norm = {k.replace("\\", "/"): v for k, v in result["files"].items()}
        assert files_norm["skill/main.py"] == "import os"
        assert files_norm["meta.toml"] == "[artifact]\nname='test'"

    def test_mcp_read_matches_ops(self, tmp_path, monkeypatch):
        monkeypatch.setattr(builder, "shadow_root", lambda: tmp_path)
        bundle = {"a.py": "pass"}
        builder.write_bundle(bundle, "parity_test", root=tmp_path)

        assert mcp.tool_read_shadow_artifact("parity_test") == ops.read_artifact("parity_test")


# ---------------------------------------------------------------------------
# Context param wired through
# ---------------------------------------------------------------------------

class TestContextWiring:
    def test_mcp_session_includes_context(self):
        mcp._SESSIONS.clear()
        sid = mcp._new_session("test intent", "some prior context")
        assert "prior context" in mcp._SESSIONS[sid]["system"]
        mcp._SESSIONS.clear()

    def test_mcp_session_no_context(self):
        mcp._SESSIONS.clear()
        sid = mcp._new_session("test intent", "")
        assert "prior context" not in mcp._SESSIONS[sid]["system"]
        mcp._SESSIONS.clear()
