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

- **shape** — what kind of judgment (`binary`, `scalar`, `multi_class`, `ordinal`, `vector`, `distributional`, `set`, `rank`)
- **specification** — how the judgment is produced (`explicit`, `property`, `implicit`, `learned`, `hybrid`)
- **phase** — where in the lifecycle (`exploration`, `calibration`, `optimization`, `maintenance`)

Plus an opt-in eight-property floor (schema validity, bounded cost, determinism, idempotence, refusal symmetry, monotonicity, rephrase stability, calibration) that every artifact considers explicitly, and an optional context-match table for same-artifact-different-bar criteria.

The combination dissolves the analysis-paralysis problem at the source: you no longer have to know what success looks like before starting. Most artifacts begin in `exploration × property` and graduate to `optimization × explicit` only when the data supports it.

## What you get

- **No upfront design.** Add artifacts one at a time; the DAG emerges from declared I/O.
- **No silent rot.** The property floor catches schema, cost, and determinism failures from day one, even on artifacts where "good output" is still undefined.
- **No premature optimization.** Phase-aware scaffolding means an exploration artifact doesn't accumulate eval cases against criteria you haven't decided on yet.
- **No lock-in.** beeja produces specs; it doesn't replace your substrate. Run them on Anthropic SDK, Copilot CLI, MCP servers, DSPy programs, VS Code agents, or your own runtime.

## Install

```bash
pip install beeja                       # once published
# or for now:
git clone https://github.com/akhiliyengar/beeja
cd beeja
pip install -e .
```

Then pick an LLM backend:

### Backend A — Anthropic API (default)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# optional:
export BEEJA_MODEL=claude-sonnet-4-6
export BEEJA_SHADOW_ROOT=~/agents/shadow
```

### Backend B — VS Code Copilot via the bridge extension

Uses your existing GitHub Copilot subscription instead of a separate API key.

```bash
# build & install the sibling VS Code extension once
cd vscode-extension
npm install && npm run compile
npx vsce package --no-yarn -o beeja-bridge.vsix
code --install-extension beeja-bridge.vsix
cd ..

# then in your shell
export BEEJA_LLM_BACKEND=vscode
export BEEJA_MODEL=claude-sonnet-4         # or whatever your Copilot plan exposes
```

VS Code must be running when you invoke beeja. See `vscode-extension/README.md` for details, model discovery, and troubleshooting.

## Use

```bash
beeja "I want something that ranks new arxiv papers using my save history"
```

The builder will:

1. Run the three-question interview (`beeja/prompts/interview.v2.md`).
2. Silently classify your intent on three axes: shape, specification, phase.
3. Hand off to the draft phase (`beeja/prompts/draft.v2.md`) which:
   - Fills the chosen template.
   - Adds the three-axis `[success]` block.
   - Adds the eight-property `[success.properties]` block.
   - Generates phase-appropriate eval cases.
   - Optionally scaffolds a `[success.context_match]` block.
   - Optionally emits a sibling `signal_collector` sensor.
4. Write the bundle to `~/agents/shadow/<name>/`.

Edit the files, then revise:

```bash
beeja --revise arxiv_ranked_today --feedback "tighten the JSON-output rules"
```

### Programmatic

```python
from beeja import interview, draft, revise, write_bundle

state = interview("rank arxiv papers", context="...")
print(state.success.shape, state.success.specification, state.success.phase)

bundle, assumptions = draft(state)
out_dir = write_bundle(bundle, "arxiv_ranked_today")
```

## The `[success]` block

```toml
[success]
shape         = "scalar"
specification = "explicit"
phase         = "optimization"
description   = "Top-5 ranked papers get user-clicked within 24h."
range     = [0.0, 1.0]
target    = 0.7
direction = "maximize"

[success.properties]
schema_validity    = true
bounded_cost       = true
determinism        = true
idempotence        = false
refusal_symmetry   = false
monotonicity       = false
rephrase_stability = false
calibration        = false

# optional, for context-conditional bars:
# [success.context_match]
# "urgency=high"   = { shape = "binary", must_be = true }
# "urgency=normal" = { shape = "scalar", target = 0.7 }
```

See `beeja/prompts/properties.v1.md` for full property semantics.

## Phase-dependent scaffolding

| Phase | Eval cases | Extras | Meta-compatible | Canary % |
|---|---|---|---|---|
| `exploration` | property floor only | + `notes.md` graduation criteria | no | 0 |
| `calibration` | property + provisional | + `notes.md` | no | 5 |
| `optimization` | full suite | — | yes | 10 |
| `maintenance` | frozen | — | weekly only | 10 |

The graduation path: `exploration → calibration → optimization → maintenance`. Most artifacts spend weeks in exploration. Forcing them into optimization on day one is the actual mistake to avoid.

## Hard rules

- Max **3 interview questions** before a draft.
- **Never ask what context already answers.**
- Always show a draft after question 3, even if wrong.
- All output is **shadow-status by default**; promotion goes through the eval bank only.
- The builder **never promotes its own work**.
- **Budget cap**: ~$0.50/session, 30-min wall-clock.

## Bootstrap sequence

1. Build the **prompt library maintainer** with beeja. Bootstraps the registry layer.
2. Build the **eval harness gardener** wired to Inspect AI. Bootstraps scoring.
3. Build the **signal-collector sensor** for one existing artifact. Bootstraps implicit feedback.
4. Build the **meta-improver**, point it at the prompt library maintainer first.
5. Use beeja to improve its own interview prompt. **First closed loop.**

## Repository layout

```
beeja/
├── beeja.toml                  # this builder, as an artifact (with its own [success] block)
├── CHANGELOG.md
├── LICENSE
├── README.md
├── pyproject.toml
└── beeja/                      # the python package
    ├── __init__.py
    ├── __main__.py
    ├── builder.py              # ~280 lines; orchestration only
    ├── prompts/
    │   ├── interview.v1.md
    │   ├── interview.v2.md     # ← active
    │   ├── draft.v1.md
    │   ├── draft.v2.md         # ← active
    │   ├── revise.v1.md
    │   ├── revise.v2.md        # ← active
    │   └── properties.v1.md    # the eight universal properties
    ├── templates/
    │   ├── sensor.toml         # supports subtype=signal_collector
    │   ├── transform.toml
    │   ├── scorer.toml         # supports subtype=learned_scorer
    │   ├── applier.toml        # idempotence forced ON
    │   └── meta.toml           # monotonicity forced ON
    └── evals/
        ├── interview_quality.yaml
        └── draft_acceptance.yaml
```

## Status

v0.1 (built on v2 prompts). Interview → draft → revise loop works end-to-end. Property floor is declared; the test runner is on the roadmap (v0.2). No execution spine yet — that's the second artifact beeja helps you build.

## Contributing

```bash
# 1. Install dev deps (one-time, into a venv)
pip install -e ".[dev]"

# 2. Activate the pre-commit hook (one-time per clone)
git config core.hooksPath .githooks
```

The hook runs on every `git commit` and enforces:

| Step | Tool | Fix command |
|---|---|---|
| Manifest in sync with source | `python -m beeja._manifest --write` | auto-staged |
| Lint clean | `python -m ruff check beeja tests` | `ruff check --fix beeja tests` |
| No dead public symbols | `python -m beeja._dead_code` | delete or use the symbol |
| Tests pass | `python -m pytest -q` | fix the failure |

CI runs the same four checks on every push and PR, so `--no-verify` will not save you. To skip the hook locally for a WIP commit: `git commit --no-verify`.

### Where to add code

- **New capability** → add a function to `beeja/ops.py`. The CLI (`beeja --foo`) and MCP tool (`tool_foo`) become thin wrappers. A `tests/test_conformance.py` test asserts both surfaces stay aligned.
- **Internal helper** → add to `beeja/builder.py` or `beeja/backends.py` and call it from ops. The dead-code scan flags it if nothing references it.
- **New entry-point flag** → mirror it in `beeja/mcp_server.py` so CLI and MCP capability parity holds.

## Failure modes & escape hatches

- **Over-interview** — hard cap at 3 questions; runtime forces JSON handoff with inferred assumptions.
- **Wrong template** — revise phase emits `<reclassify>` if edits suggest a different shape.
- **Wrong phase** — revise phase handles transitions (`exploration → calibration → optimization`) explicitly.
- **Property floor too strict** — turn properties off explicitly in the spec; never leave them implicit.
- **Unknown success** — set `specification = property` and `phase = exploration`. Collect outputs while you figure it out.

## Roadmap

- **v0.2** — property-floor test runner wired to Inspect AI.
- **v0.3** — auto-trigger from conversation logs.
- **v0.4** — DSPy / GEPA integration in the draft phase.
- **v0.5** — OpenTelemetry export to a shared backend.

## License

MIT.
