# beeja

> *An artifact that grows artifacts. A graph that wires itself.*

An interview-driven artifact builder for self-improving agent systems.

Most agent frameworks start by asking you to *design* a swarm — pick a framework, wire workflows, choose tools. beeja inverts that: it gives you *one* artifact (the builder), three classification axes (shape × specification × phase), and a five-template alphabet. You answer three questions; it produces a draft. You edit; it integrates. The system grows from there.

## How it works

Every artifact is a function from declared inputs to a declared output asset. "Always-on" is a property of the change-detection layer, not the artifacts themselves — sensors watch the world and emit events; transforms re-materialize only when their inputs change. The DAG you'd otherwise design by hand emerges from the I/O contracts you declare.

Self-improvement is just another input changing. When the meta-improver promotes a new prompt version, every downstream artifact that consumed the old prompt becomes stale and re-materializes against the new one. Eval scores propagate back. Prompt revisions propagate forward. Accept/edit/discard signals propagate sideways into preference models. The "swarm" is the steady-state of those propagations.

## The five templates

| Template | Role |
|---|---|
| **sensor** | Watches an external source (filesystem, RSS, IMAP, cron, git, webhook). Subtype `signal_collector` for implicit feedback. |
| **transform** | Pure-ish function from input assets to output asset. The bread and butter. |
| **scorer** | Evaluates artifacts; emits typed verdicts. Subtype `learned_scorer` for preference models. |
| **applier** | Executes side effects under approval, with rollback. Idempotence forced ON. |
| **meta-improver** | Reads runs + scores, proposes new prompt versions. Monotonicity forced ON. |

If none fit, `freeform` opens a minimal skeleton. Three freeforms of similar shape signal a sixth canonical template should be minted.

## The three-axis success spec

Every artifact declares its notion of "good" along three orthogonal axes:

- **shape** — what kind of judgment (binary, scalar, multi_class, ordinal, vector, distributional, set, rank)
- **specification** — how the judgment is produced (explicit, property, implicit, learned, hybrid)
- **phase** — where in the lifecycle (exploration, calibration, optimization, maintenance)

Plus an opt-in eight-property floor (schema validity, bounded cost, determinism, idempotence, refusal symmetry, monotonicity, rephrase stability, calibration) that every artifact considers explicitly, and an optional context-match table for same-artifact-different-bar criteria.

The combination dissolves the analysis-paralysis problem at the source: you no longer have to know what success looks like before starting. Most artifacts begin in `exploration × property` and graduate to `optimization × explicit` only when the data supports it.

## What you get

- **No upfront design.** Add artifacts one at a time; the DAG emerges from declared I/O.
- **No silent rot.** The property floor catches schema, cost, and determinism failures from day one, even on artifacts where "good output" is still undefined.
- **No premature optimization.** Phase-aware scaffolding means an exploration artifact doesn't accumulate eval cases against criteria you haven't decided on yet.
- **No lock-in.** beeja produces specs; it doesn't replace your substrate. Run them on Anthropic SDK, Copilot CLI, MCP servers, DSPy programs, VS Code agents, or your own runtime.

## Status

v2. Interview → draft → revise loop works end-to-end. Property floor declared; the test runner is v3. No execution spine yet — that's the second artifact beeja helps you build.

## Install

\`\`\`bash
pip install beeja
export ANTHROPIC_API_KEY=sk-ant-...
beeja "I want something that ranks new arxiv papers using my save history"
\`\`\`

The first run produces a shadow bundle at `~/agents/shadow/<name>/`. Review, edit, then:

\`\`\`bash
beeja --revise arxiv_ranked_today
\`\`\`

See `CHANGELOG.md` for the v1 → v2 design jump.
