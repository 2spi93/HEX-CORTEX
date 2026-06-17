# Profile Registry Learning Candidate Contract

## Status

Opened as `PROFILE_REGISTRY_LEARNING_CANDIDATE_V5_3`.

## Purpose

RegistryLearningCandidate summarizes skill outcome feedback and registry match state into a non-mutating registry learning proposal. It does not modify `skills.jsonl`.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_registry_learning_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_registry_learning_cli .hex-cortex --summary --pretty
```

## Learning file

```text
.hex-cortex/registry-learning-candidate.jsonl
```

## Sources

```text
skill-outcome-feedback.jsonl
skill-registry-match.jsonl
```

## Fields

```text
learning_id
created_at
profile_path
selected_skill
source_feedback_id
source_match_id
registry_status
observed_outcome
success_count
failure_count
blocked_count
not_observed_count
learning_score
learning_status
learning_decision
next_action
reasons
```

## Decisions

```text
learning_ready
learning_watch
learning_hold
learning_blocked
```

## Rule

Registry learning may become ready only from successful outcome feedback. Non-observed, blocked, failure, and regression outcomes must hold or block registry learning.

## Future path

```text
v5.4 controlled execution receipt
v5.5 registry mutation proposal gate
v5.6 feedback-weighted skill confidence report
```
