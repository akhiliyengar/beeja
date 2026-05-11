"""LLM backend abstraction.

Selects a backend at import time based on BUILDER_LLM_BACKEND:
  - "anthropic" (default): direct Anthropic API. Requires ANTHROPIC_API_KEY.
  - "vscode":              bridges to GitHub Copilot via a local VS Code extension.
                            Requires the builder-bridge VS Code extension running.
                            Reads bridge URL from BUILDER_VSCODE_BRIDGE_URL (default
                            http://127.0.0.1:21847) or from ~/.builder/bridge.port.

The backend interface is just `call(system, messages, max_tokens) -> str`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

DEFAULT_BRIDGE_URL = "http://127.0.0.1:21847"
BRIDGE_PORT_FILE   = Path.home() / ".builder" / "bridge.port"


class LLMBackend(ABC):
    """Minimal backend contract. All backends turn (system, messages) into text."""

    name: str = "abstract"

    @abstractmethod
    def call(self, system: str, messages: list[dict], max_tokens: int) -> str: ...


# --- Anthropic --------------------------------------------------------------

class AnthropicBackend(LLMBackend):
    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "anthropic SDK not installed. Run: pip install anthropic"
            ) from e
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Either set it, or switch backends with "
                "BUILDER_LLM_BACKEND=vscode."
            )
        self._client = anthropic.Anthropic()
        self._model = model

    def call(self, system: str, messages: list[dict], max_tokens: int) -> str:
        # Prompt caching: the system prompt is ~3K tokens and is identical across
        # every interview turn. Wrapping it with cache_control lets Anthropic reuse
        # a cached prefix across calls within ~5 minutes, cutting input tokens by
        # roughly the system-prompt size on every turn after the first.
        # Requires anthropic SDK >= 0.18 (we pin >=0.40).
        system_param: Any = (
            [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            if system
            else system
        )
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=0,
            system=system_param,
            messages=messages,
        )
        return "".join(b.text for b in resp.content if b.type == "text")


# --- VS Code bridge ---------------------------------------------------------

class VSCodeBridgeBackend(LLMBackend):
    """Talks to a local VS Code extension that exposes vscode.lm over HTTP.

    The extension binds to 127.0.0.1 on a configurable port. Bridge URL is found
    via (in order):
      1. BUILDER_VSCODE_BRIDGE_URL env var.
      2. ~/.builder/bridge.port file (just the port number, written by the extension).
      3. The default http://127.0.0.1:21847.
    """

    name = "vscode"

    def __init__(self, model: str = "claude-sonnet-4.6") -> None:
        self._url   = _discover_bridge_url()
        self._model = model

    def call(self, system: str, messages: list[dict], max_tokens: int) -> str:
        # vscode.lm has no separate "system" param — fold it in as a leading user msg.
        all_msgs = [{"role": "user", "content": system}] + messages if system else messages
        body = json.dumps({
            "model":      self._model,
            "messages":   all_msgs,
            "max_tokens": max_tokens,
            "temperature": 0,
        }).encode()
        req = urllib.request.Request(
            f"{self._url}/v1/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Could not reach builder-bridge at {self._url}. Is VS Code running with "
                f"the builder-bridge extension installed? Underlying error: {e}"
            ) from e
        if "error" in data:
            raise RuntimeError(f"bridge error: {data['error']}")
        return data["text"]


def _discover_bridge_url() -> str:
    if env := os.environ.get("BUILDER_VSCODE_BRIDGE_URL"):
        return env.rstrip("/")
    if BRIDGE_PORT_FILE.exists():
        port = BRIDGE_PORT_FILE.read_text().strip()
        if port.isdigit():
            return f"http://127.0.0.1:{port}"
    return DEFAULT_BRIDGE_URL


# --- factory ---------------------------------------------------------------

def get_backend() -> LLMBackend:
    """Construct the configured backend. Cached per-process via module-level state."""
    name = os.environ.get("BUILDER_LLM_BACKEND", "anthropic").lower()
    model = os.environ.get("BUILDER_MODEL")  # backend-specific default if unset

    if name == "anthropic":
        return AnthropicBackend(model=model or "claude-sonnet-4-6")
    if name in ("vscode", "vscode_bridge", "copilot"):
        return VSCodeBridgeBackend(model=model or "claude-sonnet-4.6")
    raise ValueError(
        f"Unknown BUILDER_LLM_BACKEND={name!r}. "
        f"Valid values: anthropic, vscode."
    )
