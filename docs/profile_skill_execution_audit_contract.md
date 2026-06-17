# Profile Skill Execution Audit Contract

## Status

Opened as `PROFILE_SKILL_EXECUTION_AUDIT_V5_1`.

## Purpose

SkillExecutionAuditTrail records a pre-execution audit trail from the controlled skill gate. It does not execute skills. It only records whether controlled staging is audit-ready, watch-only, or blocked.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_audit_report_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_audit_report_cli .hex-cortex --summary --pretty
```

## Audit file

```text
.hex-cortex/skill-execution-audit.jsonl
```

## Source

```text
controlled-skill-gate.jsonl
```

## Fields

```text
audit_id
created_at
profile_path
source_gate_id
selected_skill
selected_action
audit_status
audit_decision
execution_allowed
execution_mode
audit_stage
next_action
gate_decision
gate_confidence
reasons
```

## Audit decisions

```text
audit_ready
audit_watch
audit_blocked
```

## Rule

The audit trail may report readiness only when the controlled skill gate allows controlled staging. Watch and blocked gate states must never allow execution.

## Future path

```text
v5.2 skill outcome feedback
v5.3 replay-weighted registry promotion
v5.4 controlled execution receipt
```
