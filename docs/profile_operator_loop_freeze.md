# Profile Operator Loop Freeze

## Status

Frozen as `PROFILE_OPERATOR_LOOP_V3`.

## Canonical sequence

```text
hexctl
→ hexnext
→ hexpreflight
→ hexdispatch
→ hexdispatch-history
→ profile_dispatch_plan_cli
→ profile_run_cli
```

## One-command module

```powershell
python -m hex_cortex.memory.profile_run_cli .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Output rule

A profile run returns one compact operator cycle payload:

```text
cycle_type
status
decision
next_action
safety_status
dispatch_status
cycle_status
cycle_reason
cycle_id
cycle_trace_count
cycle_trace_path
plan_action
plan_command
```

## Trace files

```text
.hex-cortex/profile-dispatch.jsonl
.hex-cortex/profile-cycle.jsonl
```

## Freeze rule

The local operator loop is complete when the system can check readiness, choose the next action, inspect safety, dispatch when allowed, trace results, and return a plan when dispatch is not allowed.
