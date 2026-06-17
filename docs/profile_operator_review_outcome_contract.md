# Profile Operator Review Outcome Contract

## Status

Opened as `PROFILE_OPERATOR_REVIEW_OUTCOME_V5_9`.

## Purpose

OperatorReviewOutcome records the final human-facing outcome for an operator review packet. It does not execute skills and does not mutate the skill registry.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_review_outcome_cli .hex-cortex --pretty
```

## Explicit outcome command

```powershell
python -m hex_cortex.memory.profile_review_outcome_cli .hex-cortex --outcome deferred --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_review_outcome_cli .hex-cortex --summary --pretty
```

## Outcome file

```text
.hex-cortex/operator-review-outcome.jsonl
```

## Source

```text
operator-review-packet.jsonl
```

## Allowed outcomes

```text
auto
approved
rejected
deferred
needs_registry_activation
```

## Decisions

```text
outcome_approved
outcome_rejected
outcome_deferred
outcome_needs_registry_activation
outcome_blocked
```

## Rule

Approval may only be recorded as allowed when the source operator review packet already allows approval. Watch states default to deferred or needs-registry-activation outcomes.

## Future path

```text
v6.0 skill registry review document
v6.1 registry review signature packet
v6.2 controlled registry mutation dry-run
```
