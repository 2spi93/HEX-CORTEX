# Profile Skill Outcome Feedback Contract

## Status

Opened as `PROFILE_SKILL_OUTCOME_FEEDBACK_V5_2`.

## Purpose

SkillOutcomeFeedback records outcome feedback from the latest skill execution audit. It does not execute skills. It prepares future learning from success, failure, blocked, regression, or not-observed outcomes.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_feedback_cli .hex-cortex --pretty
```

## Outcome command

```powershell
python -m hex_cortex.memory.profile_feedback_cli .hex-cortex --outcome success --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_feedback_cli .hex-cortex --summary --pretty
```

## Feedback file

```text
.hex-cortex/skill-outcome-feedback.jsonl
```

## Source

```text
skill-execution-audit.jsonl
```

## Outcomes

```text
not_observed
blocked
success
failure
regression
```

## Rule

Feedback may only promote future confidence when the audit allowed controlled staging and the observed outcome is success. Watch and blocked audit states remain non-executing feedback.

## Future path

```text
v5.3 replay-weighted registry promotion
v5.4 controlled execution receipt
v5.5 registry mutation proposal gate
```
