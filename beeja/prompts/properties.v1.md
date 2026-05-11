# Universal Properties — Shared Reference v1

This file is referenced by every artifact's `[success.properties]` block. It defines the eight
universal properties that LLM artifacts can adopt as a *property floor* — checks that hold
regardless of what "good" means for the specific task.

Properties are opt-in per artifact, but every artifact should consider all eight and explicitly
choose `true | false | { enabled = ..., ... }` for each.

## The eight properties

### 1. schema_validity
The output parses as the declared output schema (TOML, JSON, pydantic model, etc.).
- **Default:** `true` for every artifact that has a declared output schema.
- **How tested:** parse the output; fail if it doesn't.

### 2. bounded_cost
Every invocation honors its declared budget — tokens, wall-clock, dollars.
- **Default:** `true`.
- **How tested:** the runtime enforces caps; violations are property failures, not just warnings.

### 3. determinism
Same `(input, prompt, model, seed)` produces the same output bytes (or known-tolerance hash).
- **Default:** `true` for `temperature = 0` artifacts; `false` for sampling artifacts.
- **How tested:** run the same input twice; compare. Tolerance configurable.

### 4. idempotence
`f(f(x)) ≈ f(x)` where the task should converge. Critical for retry-safe artifacts (especially appliers).
- **Default:** `false` (most transforms don't have this property); `true` for appliers and sensors (no duplicate emissions on retry).
- **How tested:** run the output back through the artifact; check output is stable.

### 5. refusal_symmetry
The artifact refuses on input `x` iff `x ∈ defined_unsafe_set`. Spurious refusals (or spurious compliance) are bugs.
- **Default:** `false` unless the artifact has refusal behavior.
- **How tested:** evaluate on labeled safe/unsafe pairs; check classification matches.

### 6. monotonicity
Adding more *relevant* context never degrades performance on the eval suite. (Adding noise is allowed to degrade.)
- **Default:** `false` (hard to test reliably).
- **How tested:** generate context-augmented variants of eval cases; verify score doesn't drop.

### 7. rephrase_stability
Semantic-preserving input rephrasings yield semantic-preserving output changes.
- **Default:** `false` (expensive to test).
- **How tested:** rephrase each eval input via a separate model; compare outputs by semantic similarity. Configurable distance threshold.

### 8. calibration
If the artifact emits confidence/probability, the predicted probability matches realized accuracy within tolerance (e.g., Expected Calibration Error).
- **Default:** `false` unless the output schema includes a confidence field.
- **How tested:** bin predictions by confidence; compare bin accuracy. Tolerance via max ECE.

## Spec format

```toml
[success.properties]
schema_validity    = true
bounded_cost       = true
determinism        = true
idempotence        = false
refusal_symmetry   = false
monotonicity       = false
rephrase_stability = false
calibration        = false
```

Or with per-property configuration via inline tables:

```toml
[success.properties]
schema_validity    = true
bounded_cost       = true
determinism        = { enabled = true, tolerance_bytes = 0 }
calibration        = { enabled = true, max_ece = 0.05 }
rephrase_stability = { enabled = true, max_distance = 0.3, n_rephrases = 5 }
```

## When properties are the *only* specification

In `phase = "exploration"` mode with `specification = "property"`, properties are not a floor —
they are the entire success specification. The artifact runs, properties are checked on every
output, and outputs accumulate. No promotion happens; no meta-improver runs. The eight properties
provide just enough discipline to keep the artifact from drifting silently while you figure out
what "ceiling" criterion you actually want.

## Adding a new property

If you find yourself wanting a 9th property that several artifacts share, that's a registry-level
operation: add it to this file, give it a default, define its test method. Like any artifact
change, it goes through shadow → eval → promote.
