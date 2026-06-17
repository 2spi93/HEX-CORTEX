# Profile Controlled Skill Gate Contract

## Status

Opened as `PROFILE_CONTROLLED_SKILL_GATE_V5_0`.

## Purpose

ControlledSkillGate checks whether a planner decision may reach controlled staging. It does not execute skills. It only decides whether a later audited execution trail may be staged.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_stage_report_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_stage_report_cli .hex-cortex --summary --pretty
```

## Gate file

```text
.hex-cortex/controlled-skill-gate.jsonl
```

## Sources

```text
planner-decision-packet.jsonl
planner-replay-learning.jsonl
```

## Fields

```text
gate_id
created_at
profile_path
source_packet_id
source_replay_id
selected_skill
selected_action
gate_status
gate_decision
execution_allowed
execution_mode
next_action
planner_decision
replay_recommendation
gate_confidence
reasons
```

## Gate decisions

```text
gate_ready
gate_watch
gate_blocked
```

## Rule

A skill may reach controlled staging only when the planner packet is ready, the planner allows the action, and planner replay recommends staging the controlled skill gate. Watch and fallback states must not allow execution.

## Future path

```text
v5.1 skill execution audit trail
v5.2 skill outcome feedback
v5.3 replay-weighted registry promotion
```
