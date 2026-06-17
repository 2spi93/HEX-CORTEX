# Profile Reasoning Trace Contract

## Status

Opened as `PROFILE_REASONING_TRACE_V4`.

## Design rule

The trace is public and compact. It does not store private chain-of-thought. It stores operator-facing steps that can be tested, replayed, summarized, and audited.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_steps_cli .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_steps_cli .hex-cortex --summary --pretty
```

## Trace file

```text
.hex-cortex/cognitive-trace.jsonl
```

## Step sequence v4.0

```text
readiness
next_action
safety
dispatch
cycle
```

## Record fields

```text
trace_id
created_at
profile_path
source_type
status
decision
final_action
final_reason
steps
```

## Step fields

```text
index
label
observation
decision
confidence
```

## Purpose

ReasoningTrace v4.0 converts the operator cycle into a compact multi-step public trace. Future versions may add world-state candidates, skill scoring, result evaluation, and improvement candidates.
