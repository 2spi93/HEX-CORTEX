# Profile Operator Control Contract

## Canonical command

```powershell
hexctl .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Shell / CI command

```powershell
hexctl .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --strict-exit
```

## Development fallback

```powershell
python -m hex_cortex.memory.profile_control_cli .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Pipeline

```text
readiness snapshot refresh
→ readiness gate
→ operator status history append
→ compact operator control report
```

## Output contract

```json
{
  "control_type": "profile_operator_control",
  "status": "ready",
  "decision": "allow",
  "reason": "latest_snapshot_ready",
  "score": 1.0,
  "latest_snapshot_id": "readiness_...",
  "status_id": "opstatus_...",
  "history_count": 1,
  "history_path": ".hex-cortex\\profile-operator-status.jsonl"
}
```

## Decision contract

| decision | status | strict exit code |
|---|---|---:|
| allow | ready | 0 |
| watch | watch | 10 |
| block | blocked | 20 |

## Append-only files

```text
.hex-cortex/profile-readiness.jsonl
.hex-cortex/profile-operator-status.jsonl
```

## Rule

`hexctl` is the canonical operator entrypoint. Longer module names remain available for diagnostics, but human operation should use `hexctl`.
