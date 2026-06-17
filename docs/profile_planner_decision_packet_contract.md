# Profile Planner Decision Packet Contract

## Status

Opened as `PROFILE_PLANNER_DECISION_PACKET_V4_8`.

## Purpose

PlannerDecisionPacket merges the latest latent state, skill registry match, and action cost into a final planning packet. It does not execute skills. It only decides whether a staged execution gate may be reached.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_planner_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_planner_cli .hex-cortex --summary --pretty
```

## Packet file

```text
.hex-cortex/planner-decision-packet.jsonl
```

## Sources

```text
latent-state.jsonl
skill-registry-match.jsonl
action-cost.jsonl
```

## Fields

```text
packet_id
created_at
profile_path
source_latent_id
source_match_id
source_cost_id
selected_skill
selected_action
planner_status
planner_decision
next_action
action_allowed
registry_status
match_score
action_score
compression_score
overall_confidence
reasons
```

## Planner decisions

```text
planner_ready
planner_watch
planner_blocked
```

## Rule

A planner packet is ready only when the registry match is active, confidence is high, and action cost is acceptable. A fallback registry match must remain watch-only until the skill is registered or activated.

## Future path

```text
v4.9 replay learning from planner packets
v5.0 controlled skill execution gate
v5.1 skill execution audit trail
```
