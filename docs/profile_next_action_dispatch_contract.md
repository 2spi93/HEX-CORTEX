# Profile Next Action Dispatch Contract

## Question answered

```text
Can the next cognitive action be executed now?
```

## Canonical command

```powershell
hexdispatch .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Behavior

```text
hexctl answers: is the local profile ready?
hexnext answers: what should the cortex do next?
hexdispatch answers: execute the next action only if the dispatch safety gate allows it.
```

## Dispatch safety gate

Execution is allowed only when all conditions are true:

```text
status == ready
decision == allow
next_action == run_cortex_pipeline
latest_snapshot_id is present
```

If one condition fails, `hexdispatch` returns `dispatch_status=skipped` and records the safety reason.

## Dispatch mapping

| next_action | dispatch behavior |
|---|---|
| run_cortex_pipeline | execute CortexPipeline and persist spine/memory results |
| review_profile_watch_reasons | skip execution and return watch reason |
| repair_profile_readiness | skip execution and return repair reason |

## Output contract

```json
{
  "dispatch_type": "profile_next_action_dispatch",
  "status": "ready",
  "decision": "allow",
  "next_action": "run_cortex_pipeline",
  "safety_status": "allow",
  "safety_reasons": [],
  "dispatch_status": "executed",
  "dispatch_reason": "cortex_pipeline_executed",
  "pipeline_result": {}
}
```
