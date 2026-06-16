# Profile Operator Command Index

## Canonical human command

```powershell
hexctl .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Canonical shell / CI command

```powershell
hexctl .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --strict-exit
```

## Development fallback

```powershell
python -m hex_cortex.memory.profile_control_cli .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Operator rule

Use `hexctl` for human operation.

Long diagnostic CLIs are implementation details. Do not expose them as primary operator commands in docs.

## Diagnostic-only modules

```text
profile_operator_control_cli
profile_operator_status_cli
profile_operator_status_refresh_cli
profile_operator_status_history_cli
profile_readiness_refresh_cli
profile_readiness_gate_cli
profile_readiness_snapshot_cli
```

These remain valid for debugging and tests, but the operator rail is frozen on `hexctl`.
