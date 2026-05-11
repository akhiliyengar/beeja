"""builder — interview-driven artifact builder.

Three phases: interview -> draft -> revise.

CLI:
    builder "I want something that ranks new arxiv papers"
    builder --revise arxiv_ranked_today --feedback "tighten JSON rules"

Programmatic:
    from skill import interview, draft, revise, write_bundle
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from skill.backends import LLMBackend, get_backend

# --- config -----------------------------------------------------------------

# Tarball layout: skill/ is the package; prompts/, templates/, evals/ live at
# the *repo root* (one level up). When installed via the wheel, hatchling
# force-includes those dirs alongside the package so the same parent-of-package
# resolution still works.
SKILL_DIR       = Path(__file__).resolve().parent
REPO_ROOT       = SKILL_DIR.parent
PROMPTS_DIR     = REPO_ROOT / "prompts"
TEMPLATES_DIR   = REPO_ROOT / "templates"
EVALS_DIR       = REPO_ROOT / "evals"
MAX_QUESTIONS   = 3
PROMPT_VERSION  = "v2"

_BACKEND: LLMBackend | None = None


def shadow_root() -> Path:
    """Return the shadow root, reading the env var each time."""
    return Path(os.environ.get("AGENTS_SHADOW_ROOT", str(Path.home() / "agents" / "shadow")))


# Module-level snapshot for backward compat. Prefer shadow_root() for dynamic reads.
SHADOW_ROOT = shadow_root()


def _backend() -> LLMBackend:
    """Lazily construct the configured backend on first use."""
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = get_backend()
    return _BACKEND

TemplateKind = Literal["sensor", "transform", "scorer", "applier", "meta", "freeform"]
Subtype      = Literal["signal_collector", "learned_scorer", None]
Shape        = Literal[
    "binary", "scalar", "multi_class", "ordinal",
    "vector", "distributional", "set", "rank",
]
Specification = Literal["explicit", "property", "implicit", "learned", "hybrid"]
Phase         = Literal["exploration", "calibration", "optimization", "maintenance"]


@dataclass
class SuccessSpec:
    shape:         Shape | None         = None
    specification: Specification | None = None
    phase:         Phase | None         = None
    description:   str                  = ""
    context_match: bool                 = False


@dataclass
class InterviewState:
    questions_asked:  int                  = 0
    turns:            list[dict]           = field(default_factory=list)
    template:         TemplateKind | None  = None
    subtype:          Subtype              = None
    trigger:          str | None           = None
    output_asset:     str | None           = None
    success:          SuccessSpec          = field(default_factory=SuccessSpec)
    properties_hint:  list[str]            = field(default_factory=list)
    assumptions:      list[str]            = field(default_factory=list)
    ready:            bool                 = False


# --- prompt + template loading ---------------------------------------------

def load_prompt(name: str, version: str = PROMPT_VERSION) -> str:
    """Load a prompt file. Falls back to v1 if requested version doesn't exist."""
    candidate = PROMPTS_DIR / f"{name}.{version}.md"
    if not candidate.exists() and version == "v2":
        candidate = PROMPTS_DIR / f"{name}.v1.md"
    return candidate.read_text(encoding="utf-8")


def load_template(kind: str) -> str:
    return (TEMPLATES_DIR / f"{kind}.toml").read_text(encoding="utf-8")


def load_properties_reference() -> str:
    return (PROMPTS_DIR / "properties.v1.md").read_text(encoding="utf-8")


# --- LLM call --------------------------------------------------------------

def llm_call(system: str, messages: list[dict], max_tokens: int = 4096,
             backend: LLMBackend | None = None) -> str:
    return (backend or _backend()).call(system, messages, max_tokens)


# --- interview core --------------------------------------------------------

class NeedAnswer(Exception):
    """Raised by the answer callback when no more answers are available."""
    def __init__(self, question: str, state: InterviewState):
        self.question = question
        self.state = state


def run_interview(
    system: str,
    state: InterviewState,
    get_answer: Callable[[str], str],
    backend: LLMBackend | None = None,
) -> InterviewState:
    """Core interview loop. *get_answer(question)* must return the user's answer
    or raise NeedAnswer to pause (for non-interactive callers)."""
    while not state.ready and state.questions_asked < MAX_QUESTIONS:
        reply = llm_call(system, state.turns, backend=backend)
        state.turns.append({"role": "assistant", "content": reply})

        handoff = extract_json(reply)
        if handoff and handoff.get("ready_for_draft"):
            absorb_handoff(state, handoff)
            return state

        state.questions_asked += 1
        answer = get_answer(reply)  # may raise NeedAnswer
        state.turns.append({"role": "user", "content": answer})

    # question budget exhausted; force finalization
    state.turns.append({
        "role": "user",
        "content": "Question budget reached. Emit the JSON handoff with your best inference.",
    })
    reply = llm_call(system, state.turns, backend=backend)
    absorb_handoff(state, extract_json(reply) or {})
    return state


# --- interview phase (CLI convenience) -------------------------------------

def interview(intent: str, context: str = "", interactive: bool = True,
              backend: LLMBackend | None = None) -> InterviewState:
    """Run the 3-question interview via stdin/stdout."""
    state = InterviewState()
    system = load_prompt("interview")
    if context:
        system += f"\n\n## Context from prior conversation\n\n{context}\n"
    state.turns.append({"role": "user", "content": intent})

    def _ask(question: str) -> str:
        if not interactive:
            raise RuntimeError(
                "interactive=False but builder asked a question; "
                "supply answers via the API instead."
            )
        print(f"\n[builder] {question}\n")
        return input("> ").strip()

    return run_interview(system, state, _ask, backend=backend)


def absorb_handoff(state: InterviewState, handoff: dict[str, Any]) -> None:
    state.template        = handoff.get("template", "transform")
    state.subtype         = handoff.get("subtype")
    state.trigger         = handoff.get("trigger", "")
    state.output_asset    = handoff.get("output_asset", "unnamed")
    state.assumptions     = handoff.get("assumptions", [])
    state.properties_hint = handoff.get("properties_hint", [])

    s = handoff.get("success", {}) or {}
    state.success = SuccessSpec(
        shape=s.get("shape"),
        specification=s.get("specification"),
        phase=s.get("phase", "exploration"),
        description=s.get("description", ""),
        context_match=bool(s.get("context_match", False)),
    )
    state.ready = True


# Backward compat alias
_absorb_handoff = absorb_handoff


# --- draft phase -----------------------------------------------------------

def draft(state: InterviewState, backend: LLMBackend | None = None) -> tuple[dict[str, str], list[str]]:
    """Produce the artifact bundle. Returns ({path: content}, assumptions)."""
    system = load_prompt("draft")
    system += "\n\n## Universal properties reference\n\n" + load_properties_reference()

    template_text = load_template(state.template or "transform")

    user_msg = (
        "Interview output:\n\n```json\n"
        + json.dumps({
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
            "properties_hint": state.properties_hint,
            "assumptions": state.assumptions,
        }, indent=2)
        + f"\n```\n\nTemplate skeleton ({state.template}):\n\n```toml\n{template_text}\n```\n\nProduce the bundle."
    )

    reply = llm_call(system, [{"role": "user", "content": user_msg}], max_tokens=8192,
                     backend=backend)
    return parse_bundle(reply)


# --- revise phase ----------------------------------------------------------

def revise(current: dict[str, str], user_feedback: str,
           backend: LLMBackend | None = None) -> tuple[dict[str, str], list[str]]:
    system = load_prompt("revise")
    system += "\n\n## Universal properties reference\n\n" + load_properties_reference()
    user_msg = (
        "Current bundle:\n\n"
        + bundle_to_text(current)
        + f"\n\nUser feedback:\n\n{user_feedback}\n"
    )
    reply = llm_call(system, [{"role": "user", "content": user_msg}], max_tokens=8192,
                     backend=backend)
    return parse_bundle(reply)


# --- bundle helpers --------------------------------------------------------

_BUNDLE_FILE_RE   = re.compile(r'<file path="([^"]+)">(.*?)</file>', re.DOTALL)
_BUNDLE_ASSUME_RE = re.compile(r'<assumptions>(.*?)</assumptions>', re.DOTALL)
_JSON_BLOCK_RE    = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any] | None:
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def parse_bundle(text: str) -> tuple[dict[str, str], list[str]]:
    files = {m.group(1): m.group(2).strip() for m in _BUNDLE_FILE_RE.finditer(text)}
    assumptions: list[str] = []
    am = _BUNDLE_ASSUME_RE.search(text)
    if am:
        for line in am.group(1).strip().splitlines():
            line = line.strip().lstrip("-").strip()
            if line:
                assumptions.append(line)
    return files, assumptions


def bundle_to_text(bundle: dict[str, str]) -> str:
    parts = [f'<file path="{p}">\n{c}\n</file>' for p, c in bundle.items()]
    return "<bundle>\n" + "\n".join(parts) + "\n</bundle>"


def write_bundle(bundle: dict[str, str], shadow_name: str,
                 root: Path | None = None) -> Path:
    root = root or shadow_root()
    out_dir = root / shadow_name
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_root = out_dir.resolve()
    for relpath, content in bundle.items():
        full = (out_dir / relpath).resolve()
        if not full.is_relative_to(resolved_root):
            raise ValueError(f"path traversal blocked: {relpath}")
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    return out_dir


def read_bundle(shadow_name: str, root: Path | None = None) -> dict[str, str]:
    root = root or shadow_root()
    src = root / shadow_name
    if not src.exists():
        raise FileNotFoundError(f"no shadow at {src}")
    bundle: dict[str, str] = {}
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        try:
            bundle[str(p.relative_to(src))] = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            pass  # skip binary files
    return bundle


def derive_name(asset: str) -> str:
    return re.sub(r"[^\w]+", "_", asset).strip("_").lower() or "unnamed"


# Backward compat aliases
_extract_json = extract_json
_parse_bundle = parse_bundle
_derive_name = derive_name


# --- CLI entry point -------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        prog="builder",
        description="Interview-driven artifact builder for self-improving agent systems.",
    )
    p.add_argument("intent", nargs="?", help="What do you want to build?")
    p.add_argument("--context", default="", help="Prior conversation context.")
    p.add_argument("--revise", metavar="NAME", help="Revise an existing shadow bundle.")
    p.add_argument("--feedback", default="", help="Feedback for --revise.")
    p.add_argument("--list", action="store_true", help="List shadow artifacts.")
    p.add_argument("--read", metavar="NAME", help="Print all files in a shadow bundle.")
    p.add_argument("--inspect", action="store_true", help="List installed templates, prompts, and evals.")
    p.add_argument("--manifest", action="store_true", help="Print the code-navigation manifest as JSON.")
    p.add_argument("--write-manifest", action="store_true", help="Regenerate builder/_manifest.json on disk.")
    p.add_argument("--version", action="store_true", help="Print version and exit.")
    args = p.parse_args()

    from skill import ops

    if args.version:
        from skill import __version__
        print(f"builder {__version__}")
        return 0

    if args.write_manifest:
        from skill._manifest import write_manifest
        out = write_manifest()
        print(f"wrote {out}")
        return 0

    if args.manifest:
        from skill._manifest import load_manifest
        print(json.dumps(load_manifest(), indent=2))
        return 0

    if args.inspect:
        result = ops.inspect_registry()
        print("Templates:", ", ".join(result["templates"]) or "(none)")
        print("Prompts:  ", ", ".join(result["prompts"]) or "(none)")
        print("Evals:    ", ", ".join(result["evals"]) or "(none)")
        print(f"Shadow:    {result['shadow_root']}")
        return 0

    if args.list:
        result = ops.list_artifacts()
        if not result["artifacts"]:
            print(f"No shadow artifacts found at {result['shadow_root']}.")
            return 0
        print(f"Shadow artifacts ({result['shadow_root']}):\n")
        for a in result["artifacts"]:
            print(f"  {a['name']}  ({a['files']} files)")
        return 0

    if args.read:
        try:
            result = ops.read_artifact(args.read)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        for path in sorted(result["files"]):
            print(f"--- {path} ---")
            print(result["files"][path])
            print()
        return 0

    if args.revise:
        feedback = args.feedback or input("Feedback / what to change?\n> ").strip()
        result = ops.revise_artifact(args.revise, feedback)
        print(f"\n[revised bundle at {result['shadow_dir']}]")
        _print_summary(result["files"], result["assumptions"])
        return 0

    if not args.intent:
        p.error("intent required (or use --revise NAME)")

    print(f"\n=== builder ===\nbackend: {_backend().name}\nintent: {args.intent}\n")

    def _ask(question: str) -> str:
        print(f"\n[builder] {question}\n")
        return input("> ").strip()

    result = ops.build_artifact(args.intent, args.context, get_answer=_ask)
    iv = result["interview"]

    print("\n[interview complete]")
    print(f"  template:      {iv['template']}{' / ' + iv['subtype'] if iv.get('subtype') else ''}")
    print(f"  trigger:       {iv['trigger']}")
    print(f"  output:        {iv['output_asset']}")
    s = iv["success"]
    print(f"  success.shape: {s['shape']}")
    print(f"  success.spec:  {s['specification']}")
    print(f"  success.phase: {s['phase']}")
    print(f"  description:   {s['description']}")
    if s.get("context_match"):
        print("  context_match: yes")

    print(f"\n[draft written to {result['shadow_dir']}]")
    _print_summary(result["files"], result["assumptions"])
    print("\nReview and edit the files, then run:")
    print(f"  builder --revise {result['name']}")
    return 0


def _print_summary(files: list[str] | dict[str, str], assumptions: list[str]) -> None:
    paths = sorted(files) if isinstance(files, (list, dict)) else []
    print("Files:")
    for path in paths:
        print(f"  - {path}")
    if assumptions:
        print("Assumptions surfaced:")
        for a in assumptions:
            print(f"  ~ {a}")


if __name__ == "__main__":
    sys.exit(main())
