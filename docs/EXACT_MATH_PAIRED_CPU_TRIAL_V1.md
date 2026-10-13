# HEX-CORTEX — ExactMathCell + local Qwen paired trial V1

## Objective and limits

This experimental rail connects an **already implemented** verified
`ExactMathCell` to the actual `LocalHarness` / `CognitiveClock`, then
runs two CPU-only calls of the same model, one without and one with a
separately verified arithmetic result.

The independent calculation is **given to the CORTEX arm**. This is a
comparison of *calculator-assisted answering*, NOT a demonstration that the
LLM internally reasons better. Unlike the memory checkpoint experiments,
this experiment does not measure memory reuse. The separate memory/Harness
integration remains in place and unchanged.

- `ExactMathCell` uses bounded exact rational arithmetic and a second
  evaluator for consistency. It rejects unsupported syntax and division
  by zero before calling the model.
- Both arms use the same operator-provided mathematical expression, model ID,
  temperature (0.0), token limit, host and local Ollama adapter.
- The caller can reverse arm order to explore order effects.
- Each model call uses a fresh `LocalHarness` with explicit `CALL_MODEL`
  grant, single-call budget, CognitiveClock ticks and independent Spine.
- Local inference must be authorized with `--approve-two-calls` and
  computation with `--approve-math`. `num_gpu=0` is forced.
- Model responses are compared to the independently computed rational using
  **strict** text-to-rational parsing. Narrative text is not accepted as a
  correct answer.
- No raw outputs, prompts, checkpoints or local receipts are written by the
  trial. CLI prints only hashes, scores, receipt identities and latencies by
  default; `--show-answers` explicitly reveals the two outputs.
- The model ID is the same, but the runtime does **not** independently attest
  the installed model revision or the underlying host. There is no external
  attestation of holdout, task selection or real provider calls.
- A single pair, especially on a simple calculation, is **not statistical
  evidence** of amplification. `causal_effect_certified` and
  `general_intelligence_certified` remain false.

## Operator commands — single physical line each (PowerShell)

Preflight without reading data, math calculation, model call or GPU:

```powershell
python -m hex_cortex.memory.cortex_verified_math_pair_cli --project-root . --expression "17*23" --model qwen2.5:3b --dry-run
```

Exploratory paired run with two operator-approved Ollama model calls
(CPU only; may take a few minutes):

```powershell
python -m hex_cortex.memory.cortex_verified_math_pair_cli --project-root . --expression "17*23" --model qwen2.5:3b --approve-math --approve-two-calls --show-answers --timeout 120
```

Reverse call order on a **different** operator-selected expression:

```powershell
python -m hex_cortex.memory.cortex_verified_math_pair_cli --project-root . --expression "127*413" --model qwen2.5:3b --order cortex-first --approve-math --approve-two-calls --timeout 120
```

Tests + lint:

```powershell
python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
```

## Road to an actual defensible scientific result

Pre-register a held-out suite with several task families and difficulties,
independent oracles, arm-order balancing, revision IDs, repeated runs, costs,
latencies, abstentions and errors. Include **unassisted model, model + memory,
model + independent calculators, and ablations**, rather than conflating all
organs as one treatment. The existing paired V21 scorer can summarize
operator-captured observations but must not certify unverified causal claims.
