# Profile Next Action Contract

## Question answered

```text
What should the local cortex do next?
```

## Canonical command

```powershell
hexnext .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Development fallback

```powershell
python -m hex_cortex.memory.profile_next_action_cli .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Dependency

`hexnext` uses the operator control rail as its source of truth.

```text
hexctl answers: is the local profile ready?
hexnext answers: what should the cortex do next?
```

## Output contract

```json
{
  "action_type": "profile_next_action",
  "status": "ready",
  "decision": "allow",
  "reason": "latest_snapshot_ready",
  "score": 1.0,
  "latest_snapshot_id": "readiness_...",
  "next_action": "run_cortex_pipeline",
  "next_reason": "profile_ready_for_cognitive_execution"
}
```

## Decision mapping

| decision | next_action |
|---|---|
| allow | run_cortex_pipeline |
| watch | review_profile_watch_reasons |
| block | repair_profile_readiness |
