# Profile Review Journal Contract

## Status

Opened as `PROFILE_REVIEW_JOURNAL_V6_5`.

## Purpose

ReviewJournal records a linked local review entry from the latest review bundle. It stores source linkage, previous hash, current hash, and the operator review scope.

## Canonical command

```powershell
python -m hex_cortex.memory.profile_ledger_cli .hex-cortex --pretty
```

## Summary command

```powershell
python -m hex_cortex.memory.profile_ledger_cli .hex-cortex --summary --pretty
```

## Source

```text
review-audit-bundle.jsonl
```

## Decisions

```text
ledger_ready
ledger_watch
ledger_blocked
```

## Rule

A record becomes ready only when the source bundle is ready and complete. Watch bundles create watch records with hashes and remain review-only.

## Current watch-path expectation

```text
bundle_watch
→ ledger_watch
→ prepare_skill_activation_review
```
