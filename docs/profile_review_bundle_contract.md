# Profile Review Bundle Contract

## Status

Opened as `PROFILE_REVIEW_BUNDLE_V6_4`.

## Purpose

ReviewBundle groups the latest signature packet, review simulation, and review artifact into one verifiable local report.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_bundle_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_bundle_cli .hex-cortex --summary --pretty
```

## Bundle file

```text
.hex-cortex/review-audit-bundle.jsonl
```

## Sources

```text
registry-review-signature-packet.jsonl
registry-review-dry-run.jsonl
review-activation-artifact.jsonl
```

## Decisions

```text
bundle_ready
bundle_watch
bundle_blocked
```

## Rule

A bundle becomes ready only when all review sources are present and the latest artifact is ready. Watch artifacts keep the bundle in watch state.
