"""Tests for the static code-navigation manifest and prompt caching."""

from __future__ import annotations

import json

from beeja._manifest import MANIFEST_PATH, generate_manifest, load_manifest


def test_manifest_file_exists():
    assert MANIFEST_PATH.exists(), (
        "beeja/_manifest.json missing. Regenerate with: python -m beeja._manifest --write"
    )


def test_manifest_in_sync_with_source():
    """If this fails, run: python -m beeja._manifest --write"""
    on_disk = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    fresh = generate_manifest()
    assert on_disk == fresh, (
        "Manifest is stale. Regenerate with: python -m beeja._manifest --write"
    )


def test_manifest_has_expected_modules():
    data = generate_manifest()
    names = [m["module"] for m in data["modules"]]
    assert names == ["beeja.ops", "beeja.builder", "beeja.backends", "beeja.mcp_server"]


def test_manifest_ops_lists_canonical_functions():
    data = generate_manifest()
    ops_entry = next(m for m in data["modules"] if m["module"] == "beeja.ops")
    fn_names = {f["name"] for f in ops_entry["functions"]}
    assert {"list_artifacts", "read_artifact", "inspect_registry",
            "revise_artifact", "build_artifact"} <= fn_names


def test_manifest_entries_have_signature_and_doc():
    data = generate_manifest()
    for mod in data["modules"]:
        for fn in mod["functions"]:
            assert fn["signature"], f"missing signature: {mod['module']}.{fn['name']}"
            # doc may be empty for trivial helpers, but signature must exist
            assert "doc" in fn
            assert fn["line"] > 0


def test_load_manifest_returns_dict():
    data = load_manifest()
    assert isinstance(data, dict)
    assert "modules" in data
    assert "version" in data


def test_anthropic_backend_uses_prompt_caching(monkeypatch):
    """AnthropicBackend.call must wrap the system prompt with cache_control."""
    import beeja.backends as backends

    captured: dict = {}

    class _FakeContent:
        type = "text"
        text = "ok"

    class _FakeResp:
        content = [_FakeContent()]

    class _FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResp()

    class _FakeClient:
        def __init__(self):
            self.messages = _FakeMessages()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    # Bypass real client construction.
    backend = backends.AnthropicBackend.__new__(backends.AnthropicBackend)
    backend._client = _FakeClient()
    backend._model = "claude-sonnet-4-6"

    out = backend.call("system prompt", [{"role": "user", "content": "hi"}], 100)
    assert out == "ok"

    system_param = captured["system"]
    assert isinstance(system_param, list), "system must be a list to enable cache_control"
    assert system_param[0]["type"] == "text"
    assert system_param[0]["text"] == "system prompt"
    assert system_param[0]["cache_control"] == {"type": "ephemeral"}


def test_anthropic_backend_handles_empty_system():
    """An empty system prompt must not be wrapped (avoid sending bogus cache block)."""
    import beeja.backends as backends

    captured: dict = {}

    class _FakeContent:
        type = "text"
        text = "ok"

    class _FakeResp:
        content = [_FakeContent()]

    class _FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResp()

    class _FakeClient:
        def __init__(self):
            self.messages = _FakeMessages()

    backend = backends.AnthropicBackend.__new__(backends.AnthropicBackend)
    backend._client = _FakeClient()
    backend._model = "claude-sonnet-4-6"

    backend.call("", [{"role": "user", "content": "hi"}], 100)
    assert captured["system"] == ""


def test_mcp_exposes_code_manifest_tool():
    from beeja.mcp_server import TOOLS
    assert "code_manifest" in TOOLS
    result = TOOLS["code_manifest"]["fn"]()
    assert "modules" in result
