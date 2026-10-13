# HEX-CORTEX — Memory-augmented local CPU Brain V1

## Status

Executable wiring, **not an intelligence-amplification claim**.

- The **same existing** LocalHarness/CognitiveClock still enforces model grants,
  call budgets, receipt integrity and redacted events.
- The **same** CanonicalSpine, ReplayEngine and MemoryPromoter independently
  reconstruct approved memories before retrieval.
- Only approved, earlier task memories are eligible. The current task never
  retrieves memories originating from its own task ID.
- An arbitrary foreign entry placed directly in LocalKnowledgeIndex is rejected
  from the Brain context. Index-only content is never a proof.
- Retrieved material is bounded and presented to the Brain as **untrusted data**,
  not a system directive. This does **not** protect against prompt injection
  by itself; the host's independent tool gates remain mandatory.
- CLI only supports localhost Ollama with `num_gpu=0`. No cloud, VPS, GPU,
  remote actions, file writes or scheduling are initiated.
- No automatic promotion, no automatic memory storage and no model call
  without explicit approval.

Source: `src/hex_cortex/memory/cortex_memory_augmented_run.py`  
CLI: `src/hex_cortex/memory/cortex_memory_augmented_cli.py`

## Operator instructions (Windows PowerShell, one physical line per command)

Preflight without reading any file or calling Ollama:

```powershell
python -m hex_cortex.memory.cortex_memory_augmented_cli --project-root . --spine-file runtime/spine.jsonl --task-id new-task --instruction "What is a Fibonacci recurrence?" --model qwen2.5:3b --dry-run
```

The following example requires a **real previously saved, verified**
`runtime/spine.jsonl` from an authorized HEX-CORTEX local Harness. The CLI
refuses missing source files. Never use synthetic data as a real evaluation.

Local baseline (inference, **only after** explicit consent):

```powershell
python -m hex_cortex.memory.cortex_memory_augmented_cli --project-root . --spine-file runtime/spine.jsonl --task-id baseline-001 --instruction "What is a Fibonacci recurrence?" --model qwen2.5:3b --approve-model --print-answer
```

To build an approved memory checkpoint from an earlier task:

```powershell
python -m hex_cortex.memory.verified_learning_cli --project-root . --spine-file runtime/spine.jsonl --task-id PRIOR_TASK_ID --query "Fibonacci" --approve-promotion --save-checkpoint runtime/checkpoint-001.jsonl --approve-persist
```

Local memory-augmented trial with the same model (read-only memory use):

```powershell
python -m hex_cortex.memory.cortex_memory_augmented_cli --project-root . --spine-file runtime/spine.jsonl --checkpoint runtime/checkpoint-001.jsonl --task-id augmented-001 --instruction "What is a Fibonacci recurrence?" --model qwen2.5:3b --approve-model --approve-memory-use --print-answer
```

**Important:** the baseline and cortex arms need a pre-registered independent
question set, true held-out tasks, identical model revision and decoding
settings, controlled arm order, and independent scoring. These two CLI calls
**alone are not a controlled paired experiment**. For actual scoring, use the
existing `hexcortex-amplification-eval` evidence protocol; it explicitly
refuses to certify causality from operator-supplied outputs.

The preceding Harness receipts deliberately do **not** store the user's raw
prompt or the model answer. Many replayed memories therefore contain only
hashes, status and operational observations, so they may convey **little or no
useful scientific knowledge to the Brain**. A genuinely useful memory requires
a separate verified, source-linked factual observation (not invented model
output) and an evaluated retrieval policy. A hash-chain proves data integrity,
not factual truth.

## Verification

```powershell
python -m pytest -q tests/test_cortex_memory_augmented_run.py tests/test_cortex_memory_augmented_cli.py
```

```powershell
python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
```
