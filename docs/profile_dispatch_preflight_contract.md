# Profile Dispatch Preflight Contract

## Question answered

```text
Would dispatch be allowed right now?
```

## Canonical command

```powershell
hexpreflight .hex-cortex --policy-limit 6 --policy-stability-window 3 --minimum-ready-score 1.0 --pretty
```

## Output contract

```json
{
  "inspect_type": "profile_dispatch_preflight",
  "status": "ready",
  "decision": "allow",
  "next_action": "run_cortex_pipeline",
  "safety_status": "allow",
  "allowed": true,
  "safety_reasons": []
}
```
