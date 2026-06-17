# Profile Skill Registry Review Document Contract

## Status

Opened as `PROFILE_SKILL_REGISTRY_REVIEW_DOCUMENT_V6_0`.

## Purpose

SkillRegistryReviewDocument builds a human-readable review document for one selected skill. It records evidence and the recommended operator decision. It does not apply changes to `skills.jsonl`.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_registry_review_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_registry_review_cli .hex-cortex --summary --pretty
```

## Document file

```text
.hex-cortex/skill-registry-review-document.jsonl
```

## Sources

```text
operator-review-outcome.jsonl
operator-review-packet.jsonl
skill-registry-match.jsonl
skill-feedback-score.jsonl
```

## Decisions

```text
document_ready
document_needs_registry_activation
document_deferred
document_rejected
document_blocked
```

## Rule

The document may recommend review, activation, deferral, or rejection. It only records the recommendation.

## Current watch-path expectation

```text
outcome_needs_registry_activation
→ document_needs_registry_activation
→ manual_activation_review
→ prepare_skill_activation_review
```

## Future path

```text
v6.1 registry review signature packet
v6.2 registry review dry run
v6.3 registry activation artifact
```
