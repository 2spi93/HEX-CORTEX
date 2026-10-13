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


## D. Existing Math / Physics / Chemistry verification feeding the actual Brain

The earlier circuits are connected by
`cortex_science_brain_bridge.py` through an actual
`LocalHarness` and `CognitiveClock` run. Only bounded typed verified
cell payloads are provided as **data** to a separately authorized local
model. A redacted receipt is appended to the same Harness Spine. This
is not a proof that the model's final generated answer is correct; a
new independent check of model output is still required.

CPU-only preflight (no model or file access):

```powershell
python -m hex_cortex.memory.cortex_science_brain_cli --domain physics --example --model qwen2.5:3b --dry-run
```

One approved model call using PhysicsCell:

```powershell
python -m hex_cortex.memory.cortex_science_brain_cli --domain physics --example --model qwen2.5:3b --approve-science --approve-model --show-answer
```

One approved model call using ChemistryCell:

```powershell
python -m hex_cortex.memory.cortex_science_brain_cli --domain chemistry --example --model qwen2.5:3b --approve-science --approve-model --show-answer
```

One approved model call using MathCell:

```powershell
python -m hex_cortex.memory.cortex_science_brain_cli --domain mathematics --example --model qwen2.5:3b --approve-science --approve-model --show-answer
```

No model executes autonomously, no on-device action is allowed, the
scientific request is bounded and validated, no raw model response is
persisted, and GPU offload is disabled (`num_gpu=0`).

## E. Verified science answers and math-fact admission hardening (V22)

The scientific cell results and model responses have **different trust
levels**. The local answer grader (`cortex_science_answer_grade_v22.py`)
now checks an optional strict model-answer format against the already
verified cell payload:

- Mathematics: exact integer or `p/q`, for example `52451`.
- Physics: exact rational followed by a single SI unit, for example `6 N`.
- Chemistry: JSON with exact positive integer coefficient arrays, for example
  `{"reactants":[2,1],"products":[2]}`.

Prose, malformed JSON and incorrect values **do not pass**. A successful
grade means agreement with the verified idealized cell calculation, **not**
external physical truth, chemical feasibility or model general intelligence.
Ordinary natural-language answers can still be returned without a strict
grade (marked `invalid_answer_format`).

CPU-only strict model answer with operator-authorized calculation and model
call:

```powershell
python -m hex_cortex.memory.cortex_science_brain_cli --domain physics --example --model qwen2.5:3b --approve-science --approve-model --strict-answer --show-answer
```

Security change: `MemoryPromoter` now recomputes `math.exact_verified`
source episodes *before* adding memories to the index, even if the
CanonicalSpine hash chain is intact. A restored checkpoint re-enters the
same promotion guard. Memory context injection also performs its own
verification, guarding against a forged promotion manifest. Normal
memory-free inference remains allowed: absence of a qualified memory is
not the same as a rejected model call.

Operator's first public batch observation (Qwen 2.5 3B, 3 pairs):
baseline 0/3, ExactMathCell-assisted 3/3, McNemar two-sided exact p=1/4.
The treatment supplies the **actual answer**, and the sample is small,
public and order-unbalanced. Therefore neither statistical significance
nor unassisted cognition enhancement has been established.
