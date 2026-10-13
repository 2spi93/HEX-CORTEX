# HEX-CORTEX — Verified Learning Loop V1 (local-first)

## Status and mission

This is a **real, opt-in integration** of existing components, not a new
model or an assertion of increased intelligence:

1. `CanonicalSpine` provides hash-chained task events.
2. `ReplayEngine` independently consolidates one task.
3. `MemoryPromoter` applies integrity, single-task provenance, content,
   sensitivity, confidence and duplicate guards.
4. `LocalKnowledgeIndex` stores approved compressed memory in RAM.
5. `RetrievalRouter` builds a bounded packet for the next task.
6. A checkpoint optionally records only task IDs, source event IDs and a
   content fingerprint. Restore **replays the original Spine** and repeats
   promotion checks into a new index. It never trusts serialized memory text.

Source: `src/hex_cortex/memory/verified_learning_loop.py`.
Entry point: `python -m hex_cortex.memory.verified_learning_cli`.

## Operator commands (Windows PowerShell, one line each)

The commands assume `runtime/spine.jsonl` **already exists**, saved from an
authorized local Harness session or CanonicalSpineJsonlStore. The CLI will
refuse a missing file and never generate fake evidence.

Inspection only (default: no memory changes):

```powershell
python -m hex_cortex.memory.verified_learning_cli --project-root . --spine-file runtime/spine.jsonl --task-id YOUR_TASK_ID --query "Fibonacci"
```

One approved, in-memory promotion and retrieval:

```powershell
python -m hex_cortex.memory.verified_learning_cli --project-root . --spine-file runtime/spine.jsonl --task-id YOUR_TASK_ID --query "Fibonacci" --approve-promotion
```

Promote and create a new local checkpoint, with **two separate approvals**:

```powershell
python -m hex_cortex.memory.verified_learning_cli --project-root . --spine-file runtime/spine.jsonl --task-id YOUR_TASK_ID --query "Fibonacci" --approve-promotion --save-checkpoint runtime/learning-001.jsonl --approve-persist
```

Reload the same Spine and checkpoint in a separate process, and search the
reconstructed index without promoting any new task:

```powershell
python -m hex_cortex.memory.verified_learning_cli --project-root . --spine-file runtime/spine.jsonl --restore-checkpoint runtime/learning-001.jsonl --query "Fibonacci"
```

`runtime/learning-001.jsonl` must not already exist; checkpoints are
immutable snapshots. Use a new filename for the next checkpoint, not an
overwrite. Do **not** commit local runtime Spine, checkpoints, secrets or
machine-specific receipts to Git.

## Security boundaries

- No cloud or local inference, GPU dependency, server or physical actuation.
- No automatic promotion. `approve_promotion` is separate from the
  `override_low_confidence` exception in the underlying promoter.
- `run_from_harness` accepts only a verified, completed receipt from the
  exact same Spine; it does not grant Harness tools or model permissions.
- Checkpoints are **not a backup of the Spine**. Preserve the original Spine
  separately and load it through `CanonicalSpineJsonlStore`.
- Fingerprints and a hash chain detect accidental changes within a chosen
  trust boundary; **they are not digital signatures**, and do not protect
  against an attacker able to rewrite all local files.
- Restore refuses a changed chain, mismatched event lineage or memory digest,
  blocked content, inadmissible outcome or duplicate tasks. Restore builds
  a fresh RAM index and exposes no partially restored index after failure.
- The checkpoint facility applies **only to replay-derived promotions made
  through this loop**. It does not serialize arbitrary preloaded index entries.
- Cross-process checkpoint revision, revocation propagation, indexed metadata
  schemas, hardware-level sandboxing and external attestation are not provided.
- On-disk checkpoint writes reuse existing exclusive writer and atomic JSONL
  snapshot utilities. Cooperating writers are protected; this is not a database.

## Verification

```powershell
python -m pytest -q tests/test_verified_learning_loop.py tests/test_verified_learning_cli.py
```

```powershell
python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
```

The offline tests demonstrate wiring, provenance gates, bounded retrieval and
restart restoration. **They do not demonstrate cognitive amplification**.
The next experiment must compare the *same* real model, same tasks and settings,
with versus without this circuit on held-out tasks, with external grading,
timing, cost and regression tracking (see
`MODEL_AMPLIFICATION_EVALUATION_V21.md`).
