# V23 — Scientific memory and four-arm cognitive ablations

## Architecture

1. **ExactMathCell four-arm comparison** — original Harness/CognitiveClock invoked once per arm: baseline / training-memory-only / evaluation-calculator-only / combined. Same model ID and strict rational answer grader. This is an exploratory operator-selected comparison, not a causal result.
2. **PhysicsCell and ChemistryCell memory** — existing deterministic calculations become typed, source-linked `science.verified_domain_fact` episodes; ReplayEngine compresses; MemoryPromoter validates the fact again before index mutation; optional checkpoint reconstructs a verified memory from the original Spine.
3. **Forged-fact protection** — mathematical or scientific claims that disagree with deterministic cells are rejected even if the Spine itself is rehashed consistently. Hashes are not trusted-publisher attestations.

**Limits:** PhysicsCell covers allowlisted idealized classical formulae, not measured reality; ChemistryCell covers atom-balance and idealized stoichiometry, not reaction feasibility or safe laboratory operations. Re-running the same deterministic software does not certify external scientific truth.

## Operator commands (Windows PowerShell, one physical line each)

Four-arm dry run, no model calls, no file reads or writes:

```powershell
python -m hex_cortex.memory.cortex_four_arm_math_eval_cli_v23 --project-root . --training-expression "127*413" --evaluation-expression "127*419" --model qwen2.5:3b --dry-run
```

Four-arm real local CPU Qwen experiment (**four authorized calls**):

```powershell
python -m hex_cortex.memory.cortex_four_arm_math_eval_cli_v23 --project-root . --training-expression "127*413" --evaluation-expression "127*419" --model qwen2.5:3b --approve-model-calls --approve-memory --approve-calculator --show-answers --timeout 120
```

The two expressions and their results must differ. Only the calculator-containing arms receive the actual evaluation answer. The memory-only arm receives a verified fact from a *different* task. Retrieval is intentionally operator-guided, not a blind retrieval benchmark.

Physics memory dry run (no calculation/model/files):

```powershell
python -m hex_cortex.memory.cortex_verified_science_memory_cli_v23 --project-root . --domain physics --example --task-id proof-force-v23 --dry-run
```

Physics fact promotion and persistence — two **new** local files, with three explicit approvals (no model or physical action):

```powershell
python -m hex_cortex.memory.cortex_verified_science_memory_cli_v23 --project-root . --domain physics --example --task-id proof-force-v23 --approve-record --approve-promote --approve-persist --spine-output receipts/proof-force-v23-spine.jsonl --checkpoint-output receipts/proof-force-v23-memory.jsonl
```

Chemistry fact promotion and persistence (only idealized stoichiometry):

```powershell
python -m hex_cortex.memory.cortex_verified_science_memory_cli_v23 --project-root . --domain chemistry --example --task-id proof-chem-v23 --approve-record --approve-promote --approve-persist --spine-output receipts/proof-chem-v23-spine.jsonl --checkpoint-output receipts/proof-chem-v23-memory.jsonl
```

Do not commit local receipt files. Choose new filenames on subsequent runs.

## Interpretation rules

- Score all four arms separately, including regressions and latency.
- Do not attribute calculator-driven improvements to better internal model reasoning or memory learning.
- The operator-selected examples are **not independently attested holdouts**. There is no external confirmation of model revision, provider execution or contamination-free tasks.
- Real scientific inference, physical controls, autonomous training and unverified data ingestion remain outside V23.
