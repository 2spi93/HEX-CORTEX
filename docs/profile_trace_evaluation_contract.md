# Profile Trace Evaluation Contract

## Status

Opened as `PROFILE_TRACE_EVALUATION_V4_1`.

## Purpose

TraceEvaluation scores public cognitive traces. It does not evaluate private chain-of-thought. It evaluates compact operator-facing traces.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_score_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_score_cli .hex-cortex --summary --pretty
```

## Evaluation file

```text
.hex-cortex/cognitive-trace-evaluation.jsonl
```

## Scores

```text
coherence_score
safety_score
completeness_score
actionability_score
overall_score
```

## Verdicts

```text
trace_valid
trace_watch
trace_blocked
trace_missing
```

## Rule

A trace is valid when the expected public step sequence is present, the safety step is interpretable, the final action is actionable, and the overall score is high.
