"""beeja MCP server — stdio JSON-RPC 2.0 wrapper around beeja.ops.

All business logic lives in beeja.ops. This module handles:
  1. Session management for multi-turn build_artifact calls.
  2. JSON-RPC wire protocol.

Run with:  python -m beeja.mcp_server
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any

from beeja.builder import (
    MAX_QUESTIONS,
    InterviewState,
    NeedAnswer,
    derive_name,
    draft,
    load_prompt,
    run_interview,
    write_bundle,
)
from beeja.ops import (
    inspect_registry,
    list_artifacts,
    read_artifact,
    revise_artifact,
)

# --- session store (multi-turn build only) ---------------------------------

MAX_SESSION_AGE = 1800  # 30 minutes

_SESSIONS: dict[str, dict[str, Any]] = {}


def _evict_stale() -> None:
    cutoff = time.monotonic() - MAX_SESSION_AGE
    stale = [sid for sid, s in _SESSIONS.items() if s["created"] < cutoff]
    for sid in stale:
        _SESSIONS.pop(sid, None)


def _new_session(intent: str, context: str) -> str:
    _evict_stale()
    sid = uuid.uuid4().hex[:12]
    system = load_prompt("interview")
    if context:
        system += f"\n\n## Context from prior conversation\n\n{context}\n"
    _SESSIONS[sid] = {
        "system": system,
        "state": InterviewState(),
        "turns": [{"role": "user", "content": intent}],
        "created": time.monotonic(),
    }
    return sid


# --- MCP tool wrappers -----------------------------------------------------
# Read-only tools delegate directly to ops.
# build_artifact needs session handling for the multi-turn interview.

def tool_build_artifact(
    intent: str = "",
    context: str = "",
    answers: list[str] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    answers = list(answers or [])

    if session_id is None:
        if not intent:
            return {"status": "error", "error": "intent required for new session"}
        session_id = _new_session(intent, context)

    if session_id not in _SESSIONS:
        return {"status": "error", "error": f"unknown session_id {session_id}"}

    sess = _SESSIONS[session_id]
    state: InterviewState = sess["state"]

    def _get_answer(question: str) -> str:
        if not answers:
            raise NeedAnswer(question, state)
        return answers.pop(0)

    try:
        run_interview(sess["system"], state, _get_answer)
    except NeedAnswer as na:
        return {
            "status": "pending_question",
            "session_id": session_id,
            "question": na.question,
            "questions_asked": state.questions_asked,
            "questions_remaining": MAX_QUESTIONS - state.questions_asked,
        }

    bundle, assumptions = draft(state)
    name = derive_name(state.output_asset or "unnamed")
    out_dir = write_bundle(bundle, name)
    _SESSIONS.pop(session_id, None)

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


def tool_revise_artifact(name: str, feedback: str) -> dict[str, Any]:
    if not name or not feedback:
        return {"status": "error", "error": "name and feedback both required"}
    return revise_artifact(name, feedback)


def tool_list_shadow_artifacts() -> dict[str, Any]:
    return list_artifacts()


def tool_read_shadow_artifact(name: str) -> dict[str, Any]:
    try:
        return read_artifact(name)
    except FileNotFoundError as e:
        return {"status": "error", "error": str(e)}


def tool_inspect_registry() -> dict[str, Any]:
    return inspect_registry()


def tool_code_manifest() -> dict[str, Any]:
    """Return the static manifest of public functions/classes in this package."""
    from beeja._manifest import load_manifest
    return load_manifest()


# --- MCP wire protocol (minimal stdio JSON-RPC 2.0) ------------------------

TOOLS: dict[str, dict[str, Any]] = {
    "build_artifact": {
        "fn": tool_build_artifact,
        "description": (
            "Run the beeja interview + draft. Returns 'pending_question' if more "
            "input is needed (re-call with same session_id and the answer appended "
            "to answers[])."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent":     {"type": "string", "description": "Initial natural-language intent (required for new sessions)."},
                "context":    {"type": "string", "description": "Prior conversation context to prepend to the interview system prompt."},
                "answers":    {"type": "array", "items": {"type": "string"}, "description": "Answers to interview questions, in order asked."},
                "session_id": {"type": "string", "description": "Session id from a previous pending_question response."},
            },
        },
    },
    "revise_artifact": {
        "fn": tool_revise_artifact,
        "description": "Revise an existing shadow bundle with user feedback.",
        "inputSchema": {
            "type": "object",
            "required": ["name", "feedback"],
            "properties": {
                "name":     {"type": "string"},
                "feedback": {"type": "string"},
            },
        },
    },
    "list_shadow_artifacts": {
        "fn": tool_list_shadow_artifacts,
        "description": "List all shadow artifacts under BEEJA_SHADOW_ROOT.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "read_shadow_artifact": {
        "fn": tool_read_shadow_artifact,
        "description": "Read every file in a shadow bundle as a {path: content} map.",
        "inputSchema": {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        },
    },
    "inspect_registry": {
        "fn": tool_inspect_registry,
        "description": "List installed templates, prompts, and evals shipped with beeja.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "code_manifest": {
        "fn": tool_code_manifest,
        "description": (
            "Return a JSON manifest of public functions/classes across beeja's modules "
            "(name, signature, docstring, file, line). Use to locate code for targeted "
            "edits without scanning the whole repo."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
}


def _resp(rid: Any, result: Any = None, error: dict | None = None) -> dict:
    out = {"jsonrpc": "2.0", "id": rid}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    return out


def _handle(req: dict) -> dict | None:
    method = req.get("method")
    rid    = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return _resp(rid, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "beeja", "version": "0.1.0"},
        })

    if method == "tools/list":
        return _resp(rid, {
            "tools": [
                {"name": n, "description": t["description"], "inputSchema": t["inputSchema"]}
                for n, t in TOOLS.items()
            ],
        })

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if tool is None:
            return _resp(rid, error={"code": -32601, "message": f"unknown tool {name}"})
        try:
            result = tool["fn"](**args)
        except Exception as e:  # noqa: BLE001
            return _resp(rid, error={"code": -32000, "message": f"{type(e).__name__}: {e}"})
        return _resp(rid, {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "structuredContent": result,
            "isError": False,
        })

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None  # notifications get no response

    if rid is None:
        return None
    return _resp(rid, error={"code": -32601, "message": f"unknown method {method}"})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
