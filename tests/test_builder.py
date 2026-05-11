"""Tests for skill.builder — pure-logic functions and filesystem operations."""

from __future__ import annotations

import pytest

from skill.builder import (
    InterviewState,
    absorb_handoff,
    derive_name,
    extract_json,
    load_prompt,
    parse_bundle,
    read_bundle,
    write_bundle,
)

# --- extract_json ----------------------------------------------------------

class TestExtractJson:
    def test_valid_block(self):
        text = 'Some preamble\n```json\n{"ready_for_draft": true, "template": "sensor"}\n```\ntrailing'
        result = extract_json(text)
        assert result == {"ready_for_draft": True, "template": "sensor"}

    def test_no_block(self):
        assert extract_json("no json here at all") is None

    def test_malformed_json(self):
        assert extract_json('```json\n{broken json}\n```') is None

    def test_nested_braces(self):
        text = '```json\n{"a": {"b": 1}}\n```'
        assert extract_json(text) == {"a": {"b": 1}}

    def test_whitespace_variants(self):
        text = '```json   \n{"x": 1}\n  ```'
        assert extract_json(text) == {"x": 1}


# --- parse_bundle ----------------------------------------------------------

class TestParseBundle:
    def test_single_file(self):
        text = '<file path="main.py">print("hi")</file>'
        files, assumptions = parse_bundle(text)
        assert files == {"main.py": 'print("hi")'}
        assert assumptions == []

    def test_multiple_files(self):
        text = (
            '<file path="a.py">code_a</file>\n'
            '<file path="b/c.toml">[section]\nkey=1</file>'
        )
        files, _ = parse_bundle(text)
        assert set(files.keys()) == {"a.py", "b/c.toml"}

    def test_assumptions(self):
        text = (
            '<file path="x.py">pass</file>\n'
            '<assumptions>\n- assumes Python 3.11\n- assumes network access\n</assumptions>'
        )
        _, assumptions = parse_bundle(text)
        assert assumptions == ["assumes Python 3.11", "assumes network access"]

    def test_empty_input(self):
        files, assumptions = parse_bundle("nothing here")
        assert files == {}
        assert assumptions == []

    def test_strips_content_whitespace(self):
        text = '<file path="a.py">\n  code  \n</file>'
        files, _ = parse_bundle(text)
        assert files["a.py"] == "code"


# --- derive_name -----------------------------------------------------------

class TestDeriveName:
    @pytest.mark.parametrize("input_val,expected", [
        ("arxiv_ranked_today", "arxiv_ranked_today"),
        ("My Cool Agent!", "my_cool_agent"),
        ("hello world 123", "hello_world_123"),
        ("", "unnamed"),
        ("---", "unnamed"),
        ("___", "unnamed"),  # strip("_") empties it
    ])
    def test_cases(self, input_val, expected):
        assert derive_name(input_val) == expected


# --- absorb_handoff --------------------------------------------------------

class TestAbsorbHandoff:
    def test_full_handoff(self):
        state = InterviewState()
        absorb_handoff(state, {
            "template": "scorer",
            "subtype": "learned_scorer",
            "trigger": "daily cron",
            "output_asset": "my_scorer",
            "assumptions": ["needs API key"],
            "properties_hint": ["bounded_cost"],
            "success": {
                "shape": "vector",
                "specification": "learned",
                "phase": "calibration",
                "description": "scores well",
                "context_match": True,
            },
        })
        assert state.template == "scorer"
        assert state.subtype == "learned_scorer"
        assert state.trigger == "daily cron"
        assert state.output_asset == "my_scorer"
        assert state.success.shape == "vector"
        assert state.success.specification == "learned"
        assert state.success.phase == "calibration"
        assert state.success.context_match is True
        assert state.assumptions == ["needs API key"]
        assert state.ready is True

    def test_minimal_handoff(self):
        state = InterviewState()
        absorb_handoff(state, {})
        assert state.template == "transform"  # default
        assert state.output_asset == "unnamed"
        assert state.ready is True

    def test_none_success_block(self):
        state = InterviewState()
        absorb_handoff(state, {"success": None})
        assert state.success.phase == "exploration"  # default
        assert state.ready is True


# --- write_bundle / read_bundle roundtrip ----------------------------------

class TestBundleIO:
    def test_roundtrip(self, tmp_path):
        bundle = {
            "skill/main.py": "print('hello')",
            "config.toml": "[a]\nb = 1",
        }
        out = write_bundle(bundle, "test_art", root=tmp_path)
        assert (out / "skill" / "main.py").exists()
        loaded = read_bundle("test_art", root=tmp_path)
        # Normalize path separators (Windows uses backslash)
        loaded_norm = {k.replace("\\", "/"): v for k, v in loaded.items()}
        assert loaded_norm["skill/main.py"] == "print('hello')"
        assert loaded_norm["config.toml"] == "[a]\nb = 1"

    def test_path_traversal_blocked(self, tmp_path):
        with pytest.raises(ValueError, match="path traversal"):
            write_bundle({"../../etc/passwd": "pwned"}, "evil", root=tmp_path)

    def test_read_nonexistent(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="no shadow"):
            read_bundle("does_not_exist", root=tmp_path)

    def test_binary_files_skipped(self, tmp_path):
        art_dir = tmp_path / "binary_test"
        art_dir.mkdir()
        (art_dir / "text.txt").write_text("hello", encoding="utf-8")
        (art_dir / "binary.bin").write_bytes(b"\x80\x81\x82\xff\xfe")
        bundle = read_bundle("binary_test", root=tmp_path)
        assert "text.txt" in bundle
        assert "binary.bin" not in bundle

    def test_utf8_content(self, tmp_path):
        bundle = {"notes.md": "Special chars: ≤ ≥ → ← ∀ ∃"}
        write_bundle(bundle, "utf8_test", root=tmp_path)
        loaded = read_bundle("utf8_test", root=tmp_path)
        assert loaded["notes.md"] == "Special chars: ≤ ≥ → ← ∀ ∃"


# --- load_prompt -----------------------------------------------------------

class TestLoadPrompt:
    def test_v2_fallback_to_v1(self, tmp_path, monkeypatch):
        import skill.builder as b
        monkeypatch.setattr(b, "PROMPTS_DIR", tmp_path)
        (tmp_path / "test.v1.md").write_text("v1 content", encoding="utf-8")
        assert load_prompt("test", "v2") == "v1 content"

    def test_v2_preferred(self, tmp_path, monkeypatch):
        import skill.builder as b
        monkeypatch.setattr(b, "PROMPTS_DIR", tmp_path)
        (tmp_path / "test.v1.md").write_text("v1", encoding="utf-8")
        (tmp_path / "test.v2.md").write_text("v2", encoding="utf-8")
        assert load_prompt("test", "v2") == "v2"

    def test_exact_version(self, tmp_path, monkeypatch):
        import skill.builder as b
        monkeypatch.setattr(b, "PROMPTS_DIR", tmp_path)
        (tmp_path / "test.v1.md").write_text("v1", encoding="utf-8")
        assert load_prompt("test", "v1") == "v1"
