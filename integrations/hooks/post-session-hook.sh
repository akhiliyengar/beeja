#!/usr/bin/env bash
# beeja post-session-hook — append a signal record after every chat session
# that invoked the builder. Wire into VS Code via chat.hooks.enabled.
#
# Receives a JSON blob on stdin describing the session:
#   { "session_id": "...", "tool_calls": [...], "duration_ms": ..., ... }
#
# Writes one JSONL record per builder invocation to:
#   $BEEJA_SHADOW_ROOT/_signals/builder.jsonl

set -euo pipefail

SHADOW_ROOT="${BEEJA_SHADOW_ROOT:-$HOME/agents/shadow}"
SIGNALS_DIR="$SHADOW_ROOT/_signals"
SIGNALS_FILE="$SIGNALS_DIR/builder.jsonl"

mkdir -p "$SIGNALS_DIR"

# Buffer stdin so we can inspect it twice.
PAYLOAD="$(cat)"

# Only record if this session touched the build_artifact tool.
if ! printf '%s' "$PAYLOAD" | grep -q '"build_artifact"\|beeja --revise\|beeja "'; then
  exit 0
fi

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Use python (always present in beeja envs) for safe JSON projection.
python - <<PY
import json, os, sys, datetime
payload = json.loads(${PAYLOAD@Q})
record = {
    "ts": "$TS",
    "session_id": payload.get("session_id"),
    "duration_ms": payload.get("duration_ms"),
    "tool_calls": [c.get("name") for c in payload.get("tool_calls", [])],
    "drafts_written": sum(
        1 for c in payload.get("tool_calls", [])
        if c.get("name") == "build_artifact" and (c.get("result") or {}).get("status") == "complete"
    ),
    "revisions": sum(
        1 for c in payload.get("tool_calls", [])
        if c.get("name") == "revise_artifact"
    ),
    "user_marked_quality": payload.get("user_feedback", {}).get("rating"),
}
with open("$SIGNALS_FILE", "a", encoding="utf-8") as f:
    f.write(json.dumps(record) + "\n")
PY
