# Profile Review Simulation Contract

## Status

Opened as `PROFILE_REVIEW_SIMULATION_V6_2`.

## Purpose

ReviewSimulation records a report from the latest review signature packet. It writes only a local report and keeps the operator in control.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_dry_run_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_dry_run_cli .hex-cortex --summary --pretty
```

## Report file

```text
.hex-cortex/registry-review-dry-run.jsonl
```

## Sources

```text
registry-review-signature-packet.jsonl
skill-registry-review-document.jsonl
```

## Decisions

```text
dry_run_ready
dry_run_watch
dry_run_blocked
```

## Rule

The report may become ready only when the signature packet is signed and allowed. A needs-more-evidence signature stays watch-only.

## Current watch-path expectation

```text
signature_needs_more_evidence
→ dry_run_watch
→ prepare_skill_activation_review
```
