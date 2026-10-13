# HEX-CORTEX V25 — Procedural Skills, Transfer Evidence and Revocation

## Goal and architecture

A replayed correct answer is an episodic fact, **not a transferable skill**.
V23 demonstrated negative transfer (127×413=52451 copied into 127×419).
V24 now filters scalar memories for different expressions. V25 separately
studies what happens when a language model receives a **general method**
rather than an answer.

Reuse existing systems rather than replacing them:

- `ExactMathCell`: independent bounded exact-rational oracle for each
  training example and **each separate** evaluation problem.
- `LocalHarness` + `CognitiveClock`: two independent calls of the same
  explicitly authorized model per case; receipts and Spine validated.
- Existing `cortex-skill-candidate`, `cortex-skill-library`,
  activation gate, **manual activation**, active index and usage history
  remain the **only** historical skill authority.
- `cortex_procedural_skill_evidence_v25.py` is only a supporting,
  operator-approved, redacted **evidence sidecar**, not a new active registry.
  Its hash is not a digital signature, and stored scores are not independent
  attestation.
- `cortex_skill_capability_audit_v25.py` provides a read-only inventory of
  this pre-existing pipeline and the evidence sidecar.

## Three bounded methods actually executable in evaluation

| Method | Applicability | Operator-independent verification |
|---|---|---|
| `multiply_decomposition` | `a*b` integers within operand bounds | Distributivity using tens, cross-checked by ExactMathCell |
| `fraction_reduction` | `a/b`, integer operands, nonzero divisor | Exact gcd reduction, checked against exact rational |
| `addition_compensation` | `a+b` with bounded integers | Arithmetic compensation, checked by ExactMathCell |

These are **implemented, bounded procedures**. They are not three new LLM
weights, three verified domain experts, autonomous self-learning, or proof of
cognitive transfer. Every LLM result must be tested separately.

The evaluations use three fixed, known training examples and up to four
different evaluation expressions per skill. The model is NOT shown
the evaluation answer in either arm. It receives only the fixed method in
the skill arm. Model order alternates between pairs. Every result is scored
using the independent exact oracle, with both improvement and regression
counts kept visible. Public fixtures are not independently held out.

### Promotion discipline

- An exploratory candidate is **eligible for manual review** only if four or
  more unseen test cases have been evaluated, at least three skill-arm
  answers are correct, the skill arm outperforms baseline, and **zero**
  baseline-correct / skill-wrong regressions occur.
- A regression yields a **quarantined** evidence receipt.
- An operator can append a **revoked** record; future evidence cannot
  silently reactivate that skill ID. No automatic promotion or model/tool
  activation occurs in any V25 CLI.
- An advisory review recommendation is **not a production activation**.
  Actual activation still requires the legacy HEX-CORTEX manual gates.

## Commands (Windows PowerShell — each one physical line)

Full latest regression + lint:

```powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
```

Safe **zero-inference** method preview:

```powershell
python -m hex_cortex.memory.cortex_procedural_transfer_cli_v25 --skill multiply_decomposition --model qwen2.5:3b --cases 4 --dry-run
```

Real CPU-only Qwen **8-call** benchmark (four two-arm pairs, no answer
leakage, no files written unless explicit saving flags are supplied):

```powershell
python -m hex_cortex.memory.cortex_procedural_transfer_cli_v25 --project-root . --skill multiply_decomposition --model qwen2.5:3b --cases 4 --approve-model-calls --approve-procedure --show-answers --timeout 120
```

Same comparison, with an **additional explicit authorization** to store
only redacted trial evidence (creates
`cortex-procedural-transfer-evidence-v25.jsonl` under the selected
project root; ignored by Git):

```powershell
python -m hex_cortex.memory.cortex_procedural_transfer_cli_v25 --project-root . --skill fraction_reduction --model qwen2.5:3b --cases 4 --approve-model-calls --approve-procedure --save-evidence --approve-save-evidence --timeout 120
```

Evaluate addition compensation (another eight CPU-only calls):

```powershell
python -m hex_cortex.memory.cortex_procedural_transfer_cli_v25 --project-root . --skill addition_compensation --model qwen2.5:3b --cases 4 --approve-model-calls --approve-procedure --timeout 120
```

Inspect V25 transfer evidence without touching it:

```powershell
python -m hex_cortex.memory.cortex_procedural_skill_evidence_cli_v25 --project-root . --skill multiply_decomposition
```

Operator-authorized revocation of a specific method ID:

```powershell
python -m hex_cortex.memory.cortex_procedural_skill_evidence_cli_v25 --project-root . --skill multiply_decomposition --revoke --reason "Regression detected on independent test set" --approve-revoke
```

**Do not run the revocation command unless you deliberately want that
method ID permanently marked as revoked in the local evidence ledger.**

Inspect the EXISTING skill pipeline in read-only mode (point `--profile`
at the appropriate profile directory; `.` is only an example):

```powershell
python -m hex_cortex.memory.cortex_skill_capability_audit_cli_v25 --profile .
```

## Honest coverage and future priorities

- Existing learning/candidate/library/activation components are
  **documented and inspectable**. A V25 successful trial is not yet
  imported into the historical candidate/activation pipeline because
  that would blur exploratory trial evidence and operator-approved skill
  provenance. A controlled migration with verified lineage is a
  subsequent gate.
- No blind skill search or general domain inference has been certified.
  Physics/Chemistry currently have deterministic verified cells and memory
  episodes, **not** tested human-like cross-domain procedural learning.
- Future expert portfolios: formal verification and symbolic algebra,
  unit-safe numerical modelling and uncertainty, chemistry source
  validation, source-linked research, code/test repair, architecture
  review, robust tool selection, retrieval calibration, scientific
  planning and world-model residual analysis. Build only against
  repeatable trusted evidence, and keep dangerous device operations
  outside the model's direct authority.
- Score **cost, latency, regressions, non-response and contamination**
  across balanced, independently held-out tasks before announcing
  improved general reasoning or an active new skill.
