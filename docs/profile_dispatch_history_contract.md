# Profile Dispatch History Contract

## Question answered

```text
What dispatch actions actually happened?
```

## Append-only file

```text
.hex-cortex/profile-dispatch.jsonl
```

## Canonical summary command

```powershell
hexdispatch-history .hex-cortex --pretty
```

## Producing records

```powershell
hexdispatch .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

Each `hexdispatch` run appends one compact record to `profile-dispatch.jsonl`.

## Summary fields

```text
inspect_type
path
exists
total_dispatch_count
executed_count
skipped_count
latest_dispatch_id
latest_dispatch_status
latest_dispatch_reason
latest_next_action
latest_task_id
latest_pipeline_mode
latest_clock_completed
```

## Record rule

Dispatch history stores compact metadata only. Full pipeline outputs stay in the direct `hexdispatch` response and operational JSONL files.
