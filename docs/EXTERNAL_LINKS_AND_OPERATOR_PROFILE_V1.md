# External Links And Operator Profile V1

Status: cold implementation notes.

## Candidate links

The code uses neutral IDs, but the intended mapping is:

- `formal_math_link`: Hermes-style formal/math agent candidate.
- `repo_coding_link_a`: Codex-style repository coding agent candidate.
- `repo_coding_link_b`: Claude-Code-style repository review/refactor candidate.
- `tool_protocol_link`: MCP-style schema-first tool protocol candidate.

Every link remains candidate-only until tests, receipts, permissions, and operator approval exist.

## Operator profile

`preferences.profile` captures the current working preference:

- French responses,
- fast branch-first execution,
- pytest + ruff validation,
- fast-forward-only merge,
- auto-safe only when trusted,
- receipts first,
- no hidden execution.

## Purpose

This makes the auto plan more personalized without relying on vague memory.

The profile can feed trusted-plan scoring while staying explicit, testable, and auditable.
