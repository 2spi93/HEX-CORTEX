# Profile Planner Replay Learning Contract

## Status

Opened as `PROFILE_PLANNER_REPLAY_LEARNING_V4_9`.

## Purpose

PlannerReplayLearning summarizes planner decision packets over time. It does not execute skills. It learns from planner outcomes and recommends the next structural repair or gate.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_learning_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_learning_cli .hex-cortex --summary --pretty
```

## Learning file

```text
.hex-cortex/planner-replay-learning.jsonl
```

## Source

```text
planner-decision-packet.jsonl
```

## Fields

```text
replay_id
created_at
profile_path
packet_count
ready_count
watch_count
blocked_count
fallback_count
dominant_status
missing_skills
repeated_next_actions
latest_planner_decision
latest_next_action
replay_recommendation
replay_score
reasons
```

## Recommendations

```text
build_planner_decision_packet
register_or_activate_missing_skills
stage_controlled_skill_execution_gate
repair_blocking_planner_inputs
continue_planner_observation
```

## Rule

Fallback planner packets should recommend registering or activating missing skills. Ready packets should recommend staging the controlled skill execution gate.

## Future path

```text
v5.0 controlled skill execution gate
v5.1 skill execution audit trail
v5.2 replay-weighted skill registry promotion
```
