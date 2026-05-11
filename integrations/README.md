# builder integrations

Three ways to call the builder. Pick whichever fits your workflow — they all
end up in the same Python module.

## A. Slash command (simplest)

```bash
mkdir -p ~/.agents/skills/build-artifact
cp vscode_skill/SKILL.md ~/.agents/skills/build-artifact/
```

Then in VS Code, Visual Studio, or Copilot CLI chat:

```
/build-artifact rank my arxiv saves
```

The skill auto-discovers from `~/.agents/skills/`. No restart needed.

## B. MCP server (programmatic / agent-to-agent)

```bash
mkdir -p .vscode
cp vscode_config/mcp.json .vscode/
```

Reload the window. The `builder` server appears under MCP and exposes:

| Tool | Purpose |
|---|---|
| `build_artifact` | Run the interview + draft. Multi-turn: returns `pending_question` if needed. |
| `revise_artifact` | Apply feedback to an existing shadow bundle. |
| `list_shadow_artifacts` | List `~/agents/shadow/*`. |
| `read_shadow_artifact` | Read all files in a bundle. |
| `inspect_registry` | List installed templates / prompts / evals. |

`build_artifact` is stateful across calls when the interview needs more input:

```jsonc
// 1st call
{"intent": "rank my arxiv papers"}
// → {"status": "pending_question", "session_id": "abc123", "question": "..."}

// 2nd call (re-supply the answer)
{"session_id": "abc123", "answers": ["cs.LG and cs.AI, last 7 days"]}
// → {"status": "complete", "name": "papers_ranked_feed", ...}
```

## C. Direct CLI

```bash
builder "rank arxiv papers"
builder --revise papers_ranked_feed --feedback "tighten JSON rules"
```

Useful for cron jobs, CI, and shell pipelines.

## Signal hook (optional but recommended)

`vscode_config/post-session-hook.sh` (or `.ps1` on Windows) appends one JSONL
record per builder invocation to `$AGENTS_SHADOW_ROOT/_signals/builder.jsonl`.
This is the data feed the self-improvement loop consumes.

Enable in VS Code settings — bash (Linux / macOS / WSL):

```json
"chat.hooks.enabled": true,
"chat.hooks.postSession": "${workspaceFolder}/integrations/vscode_config/post-session-hook.sh"
```

Windows / PowerShell:

```json
"chat.hooks.enabled": true,
"chat.hooks.postSession": "powershell -NoProfile -ExecutionPolicy Bypass -File ${workspaceFolder}/integrations/vscode_config/post-session-hook.ps1"
```

Without this, signals only accumulate when you remember to log feedback —
which is the wrong default.

## Pre-flight checklist

- [ ] Python venv active, `pip install -e ..` from this dir
- [ ] `builder-bridge` VS Code extension installed and showing `$(plug) builder :21847`
- [ ] `BUILDER_LLM_BACKEND=vscode` (set automatically by the MCP config and SKILL)
- [ ] `~/agents/shadow/` writable
