# Profile Receipt Summary Contract

## Status

Opened as `PROFILE_RECEIPT_SUMMARY_V5_7`.

## Purpose

ReceiptSummary aggregates controlled receipts into a compact non-mutating status summary.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_status_summary_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_status_summary_cli .hex-cortex --summary --pretty
```

## Summary file

```text
.hex-cortex/receipt-summary.jsonl
```

## Source

```text
controlled-execution-receipt.jsonl
```

## Decisions

```text
summary_ready
summary_watch
summary_blocked
```

## Rule

A summary becomes ready only when successful controlled receipt evidence exists. Prevented receipts remain watch-only.

## Future path

```text
v5.8 operator review packet
v5.9 operator review outcome
v6.0 skill registry review document
```
