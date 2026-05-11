# AGENTS.md

Repo-tracked guidance for agents (Copilot, Claude, etc.) working in this codebase.
Anything an agent would otherwise stash in private/user memory belongs here so it
stays traceable, reviewable, and version-controlled.

## Operating principles

- **Traceability first.** Don't put repo-relevant preferences, decisions, or
  conventions into user-scoped or session-scoped memory. They belong in this file
  (or a sibling file linked from here) so they survive across machines, agents,
  and contributors.
- **Ask before bypassing safety rails.** Never use `git commit --no-verify`,
  `git push --force`, `git reset --hard` on shared history, or similar without
  explicit confirmation in the current turn.
- **Prefer in-place fixes over workarounds.** If a hook or check fails, fix the
  cause; don't disable the check.

## Builder artifact preferences

These constrain what the `builder` CLI / `draft.v*.md` prompts should produce.
They are reflected in `prompts/draft.v2.md` ("When to omit a file" table); this
section is the human-authoritative copy.

- **Bias toward minimal artifacts.** Fewer files, fewer lines, fewer abstractions.
  Bulkiness must be earned by the spec, not assumed.
- **Required floor:** `<name>.toml` + `skill/main.py`. Single-pair artifacts are
  a valid, preferred outcome when the work fits.
- **Optional files** — emit only when the answer is yes:
  - `prompts/main.v1.md` — the artifact actually issues an LLM call.
  - `evals/cases.yaml` — phase ≠ `exploration`, or at least one runnable
    property-floor case exists. Placeholder-only files are worse than no file.
  - `notes.md` — there are concrete graduation criteria or open questions.
    Empty checklists are noise.
  - sibling `signal_collector` artifact — `specification ∈ {learned, implicit}`
    and no existing collector watches this asset.
- **Surface omissions.** When a file is skipped, mention it in `<assumptions>`
  so the user can request it during `--revise`.

## Where things live

- Python package: `skill/` (dist name `builder`, CLI binary `builder`).
- Prompts: `prompts/` (flat, versioned `<name>.vN.md`).
- Templates: `templates/` (artifact archetypes).
- Evals: `evals/` (suite YAMLs).
- Shadow workspace (artifact builds): `shadow/` (gitignored runtime output).
- VS Code extension (bridge): `vscode-extension/`.

## Environment variables

- `BUILDER_LLM_BACKEND` — `anthropic` (default) or `vscode`.
- `BUILDER_MODEL` — overrides backend's default model.
- `AGENTS_SHADOW_ROOT` — where built artifacts are written.
- `BUILDER_VSCODE_BRIDGE_URL` — VS Code bridge endpoint (else read from
  `~/.builder/bridge.port`).

## Hooks

Three places fire the `signal_collector` so the meta-improver loop has fresh
data without manual prompting:

1. **Pre-commit** (`.githooks/pre-commit`) — gatekeeper: manifest regen, ruff,
   dead-code, pytest. Blocks the commit on failure.
2. **Post-commit** (`.githooks/post-commit`) — best-effort: invokes the
   collector against `$AGENTS_SHADOW_ROOT` (defaults to `./shadow`). Silent if
   the collector hasn't been built. Skip with `SKIP_BUILDER_POST_COMMIT=1`.
3. **VS Code chat session end** (`.vscode/settings.json` →
   `chat.hooks.postSession` → `integrations/vscode_config/post-session-hook.ps1`)
   — appends a JSONL invocation record to `$AGENTS_SHADOW_ROOT/_signals/builder.jsonl`,
   which the collector lifts into deduped signals on its next run.
4. **VS Code shutdown** (`vscode-extension/src/extension.ts` → `deactivate()`)
   — backstop: spawns the collector detached so it runs even when the chat-hook
   path didn't fire (e.g. full editor close).

Enable the git hooks once per checkout: `git config core.hooksPath .githooks`.

## Commit / push conventions

- Pre-commit hook runs: manifest regen → ruff → dead-code scan → pytest.
  All must be green; never bypass.
- Commit messages: short imperative summary, optional `-m` body bullets for
  what/why. Include affected file or subsystem in the summary when useful
  (e.g. `draft.v2: bias toward minimal artifacts`).
- The `git push` PowerShell exit code 1 with `main -> main` in stderr is
  cosmetic (git progress output). The push succeeded if you see the ref update.
