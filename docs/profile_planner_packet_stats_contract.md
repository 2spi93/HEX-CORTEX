# Profile Planner Packet Stats Contract

## Status

Opened as `PROFILE_PLANNER_PACKET_STATS_V4_9`.

## Purpose

PlannerPacketStats aggregates planner decision packets into a compact operational report. It does not execute skills. It identifies repeated fallback states, missing skills, dominant planner status, and recommended next action.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_stats_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_stats_cli .hex-cortex --summary --pretty
```

## Stats file

```text
.hex-cortex/planner-packet-stats.jsonl
```

## Source

```text
.hex-cortex/planner-decision-packet.jsonl
```

## Fields

```text
profile_path
source_packet_count
dominant_status
dominant_next_action
missing_skills
packet_score
recommended_action
```

## Current expected behavior

With a fallback planner packet for `operator_watch_review`, v4.9 should recommend:

```text
register_or_activate_missing_skills
```

## Future path

```text
v5.0 controlled skill gate
v5.1 skill execution audit trail
v5.2 skill outcome replay stats
```
