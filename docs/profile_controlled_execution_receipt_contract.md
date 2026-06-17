# Profile Controlled Execution Receipt Contract

## Status

Opened as `PROFILE_CONTROLLED_EXECUTION_RECEIPT_V5_4`.

## Purpose

ControlledExecutionReceipt certifies the latest audited execution state. It does not execute skills. It records whether execution was prevented, staged but unobserved, successful, failed, or uncertified.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_receipt_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_receipt_cli .hex-cortex --summary --pretty
```

## Receipt file

```text
.hex-cortex/controlled-execution-receipt.jsonl
```

## Sources

```text
skill-execution-audit.jsonl
skill-outcome-feedback.jsonl
```

## Fields

```text
receipt_id
created_at
profile_path
source_audit_id
source_feedback_id
selected_skill
selected_action
receipt_status
receipt_decision
execution_allowed
execution_observed
execution_mode
observed_outcome
certification
next_action
reasons
```

## Receipt decisions

```text
receipt_blocked
receipt_not_executed
receipt_staged_unobserved
receipt_success
receipt_failure
```

## Rule

A receipt may certify success only when the audit allowed controlled staging and feedback observed success. Non-allowed audits must produce a non-executed receipt.

## Future path

```text
v5.5 registry update proposal gate
v5.6 feedback-weighted skill confidence report
v5.7 controlled execution receipt digest
```
