---
name: build-artifact
description: |
  Build a self-improving agent artifact via builder's interview-driven flow.
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

You are wrapping the `builder` CLI. Do not re-implement the interview — invoke the tool.

## Invocation

Run in an integrated terminal at the workspace root:

```bash
BUILDER_LLM_BACKEND=vscode builder "<the user's intent verbatim>"
```

The CLI may ask up to 3 follow-up questions. Forward each question to the user
and pipe their answer back as stdin. Do **not** invent answers. If the user is
ambiguous, repeat the question rather than guessing.

## After the draft writes

1. Print the shadow path the CLI reported (`~/agents/shadow/<name>/`).
2. Summarize the files created.
3. Tell the user: "Review the files, then run `/build-artifact revise <name>` (or
   `builder --revise <name>`) with feedback."

## Revise mode

If the user asks to change an existing artifact:

```bash
BUILDER_LLM_BACKEND=vscode builder --revise <name> --feedback "<their feedback>"
```

## Discovery

List existing artifacts:

```bash
builder --list
```

Read all files in an artifact:

```bash
builder --read <name>
```

Show installed templates, prompts, and evals:

```bash
builder --inspect
```

## Pre-flight

If the `builder` command is not on PATH, install it once:

```bash
pip install -e <path-to-this-repo>
```

The `builder-bridge` VS Code extension must be running (status bar shows
`$(plug) builder :21847`). If not, run command `builderBridge.restart`.

## Do not

- Do not edit files in `~/agents/shadow/` directly — always go through `builder`.
- Do not set `BUILDER_LLM_BACKEND=anthropic` unless the user explicitly asks
  (it costs API credits; the bridge is free).
- Do not summarize what builder's interview is "really doing". The interview
  prompt is the contract — let it speak.
