# HEX-CORTEX — Parallel integration: governed cognition, October 2026

## A. Verified multi-case MathCell experiments (already wired)

`cortex_verified_math_batch.py` orchestrates the existing
`run_verified_math_pair` (actual LocalHarness, CognitiveClock,
ExactMathCell) on a **fixed public** 10-case set. Runs 1–10 operator-approved
pairs, alternating arm order; stops on any incomplete pair. Computes
correct-answer counts, asymmetric discordances and descriptive exact McNemar
p-values, plus cumulative model-call latencies. These are **not held-out
tasks**, do not attest model revision, do not account for contamination, and
do not prove general intelligence or causality.

Windows PowerShell — one physical line per command:

```powershell
python -m hex_cortex.memory.cortex_verified_math_batch_cli --project-root . --model qwen2.5:3b --pairs 3 --dry-run
```

To authorize **up to six CPU-only Ollama calls** (3 matched pairs, 120s
model timeout per arm):

```powershell
python -m hex_cortex.memory.cortex_verified_math_batch_cli --project-root . --model qwen2.5:3b --pairs 3 --approve-math --approve-all-calls --timeout 120
```

The CORTEX arm receives the actual independent calculation result; this
demonstrates **calculator-assisted answering**, not reasoning from raw memory.

## B. ExactMathCell → scientific fact → Replay → Memory → Checkpoint

`cortex_verified_math_memory.py` uses a real computation, a second
verification and strict `math.exact_verified` event payload. The fact is
then processed by the existing `ReplayEngine`, `MemoryPromoter`,
`VerifiedLearningLoop`, `LocalKnowledgeIndex` and `RetrievalRouter`.

The context-injection path rechecks **all math-tagged source-task events**
against the live ExactMathCell. A forged math fact with a perfectly valid
hash chain must never be treated as independently verified arithmetic.
Ordinary non-math memories remain **untrusted model context**.

Safe offline read-only preflight:

```powershell
python -m hex_cortex.memory.cortex_verified_math_memory_cli --project-root . --task-id math-fact-001 --expression "127*413" --dry-run
```

Explicit operator-approved construction, promotion and persistence of
two *new* files in `receipts/` (do not commit either file):

```powershell
python -m hex_cortex.memory.cortex_verified_math_memory_cli --project-root . --task-id math-fact-001 --expression "127*413" --approve-record --approve-promote --approve-persist --spine-output receipts/math-fact-001-spine.jsonl --checkpoint-output receipts/math-fact-001-checkpoint.jsonl
```

To use the persisted fact via the existing CPU-only memory-augmented
Ollama Harness (explicit model and memory approvals):

```powershell
python -m hex_cortex.memory.cortex_memory_augmented_cli --project-root . --spine-file receipts/math-fact-001-spine.jsonl --checkpoint receipts/math-fact-001-checkpoint.jsonl --task-id math-question-002 --instruction "What is 127*413?" --model qwen2.5:3b --approve-model --approve-memory-use --print-answer
```

This shows **verified source-linked retrieval**. A single retrieved
fact, especially one directly supplying the answer, is not a credible
experimental generalization or proof of learning.

## C. Math + physics + chemistry through the original CognitiveCircuit

`cortex_verified_science_circuit.py` integrates the preexisting
`math_cell_result`, `physics_cell_result` and
`chemistry_cell_result` with `CellRegistry`, `ThalamicRouter`,
`CognitiveClock`, `GlobalWorkspace` and `CanonicalSpine`.

Each request stays within its original domain/typed input format.
The trusted Python host recomputes the candidate, checks the evidence,
and the circuit records redacted decision receipts. No LLM, robot,
drone, device, network, file mutation or implicit source verification.

```powershell
python -m hex_cortex.core.cortex_verified_science_circuit_cli --domain mathematics --example --approve-run
```

```powershell
python -m hex_cortex.core.cortex_verified_science_circuit_cli --domain physics --example --approve-run
```

```powershell
python -m hex_cortex.core.cortex_verified_science_circuit_cli --domain chemistry --example --approve-run
```

**Scientific limits:** PhysicsCell computes idealized classical
formulae with SI checks; ChemistryCell performs idealized stoichiometry
with rounded reference masses. Recomputing with the same module does NOT
constitute independent experimental validation, real-world measurement,
reaction feasibility or safe physical actuation.

## Validation and advancement

```powershell
python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
```

Remaining empirical work:

- pre-register **held-out** questions and separate truly unknown oracles;
- compare same model revision on blind data, balance order and replicate;
- compare no-cortex, memory-only, calculator-only and combined modes;
- record full tokens, latency, refusal and failure modes;
- remove automatic factual authority from any unauthenticated source;
- train JEPA or distill only after data quality, safety and generalization
  have been established independently.
