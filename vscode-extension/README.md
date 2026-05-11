# builder-bridge

A small VS Code extension that exposes `vscode.lm` (GitHub Copilot models) as a localhost HTTP endpoint, so the builder Python CLI can use your Copilot subscription instead of a separate Anthropic API key.

## What it does

- Binds `127.0.0.1:21847` (configurable) when VS Code starts.
- POST to `/v1/chat` with `{model, messages, max_tokens}`; forwards to `vscode.lm.selectChatModels({ vendor: 'copilot', family: model })` and returns `{text}`.
- Writes its port to `~/.builder/bridge.port` so the builder CLI can discover it.
- Shows a status bar item: `🔌 builder :21847`.
- Localhost-only. No network exposure. No auth required (binding restricts access).

## Install (local development)

```bash
cd vscode-extension
npm install
npm run compile

# Package as a .vsix you can install in any VS Code instance
npx vsce package --no-yarn -o builder-bridge.vsix
code --install-extension builder-bridge.vsix
```

Then **restart VS Code** (or run `Developer: Reload Window`). You should see `🔌 builder :21847` in the status bar.

The first time the builder CLI sends a request, VS Code will pop a consent dialog asking whether the bridge extension may use Copilot models. Approve it once.

## Configure

VS Code settings:

```jsonc
{
  // Port to bind on. Change if 21847 is taken.
  "builderBridge.port": 21847,

  // Default model family if a request doesn't specify one.
  // Values: any vscode.lm family — typically "gpt-4o", "claude-sonnet-4.6",
  // "claude-opus-4", etc., depending on what your Copilot plan exposes.
  "builderBridge.defaultFamily": "claude-sonnet-4.6"
}
```

## Verify

```bash
# health check
curl http://127.0.0.1:21847/healthz
# → {"ok":true,"version":"0.1.0"}

# list models you have access to via Copilot
curl http://127.0.0.1:21847/v1/models

# quick chat call
curl -X POST http://127.0.0.1:21847/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4.6",
    "messages": [{"role": "user", "content": "Say hi in 5 words."}],
    "max_tokens": 50
  }'
```

## Wire builder to use it

In your builder project:

```bash
# Windows PowerShell
$env:BUILDER_LLM_BACKEND = "vscode"
$env:BUILDER_MODEL = "claude-sonnet-4.6"
builder "I want something that ranks new arxiv papers"

# bash / zsh
export BUILDER_LLM_BACKEND=vscode
export BUILDER_MODEL=claude-sonnet-4.6
builder "I want something that ranks new arxiv papers"
```

The Python CLI will:
1. See `BUILDER_LLM_BACKEND=vscode`.
2. Read the port from `~/.builder/bridge.port` (or fall back to the default).
3. POST chat requests to the bridge.
4. VS Code routes them to Copilot. Quota is billed against your Copilot subscription.

## Limitations

- **VS Code must be running.** If you close VS Code, the bridge dies. For headless / always-on usage, switch to the `anthropic` backend (or wait for the spine, where this becomes one of several substrates).
- **Quota is your Copilot quota.** Per the announced June 1 2026 pricing changes, premium models (Claude Opus/Sonnet) carry multipliers — heavy builder sessions can chew through your monthly allowance fast.
- **No streaming exposed to the CLI.** The bridge accumulates the full response then returns it. Fine for builder; would need work for true streaming.
- **Single-tenant.** One VS Code window owns the port at a time. Multiple windows: only the first to start gets it; the others log an EADDRINUSE.
- **No tool calls / function calling.** `vscode.lm`'s tool-calling surface is more involved; the bridge currently only does text in/text out. Sufficient for builder's interview/draft/revise prompts.

## Why not just ship builder as an extension?

It would be the cleanest long-term form, but it requires rewriting the orchestration layer in TypeScript and losing the CLI surface. The bridge is the pragmatic 80-line compromise: builder stays Python, and you reuse your Copilot sub.

## Troubleshooting

- `EADDRINUSE` on startup → change `builderBridge.port`.
- `no copilot model matched family=X` → curl `/v1/models` to see what's actually available. Family names depend on your Copilot plan.
- Consent dialog never appeared → run any Copilot Chat message manually first, then try again. VS Code only exposes models after at least one user-initiated Copilot interaction.
- Python side errors with "Could not reach builder-bridge" → check `~/.builder/bridge.port` exists and matches what VS Code is listening on; check VS Code status bar shows `🔌 builder`.
