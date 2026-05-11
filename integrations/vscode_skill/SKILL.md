---
name: build-artifact
description: |
  Build a self-improving agent artifact via beeja's interview-driven flow.
  Use when the user describes a workflow they want automated (e.g. "rank my arxiv saves",
  "watch my inbox for X", "score these candidates"). Drives a 3-question interview,
  produces a bundle under ~/agents/shadow/<name>/, and tells the user how to revise.
trigger:
  - /build-artifact
  - "build an artifact"
  - "make me an agent that"
  - "I want something that"
---

# build-artifact

You are wrapping the `beeja` CLI. Do not re-implement the interview — invoke the tool.

## Invocation

Run in an integrated terminal at the workspace root:

```bash
BEEJA_LLM_BACKEND=vscode beeja "<the user's intent verbatim>"
```

The CLI may ask up to 3 follow-up questions. Forward each question to the user
and pipe their answer back as stdin. Do **not** invent answers. If the user is
ambiguous, repeat the question rather than guessing.

## After the draft writes

1. Print the shadow path the CLI reported (`~/agents/shadow/<name>/`).
2. Summarize the files created.
3. Tell the user: "Review the files, then run `/build-artifact revise <name>` (or
   `beeja --revise <name>`) with feedback."

## Revise mode

If the user asks to change an existing artifact:

```bash
BEEJA_LLM_BACKEND=vscode beeja --revise <name> --feedback "<their feedback>"
```

## Discovery

List existing artifacts:

```bash
beeja --list
```

Read all files in an artifact:

```bash
beeja --read <name>
```

Show installed templates, prompts, and evals:

```bash
beeja --inspect
```

## Pre-flight

If the `beeja` command is not on PATH, install it once:

```bash
pip install -e <path-to-this-repo>
```

The `beeja-bridge` VS Code extension must be running (status bar shows
`$(plug) beeja :21847`). If not, run command `beejaBridge.restart`.

## Do not

- Do not edit files in `~/agents/shadow/` directly — always go through `beeja`.
- Do not set `BEEJA_LLM_BACKEND=anthropic` unless the user explicitly asks
  (it costs API credits; the bridge is free).
- Do not summarize what beeja's interview is "really doing". The interview
  prompt is the contract — let it speak.
