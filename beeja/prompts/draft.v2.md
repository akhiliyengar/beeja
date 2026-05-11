# Builder — Draft Phase v2

You receive the interview phase's JSON output plus a template skeleton. You produce a complete, runnable artifact bundle: TOML spec (with the three-axis `[success]` block) + prompt file(s) + code skeleton + 2–3 eval cases.

## What changed from v1

The TOML spec now carries a structured `[success]` block with three orthogonal axes (shape, specification, phase) plus opt-in property floor and optional context-match table. The eval bundle, scaffolding, and even the *presence* of certain files now depend on the phase. See "Phase-dependent scaffolding" below.

## Hard rules

- **Use the chosen template as your skeleton.** Fill placeholders with concrete values. Don't introduce structure the template doesn't have (unless `freeform`).
- **Two placeholder styles to fill:**
  - `{{mustache}}` — scalar substitution. Replace with concrete value.
  - `"<FILL: hint>"` — list-element or multi-value substitution. Replace the whole sentinel string and adjust sibling list elements.
- **No placeholders survive in the final bundle.** No `TODO`, `{{var}}`, `<FILL: ...>`, `FIXME`, `XXX`.
- **Eval cases must be runnable**, not abstract. If you can't write a runnable case, you don't understand the success criterion well enough — say so in `<assumptions>`.
- **Default to small.** Shortest viable prompt, smallest budget, fewest dependencies.
- **Surface every assumption.** Anything inferred-but-unstated goes in `<assumptions>`.

## Filling the `[success]` block (the v2 heart)

The interview output contains `success: { shape, specification, phase, description, context_match }`. Use it directly. Then add shape-specific fields:

```toml
[success]
shape         = "<from interview>"
specification = "<from interview>"
phase         = "<from interview>"
description   = "<from interview>"

# shape-specific fields — only populate the relevant ones:

# shape = "binary":
must_be = true

# shape = "scalar":
range     = [0.0, 1.0]
target    = 0.7
direction = "maximize"   # or "minimize"

# shape = "multi_class":
classes      = ["nit", "minor", "major", "critical"]
target_class = "minor"   # this class or better
ordering     = "lex"

# shape = "ordinal":
levels       = ["stale", "fresh", "live"]
target_level = "fresh"

# shape = "vector":
dimensions  = ["quality", "latency_ms", "cost_dollars"]
directions  = ["maximize", "minimize", "minimize"]
composition = "pareto"
# weights only when composition = "weighted_sum"

# shape = "distributional":
metric    = "ece"   # or "kl", "tv", etc.
target    = 0.05
direction = "minimize"

# shape = "set":
metric = "f1"   # or "precision", "recall", "iou"
target = 0.8

# shape = "rank":
reference_order = "<asset name of reference ordering>"
metric          = "spearman"
target          = 0.6
```

## The property floor — always populate

Every artifact gets a `[success.properties]` block. Set each of the eight to a sensible default per the artifact's nature. Refer to `prompts/properties.v1.md` for full semantics.

Sensible defaults per template:

| template | schema_v | bounded | determ | idempot | refusal | mono | rephrase | calibr |
|---|---|---|---|---|---|---|---|---|
| sensor | true | true | true | true | false | false | false | false |
| transform | true | true | true* | false | false | false | false | false |
| scorer | true | true | true | false | false | false | false | maybe |
| applier | true | true | true | **true** | maybe | false | false | false |
| meta | true | true | true | false | false | true | false | false |

*determ depends on temperature setting; true if `temperature = 0`.

Adjust per the interview's `properties_hint` field — if the user emphasized invariants beyond the defaults, turn those on with appropriate config.

## Phase-dependent scaffolding (critical, new in v2)

The phase determines what files the bundle includes:

### `phase = "exploration"`

- **No eval cases against the success criterion** — there isn't one yet.
- Eval cases ONLY test the property floor.
- No meta-improver target — set `meta_compatible = false` in the artifact spec.
- Set `[promotion].canary_traffic_pct = 0` — everything stays in shadow.
- Add a `notes.md` file with a checklist for graduating to `calibration` (typically: ≥50 outputs collected, ≥1 review pass).

### `phase = "calibration"`

- Eval cases test both the property floor AND the rough success criterion.
- Include a "graduation criteria" section in `notes.md`.
- Implicit-signal sensor companion: if specification is `learned` or `implicit`, the bundle includes a sibling artifact: a sensor of subtype `signal_collector` that watches outputs of this artifact and emits accept/edit/discard events.
- `[promotion].canary_traffic_pct = 5` (very cautious).

### `phase = "optimization"`

- Full eval suite with concrete success cases.
- Meta-improver compatible (`meta_compatible = true`).
- `[promotion].canary_traffic_pct = 10` (standard).

### `phase = "maintenance"`

- Eval suite frozen.
- Set `[cache].ttl_days = 90` (long, since changes are rare).
- Meta-improver runs weekly, not daily (override the meta template's schedule).

## Context-conditional criteria

If the interview set `context_match = true`, scaffold a `[success.context_match]` table with 2–3 plausible context values (inferred from the description) and shape-appropriate criteria per value:

```toml
[success.context_match]
"urgency=high"   = { shape = "binary",  must_be = true }
"urgency=normal" = { shape = "scalar",  target = 0.7 }
"urgency=low"    = { shape = "scalar",  target = 0.5 }
```

List the context dimensions as assumptions; the user will confirm or correct in revise.

## Special subtypes

If the interview set `subtype = "signal_collector"`:
- Template is `sensor`.
- The sensor's emitted asset is `signals.<target_artifact>` — observations of user behavior on the target's outputs.
- Specification is `property` (the floor is: never miss a signal, no duplicate signals).

If the interview set `subtype = "learned_scorer"`:
- Template is `scorer`.
- The scorer's `[scoring]` block includes `model_artifact = "<a learned preference model artifact>"` referencing a sibling transform that fits the model from signal history.
- Phase typically starts at `calibration` and graduates to `optimization` once the model has stabilized.

## Naming convention (unchanged from v1)

- Artifact directory: lowercase snake_case from output asset.
- Prompt files: `prompts/<role>.v1.md` (always v1 on first creation).
- Eval cases: `evals/cases.yaml`.

## Output format

```
<bundle>
<file path="artifacts/<name>/<name>.toml">
... filled TOML with [success] block, [success.properties] block, optional [success.context_match] ...
</file>

<file path="artifacts/<name>/prompts/main.v1.md">
... the actual runtime prompt ...
</file>

<file path="artifacts/<name>/skill/main.py">
... ~50 lines of orchestration. Load prompt, parse input, call LLM, validate output (including property checks), write asset, log. No heavy frameworks in v1 of a new artifact.
</file>

<file path="artifacts/<name>/evals/cases.yaml">
suite: <name>
description: ...
cases:
  # property-floor cases (always present):
  - id: schema_validity
    ...
  - id: bounded_cost
    ...
  # success cases (only if phase != "exploration"):
  - id: smoke_<something>
    ...
</file>

<file path="artifacts/<name>/notes.md">
# <name>

Phase: <phase>

## Graduation criteria
(only present if phase ∈ {exploration, calibration})

- ...

## Open questions
- ...
</file>

<assumptions>
- <each inference and why>
</assumptions>
</bundle>
```

## What good output looks like

- TOML parses cleanly.
- `[success]` block populated with all three axes plus shape-specific fields.
- `[success.properties]` block has all 8 properties explicitly set (true/false/config).
- Property-floor eval cases present regardless of phase.
- Success-criterion eval cases present only when `phase != "exploration"`.
- `notes.md` present when phase ∈ `{exploration, calibration}` with concrete graduation criteria.
- Python skeleton ≤80 lines, no heavy imports.

## What bad output looks like

- Unfilled placeholders.
- `[success.properties]` block omitted ("just doing the standard").
- Exploration-phase artifact with success-criterion eval cases (premature).
- Optimization-phase artifact with no concrete eval cases (vacuous).
- Multi-class success that lists no classes.
- Vector success that doesn't say `composition = pareto | weighted_sum | lex`.
