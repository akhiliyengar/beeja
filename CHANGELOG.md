# CHANGELOG

## v0.1.0 — 2026-05-11

First tagged release. Renamed package from internal working name to `beeja`; relayouted so prompts, templates, and eval suites live inside the python package and ship with `pip install beeja`.

### Added

- `beeja` console script (`beeja "intent"` and `beeja --revise NAME`).
- `python -m beeja "intent"` entry point.
- `beeja --version`.
- `LICENSE` (MIT).
- Sdist + wheel build via hatchling.
- **Pluggable LLM backends** via `BEEJA_LLM_BACKEND` env var:
  - `anthropic` (default) — direct Anthropic API, requires `ANTHROPIC_API_KEY`.
  - `vscode` — bridges to GitHub Copilot via a sibling VS Code extension
    (`vscode-extension/`). Uses the user's Copilot subscription. Requires the
    extension to be installed and VS Code running.
- `beeja/backends.py` — backend abstraction (LLMBackend ABC, lazy construction,
  env-var dispatch).
- `vscode-extension/` — sibling TypeScript extension that exposes `vscode.lm`
  as `http://127.0.0.1:21847`. Writes its port to `~/.beeja/bridge.port` for
  CLI discovery.

### Changed

- Project name: was internal working name → `beeja`.
- Python package: was `skill/` → `beeja/`.
- Resource layout: `prompts/`, `templates/`, `evals/` moved from project root into the `beeja/` python package so installed wheels ship them as package data.
- Imports: `from skill import ...` → `from beeja import ...`.
- CLI: `python -m skill.builder ...` → `beeja ...`.
- Path resolution in `builder.py`: `BUILDER_DIR = parent.parent` → `PKG_DIR = parent`. Resolves correctly whether invoked from source checkout or installed wheel.
- Env vars: `AGENTS_SHADOW_ROOT` → `BEEJA_SHADOW_ROOT`; `BUILDER_MODEL` → `BEEJA_MODEL`.
- `beeja.toml` (was `builder.toml`): updated prompt/template/eval paths to reflect new layout.

### Internal

- All v1 and v2 prompts preserved (v1 prompts kept for replay and meta-improvement diffing).
- Five templates unchanged in content; rewritten in v2 to carry the three-axis `[success]` block, `[success.properties]` floor, and optional `[success.context_match]`.
- 16 + 17 eval cases preserved.

---

## v2 prompts — 2026-05-11 (incorporated into v0.1.0)

Three orthogonal additions to the success specification. None grew the five-template alphabet.

### Added — three-axis `[success]` block

Every artifact spec carries:
- `success.shape` — `binary | scalar | multi_class | ordinal | vector | distributional | set | rank`
- `success.specification` — `explicit | property | implicit | learned | hybrid`
- `success.phase` — `exploration | calibration | optimization | maintenance`

Plus shape-specific fields (target/range for scalar, classes for multi_class, dimensions/composition for vector, etc.) — see `beeja/prompts/draft.v2.md`.

### Added — universal property floor

A `[success.properties]` block with eight always-considered properties:

1. schema_validity
2. bounded_cost
3. determinism
4. idempotence
5. refusal_symmetry
6. monotonicity
7. rephrase_stability
8. calibration

Each artifact explicitly sets every property to `true | false | { ... config }`. Property semantics and defaults documented in `beeja/prompts/properties.v1.md`.

Per-template forced defaults:
- **applier**: `idempotence = true` (retry must be safe)
- **meta**: `monotonicity = true` (proposals must not regress)

### Added — phase-dependent scaffolding

| Phase | Eval cases | Files | Meta-compatible | Canary % |
|---|---|---|---|---|
| `exploration` | property floor only | + `notes.md` graduation criteria | false | 0 |
| `calibration` | property + provisional | + `notes.md` | false | 5 |
| `optimization` | full eval suite | — | true | 10 |
| `maintenance` | frozen | — | weekly only | 10 |

### Added — context-conditional criteria

Optional `[success.context_match]` block for artifacts whose success bar depends on input context:

```toml
[success.context_match]
"urgency=high"   = { shape = "binary", must_be = true }
"urgency=normal" = { shape = "scalar", target = 0.7 }
```

### Added — subtypes for implicit-feedback workflows

- `sensor[subtype=signal_collector]` — watches user behavior on a target artifact's outputs, emits `signals.<target>` events.
- `scorer[subtype=learned_scorer]` — references a sibling preference-model artifact via `[scoring].model_artifact`.

### Changed — Q3 of the interview

Was: "What would tell us it's working?"
Now: "What would tell us it's working? If you don't know yet, what's the worst thing that should *never* happen — at least an invariant we can hold while we figure out the rest?"

The escape hatch legitimizes `phase = exploration` without breaking the three-question rule.

---

## v1 prompts — 2026-05-11

Initial build. Five templates (sensor, transform, scorer, applier, meta), three interview phases (interview, draft, revise), single string `success_criterion`, no property floor, all artifacts implicitly in optimization phase.

Superseded by v2 the same day after design review surfaced shape/specification/phase as orthogonal.
