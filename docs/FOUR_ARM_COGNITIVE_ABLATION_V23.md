# HEX-CORTEX V23 — Four-arm, source-checked memory-vs-calculator experiment

## Why this exists

The first real Qwen2.5 3B test on the operator's PC gave 0/3 correct
without ExactMathCell and 3/3 with the exact answer in context. This
is useful, but it does not isolate **memory reuse** from **calculator
assistance**, nor establish general intelligence amplification.

V23 runs four separately authorized model calls on a *different*
mathematical question from the recorded training fact:

| Arm | Existing verified memory | ExactMathCell's test answer |
|---|---|---|
| baseline | no | no |
| memory | yes, from another task | no |
| calculator | no | yes |
| combined | yes, from another task | yes |

The training fact is created with \`append_verified_math_fact\` and
\`verify_math_fact_task\` in a fresh RAM-only \`CanonicalSpine\`;
\`VerifiedLearningLoop\` performs Replay/Promotion. The memory context is
reconstructed with the existing source-checked
\`cortex_memory_augmented_run._verified_context\` path. A task's own
memory and an evaluation answer appearing in memory are forbidden.

The evaluation answer is calculated **independently** by the original
ExactMathCell and used by a strict numerical scorer. It is **never**
included in the baseline or memory-only prompts. It is given verbatim
to the calculator and combined arms by design.

Each arm goes through a fresh \`LocalHarness\` with exactly one
\`CALL_MODEL\` capability, one-call budget, zero tool calls,
\`CognitiveClock\` ticks, receipt and Spine integrity verification.
There is no automatic persistence, remote action, GPU use or training.
There is no real-model inference in automated tests: all stubs are
deterministic, offline simulations.

## Operator commands — one physical PowerShell line each

Synchronize and verify the checkout:

\`\`\`powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
\`\`\`

Safe preflight (no memory loaded or model called):

\`\`\`powershell
python -m hex_cortex.memory.cortex_four_arm_math_eval_cli_v23 --project-root . --training-expression "127*413" --evaluation-expression "127*419" --model qwen2.5:3b --dry-run
\`\`\`

Operator-authorized CPU-only run (**exactly four** Ollama calls; 120 s
per call):

\`\`\`powershell
python -m hex_cortex.memory.cortex_four_arm_math_eval_cli_v23 --project-root . --training-expression "127*413" --evaluation-expression "127*419" --model qwen2.5:3b --approve-model-calls --approve-memory --approve-calculator --show-answers --timeout 120
\`\`\`

For a second operator-selected *different* pair, reverse the order to
reduce systematic time/order effects, using \`--order-index 1\`.
The \`--dry-run\` mode always calls no models, reads no files and writes
no files.

## Interpretation constraints

- The source memory is **explicitly selected using the training
  expression**, not learned through blind production-grade relevance
  search. Thus this run does *not* benchmark search quality.
- A different expression and a different rational answer are required.
  This blocks exact answer copying from the training example; it does
  **not** guarantee a novel task, prevent conceptual overlap, or
  certify that the model has never seen it during pretraining.
- Four calls on one operator-selected example **do not certify**
  statistical significance, generalization, memory uplift or causality.
- The calculator and combined arms **receive the correct evaluation
  answer directly**; successes represent calculator-assisted answering.
- A model can ignore otherwise valid memory or be harmed by irrelevant
  context. Report regressions rather than suppressing them.
- The model revision, provider execution, provenance of operator-run
  outputs, token counts and thermal effects are not externally
  attested. No raw output or prompts are written to disk by the CLI.
- Independent verification means checking the arithmetic using a
  separate invocation of the exact evaluator; it is not independent
  experimental or physical-world truth.

## Next experiment

Once the operator verifies V23 on their CPU, pre-register a genuine
unseen suite, blind scoring, randomized/balanced order, independent
oracle and fixed inference settings. Use *multiple subjects* and
different scientific domains, not just arithmetic where an oracle
directly provides the answer. Track latency, token cost, tool usage,
failure modes and memory retrieval quality separately.
