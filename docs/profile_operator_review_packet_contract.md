# Profile Operator Review Packet Contract

## Status

Opened as `PROFILE_OPERATOR_REVIEW_PACKET_V5_8`.

## Purpose

OperatorReviewPacket merges the latest review gate, skill feedback score, and receipt summary into a final human-facing operator packet. It does not execute skills and does not mutate the skill registry.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_review_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_review_cli .hex-cortex --summary --pretty
```

## Review file

```text
.hex-cortex/operator-review-packet.jsonl
```

## Sources

```text
registry-update-proposal-gate.jsonl
skill-feedback-score.jsonl
receipt-summary.jsonl
```

## Decisions

```text
review_ready
review_watch
review_blocked
```

## Rule

Approval may be allowed only when the proposal gate, skill feedback score, and receipt summary are all ready. Hold and watch states remain review-only.

## Future path

```text
v5.9 operator review outcome
v6.0 skill registry review document
v6.1 registry review signature packet
```
