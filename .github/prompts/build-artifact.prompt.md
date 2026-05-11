---
mode: agent
description: Build a self-improving agent artifact via the builder CLI's interview-driven flow.
---

# /build-artifact

Wrap the `builder` CLI to scaffold a new self-improving artifact (sensor /
transform / scorer / applier / meta) under `$AGENTS_SHADOW_ROOT` (defaults to
`./shadow`). The CLI runs a 3-question interview, drafts a bundle, and tells
the user how to revise.

## When to use

- User describes a workflow they want automated
  ("rank my arxiv saves", "watch my inbox for X", "score these candidates").
- User says "build an artifact", "make me an agent that…", or
  "I want something that…".
- User invokes `/build-artifact` directly.

## How to invoke

Run in an integrated terminal at the workspace root:

```bash
BUILDER_LLM_BACKEND=vscode builder "<the user's intent verbatim>"
```

The CLI will ask **up to 3 follow-up questions** on stdin. For each question:

1. **Stop.** Show the question to the user verbatim.
2. **Wait for the user's reply.** Do not invent or infer answers — the whole
   point of the interview is to elicit user-specific intent that is not yet in
   the conversation.
3. Pipe the user's answer back into the CLI's stdin.
4. If a question is genuinely already answered verbatim in the user's
   original intent, quote the user's words back when you reply (don't make up
   a paraphrase the user never said).

If the user's reply is ambiguous, repeat the question rather than guessing.

## After the draft writes

1. Print the shadow path the CLI reported (e.g. `shadow/<name>/`).
2. List the files the CLI created (the CLI already prints these — just relay).
3. Tell the user: "Review the files, then run `/build-artifact-revise <name>`
   (or `builder --revise <name> --feedback "..."`) to iterate."

## Revise mode

If the user asks to change an existing artifact:

```bash
BUILDER_LLM_BACKEND=vscode builder --revise <name> --feedback "<their feedback>"
```

## Discovery

| Action | Command |
|---|---|
| List existing artifacts | `builder --list` |
| Read all files in an artifact | `builder --read <name>` |
| Show installed templates / prompts / evals | `builder --inspect` |

## Pre-flight

- `builder` must be on PATH. If not: `pip install -e .` from the repo root.
- The `builder-bridge` VS Code extension must be running; status bar shows
  `$(plug) builder :21847`. If not, run command `builderBridge.restart`.

## Do not

- Do **not** edit files in `shadow/` directly — always go through `builder`.
- Do **not** set `BUILDER_LLM_BACKEND=anthropic` unless the user explicitly
  asks (it costs API credits; the bridge is free).
- Do **not** answer the interview's questions on the user's behalf, even if
  the answer seems obvious from context.
- Do **not** summarize what the interview is "really doing" — let the
  interview prompt speak for itself.
