# Profile Skill Feedback Score Contract

## Status

Opened as `PROFILE_SKILL_FEEDBACK_SCORE_V5_6`.

## Purpose

SkillFeedbackScore summarizes feedback outcomes for one selected skill into a non-mutating score report.

## Score file

```text
.hex-cortex/skill-feedback-score.jsonl
```

## Sources

```text
skill-outcome-feedback.jsonl
registry-learning-candidate.jsonl
```

## Fields

```text
score_id
created_at
profile_path
selected_skill
source_learning_id
feedback_count
success_count
failure_count
blocked_count
not_observed_count
base_score
feedback_score
final_score
score_status
score_decision
next_action
reasons
```

## Decisions

```text
score_ready
score_watch
score_hold
score_blocked
```

## Rule

A score may become ready only when the latest outcome is success and the weighted score is high enough. Non-observed outcomes stay on hold.
