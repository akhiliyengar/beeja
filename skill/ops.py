"""skill.ops — canonical operations.

Every capability (list, read, inspect, revise, build) lives here as a single
function returning a structured dict. CLI and MCP are thin presentation layers
that call these functions and format the output.

Rules:
  - Functions return plain dicts. No printing, no I/O except filesystem.
  - LLM-calling functions accept an optional ``backend`` parameter.
  - Errors are raised as exceptions (callers decide how to surface them).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import skill.builder as _builder
from skill.backends import LLMBackend

# Re-export for type hints within this module
InterviewState = _builder.InterviewState
NeedAnswer = _builder.NeedAnswer


# ---------------------------------------------------------------------------
# list_artifacts
# ---------------------------------------------------------------------------

def list_artifacts() -> dict[str, Any]:
    """Return all shadow artifacts (excluding underscore-prefixed dirs)."""
    root = _builder.shadow_root()
    if not root.exists():
        return {"shadow_root": str(root), "artifacts": []}
    items = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and not p.name.startswith("_"):
            items.append({
                "name": p.name,
                "path": str(p),
                "files": sum(1 for f in p.rglob("*") if f.is_file()),
            })
    return {"shadow_root": str(root), "artifacts": items}


# ---------------------------------------------------------------------------
# read_artifact
# ---------------------------------------------------------------------------

def read_artifact(name: str) -> dict[str, Any]:
    """Read every file in a shadow bundle. Raises FileNotFoundError."""
    bundle = _builder.read_bundle(name)
    return {
        "name": name,
        "shadow_dir": str(_builder.shadow_root() / name),
        "files": bundle,
    }


# ---------------------------------------------------------------------------
# inspect_registry
# ---------------------------------------------------------------------------

def inspect_registry() -> dict[str, Any]:
    """List installed templates, prompts, and evals."""
    def _ls(d: Path, glob: str) -> list[str]:
        return sorted(p.name for p in d.glob(glob)) if d.exists() else []
    return {
        "templates":   _ls(_builder.TEMPLATES_DIR, "*.toml"),
        "prompts":     _ls(_builder.PROMPTS_DIR, "*.md"),
        "evals":       _ls(_builder.EVALS_DIR, "*.yaml"),
        "shadow_root": str(_builder.shadow_root()),
    }


# ---------------------------------------------------------------------------
# revise_artifact
# ---------------------------------------------------------------------------

def revise_artifact(
    name: str,
    feedback: str,
    backend: LLMBackend | None = None,
) -> dict[str, Any]:
    """Revise an existing shadow bundle. Returns the new bundle metadata."""
    current = _builder.read_bundle(name)
    bundle, assumptions = _builder.revise(current, feedback, backend=backend)
    out_dir = _builder.write_bundle(bundle, name)
    return {
        "status": "complete",
        "name": name,
        "shadow_dir": str(out_dir),
        "files": sorted(bundle.keys()),
        "assumptions": assumptions,
    }


# ---------------------------------------------------------------------------
# build_artifact
# ---------------------------------------------------------------------------

def build_artifact(
    intent: str,
    context: str = "",
    get_answer: Callable[[str], str] | None = None,
    backend: LLMBackend | None = None,
) -> dict[str, Any]:
    """Run the full interview → draft pipeline.

    *get_answer(question)* returns the user's answer. If None, the interview
    must complete without questions (unlikely — caller should provide one).
    """
    state = _builder.InterviewState()
    system = _builder.load_prompt("interview")
    if context:
        system += f"\n\n## Context from prior conversation\n\n{context}\n"
    state.turns.append({"role": "user", "content": intent})

    def _no_answer(_q: str) -> str:
        raise RuntimeError("Interview needs an answer but no get_answer callback provided.")

    _builder.run_interview(system, state, get_answer or _no_answer, backend=backend)

    bundle, assumptions = _builder.draft(state, backend=backend)
    name = _builder.derive_name(state.output_asset or "unnamed")
    out_dir = _builder.write_bundle(bundle, name)

    return {
        "status": "complete",
        "name": name,
        "shadow_dir": str(out_dir),
        "files": sorted(bundle.keys()),
        "assumptions": assumptions,
        "interview": {
            "template": state.template,
            "subtype": state.subtype,
            "trigger": state.trigger,
            "output_asset": state.output_asset,
            "success": {
                "shape": state.success.shape,
                "specification": state.success.specification,
                "phase": state.success.phase,
                "description": state.success.description,
                "context_match": state.success.context_match,
            },
        },
    }
