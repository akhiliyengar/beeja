---
mode: agent
description: Revise an existing builder artifact under shadow/ with the user's feedback.
---

# /build-artifact-revise

Wrap `builder --revise` to iterate on an existing artifact bundle without
rebuilding from scratch.

## When to use

- User asks to change something about an artifact already in `shadow/`
  ("tighten the JSON rules in arxiv_ranked_today", "make papers_ranked_feed
  use a smaller model", etc.).
- User invokes `/build-artifact-revise <name>` directly.

## How to invoke

Run in an integrated terminal at the workspace root:

```bash
BUILDER_LLM_BACKEND=vscode builder --revise <name> --feedback "<user's feedback verbatim>"
```

If the user didn't specify which artifact, run `builder --list` first and
ask them to pick.

## After the revision writes

1. Print the path the CLI reported.
2. List the files that changed (CLI prints these — just relay).
3. Tell the user the bundle is updated in place; previous version is still
   in git history.

## Do not

- Do **not** invent feedback; pass exactly what the user said.
- Do **not** edit `shadow/` files directly.
