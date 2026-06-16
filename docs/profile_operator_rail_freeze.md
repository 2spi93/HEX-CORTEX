# Profile Operator Rail Freeze

## Status

Frozen as `PROFILE_OPERATOR_RAIL_V2`.

## Canonical human entrypoint

```powershell
python -m hex_cortex.memory.profile_control_cli .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Canonical shell / CI entrypoint

```powershell
python -m hex_cortex.memory.profile_control_cli .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --strict-exit
```

## Contract

```text
refresh readiness snapshot
→ evaluate readiness gate
→ append operator status history
→ return compact operator control report
```

## Canonical output fields

```text
control_type
profile_path
status
decision
reason
score
latest_snapshot_id
status_id
history_count
history_path
```

## Strict exit codes

```text
allow -> 0
watch -> 10
block -> 20
```

## Append-only traces

```text
.hex-cortex/profile-readiness.jsonl
.hex-cortex/profile-operator-status.jsonl
```

## Frozen rule

Long diagnostic CLIs remain available, but operator execution should use `profile_control_cli`.
