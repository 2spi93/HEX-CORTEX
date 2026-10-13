# HEX-CORTEX V24 — Prevent negative transfer from old scalar answers

## Operator observation (2026-10-13)

Local Windows checkout: **1825 passed**, Ruff clean.
A CPU-only Qwen2.5 3B, four-arm, operator-selected comparison gave:

| Arm | Answer to 127×419 | Strict correctness |
|---|---:|---|
| Baseline | 53813 | Wrong |
| Memory only | 52451 | Wrong |
| Calculator only | 53213 | Correct |
| Memory + calculator | 53213 | Correct |

The training episode used **127×413 = 52451**. Thus the memory-only
answer exactly copied the **previous task's answer**. This is a strong
single-case indication of **negative transfer / answer anchoring**, not
evidence of useful memory generalization. The calculator-containing arms
received the correct evaluation answer explicitly.

## Engineering correction

- New `cortex_math_fact_scope_v24.math_fact_applicability` checks
  independently verified arithmetic provenance and compares canonical
  **expression ASTs**, rather than assuming a correct numeric answer
  is reusable across different arithmetic expressions.
- The production `run_memory_augmented_task` context now filters
  arithmetic **scalar-result memories** by default: only the same
  verified expression can enter model context. If the operator
  supplies no explicit target expression, no such scalar memory is
  injected. This is fail-closed for that memory category.
- A different expression, an ambiguous or unsupported expression,
  and a forged math proof are not accepted as applicable context.
  Ordinary non-math memories remain eligible under their existing
  provenance checks and retrieval policies.
- `cortex_memory_augmented_cli` now supports
  `--target-math-expression`. The caller must ensure this is the
  actual expression in the task; the current implementation does
  **not** independently parse arbitrary natural-language instructions
  and attest this correspondence.
- The V23 four-arm evaluator is explicitly **diagnostic**: it still
  supplies the historic cross-expression answer to the memory arm
  to preserve comparability with the operator's first run, and now
  reports `negative_transfer_training_answer_copy_observed` and
  `answer_copied_from_training_fact`. Do not deploy its forced
  cross-expression memory injection as a normal inference policy.

## Safe commands — PowerShell, one physical line each

Synchronize checkout, run all regression tests and Ruff:

```powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
```

To test V24 against your real, previously saved arithmetic fact,
use these commands after creating the MathCell fact/checkpoint through
`cortex_verified_math_memory_cli`. The `--spine-file` and
`--checkpoint` must actually exist; the CLI never invents proof data.

A different arithmetic expression will result in zero retrieved
scalar-answer memories (but the operator-authorized model call still
runs normally):

```powershell
python -m hex_cortex.memory.cortex_memory_augmented_cli --project-root . --spine-file receipts/math-fact-001-spine.jsonl --checkpoint receipts/math-fact-001-checkpoint.jsonl --task-id eval-scope-002 --instruction "What is 127*419?" --target-math-expression "127*419" --model qwen2.5:3b --approve-model --approve-memory-use --print-answer
```

The same expression `127*413` is eligible when explicitly provided,
so only a truly relevant verified fact is used. Identical expression
does not mean mathematical *method* generalization.

## Next capability gap

A reusable **method/skill** is different from a stored **answer**.
To measure transferable mathematical reasoning, store source-verified
methods (rules with applicability conditions and separate assessments)
and use new, pre-registered problems rather than individual historic
scalar answers. Keep memory relevance, provider output quality,
tool correctness and causal inference as distinct evaluation axes.
