# Installation — VS Code chat, Copilot CLI, MCP

builder ships with three entry points. Pick whichever (or all three).

## Prerequisites

```bash
# Pick one backend:
export ANTHROPIC_API_KEY=sk-ant-...           # for BUILDER_LLM_BACKEND=anthropic
# or use the bridge:                           # BUILDER_LLM_BACKEND=vscode (free)

export AGENTS_SHADOW_ROOT="$HOME/agents/shadow"

# Install builder in editable mode.
cd <path-to-this-repo>
python -m pip install -e .
```

Windows / PowerShell:

```powershell
$env:AGENTS_SHADOW_ROOT = "$HOME\agents\shadow"
python -m pip install -e .
```

## Entry point 1 — VS Code chat slash command

Drop the SKILL.md anywhere VS Code scans:

```bash
# personal (recommended, cross-workspace):
mkdir -p ~/.agents/skills/build-artifact
cp integrations/vscode_skill/SKILL.md ~/.agents/skills/build-artifact/

# OR per-workspace (version-controlled):
mkdir -p .github/skills/build-artifact
cp integrations/vscode_skill/SKILL.md .github/skills/build-artifact/
```

Invoke:

```
/build-artifact rank my arxiv saves by likelihood I'll click through
```

The same SKILL.md works in VS Code chat, Visual Studio 2026 18.5+, GitHub
Copilot CLI, and Claude Code.

## Entry point 2 — MCP server (programmatic)

```bash
mkdir -p .vscode
cp integrations/vscode_config/mcp.json .vscode/
# Reload window.
```

`.vscode/mcp.json` already in this repo uses
`${command:python.interpreterPath}` so it picks up your venv on Windows / Mac /
Linux without edits.

Tools exposed:

| Tool | Purpose |
|---|---|
| `build_artifact` | Run interview + draft. Multi-turn — returns `pending_question` with a `session_id` if input is needed. |
| `revise_artifact` | Apply feedback to an existing shadow bundle. |
| `list_shadow_artifacts` | List `$AGENTS_SHADOW_ROOT/*`. |
| `read_shadow_artifact` | Read all files in a bundle. |
| `inspect_registry` | List installed templates / prompts / evals. |

Manual stdio test:

```bash
python -m skill.mcp_server          # canonical
# or, tarball-style (shim):
python -m integrations.mcp_server.server
```

Claude Desktop:

```json
{
  "mcpServers": {
    "builder": {
      "command": "python",
      "args": ["-m", "skill.mcp_server"],
      "cwd": "/path/to/builder",
      "env": { "BUILDER_LLM_BACKEND": "vscode" }
    }
  }
}
```

## Entry point 3 — Direct CLI

```bash
builder "rank arxiv papers"
builder --revise papers_ranked_feed --feedback "tighten JSON rules"
builder --list
builder --read <name>
builder --inspect
```

## Hooks — signal collection at the source

To capture every builder invocation across all chat sessions (so the
self-improvement loop has data to learn from), wire the post-session hook.

VS Code 1.109+ — `settings.json`:

```json
{
  "chat.hooks.enabled": true,
  "chat.hooks.postSession":
    "${workspaceFolder}/integrations/vscode_config/post-session-hook.sh"
}
```

Windows:

```json
{
  "chat.hooks.enabled": true,
  "chat.hooks.postSession":
    "powershell -NoProfile -ExecutionPolicy Bypass -File ${workspaceFolder}/integrations/vscode_config/post-session-hook.ps1"
}
```

Verify:

```bash
# 1. invoke /build-artifact in chat once
# 2. then check:
cat $AGENTS_SHADOW_ROOT/_signals/builder.jsonl
```

The `signal_collector` artifact reads this file (and walks bundle directories
for promotion outcomes). The `prompts_builder_versions` meta-improver fires
once enough records accumulate. See `IMPROVEMENT.md`.

## Verification

After install, in a VS Code chat:

```
> /build-artifact a test artifact that does nothing
```

Expected: agent invokes the skill, builder asks 1–3 questions, then reports back
with classification + shadow path. Inspect `$AGENTS_SHADOW_ROOT/<name>/` to
confirm the bundle was written.

If the agent doesn't see the skill: VS Code → Cmd/Ctrl-Shift-P → "Show
installed skills". The skill name must match the parent directory name
(`build-artifact`).

If MCP doesn't connect: Output → "MCP" channel for stdio errors. Most common
issues:

- `skill.mcp_server` not importable — `pip install -e .` from the repo root
- Wrong Python — set the workspace interpreter, then reload window
- `BUILDER_LLM_BACKEND=vscode` but the `builder-bridge` extension isn't running
