# Bridges V1

Status: cold integration notes.

HEX-CORTEX should integrate with external agent systems through adapters, not through hard coupling.

## Target bridges

- Codex: repository work, AGENTS.md, tests, lint, branch-first development.
- Claude Code: repository work, CLAUDE.md, review, refactor, validation.
- Hermes-style math agent: formal or semi-formal reasoning workflow, especially when proof checking is useful.
- Hermes-style network agent: structured planning for network and systems reasoning.
- MCP-style tools: schema-first external tools with explicit boundaries.
- Ollama: local model runtime target.
- llama.cpp: local model runtime target.
- Mobile cockpit: approval, receipts, summaries, no heavy runtime.
- Hardware cockpit: local workstation, mini PC, GPU host, or lab device under operator approval.

## Adapter rule

Every bridge must be represented as a candidate adapter before activation.

Required fields:

- adapter_id,
- adapter_name,
- external_system,
- allowed_inputs,
- allowed_outputs,
- required_approval,
- allowed_actions,
- forbidden_actions,
- receipt_path,
- rollback_note.

## Activation ladder

1. static note,
2. candidate adapter receipt,
3. fixture test,
4. operator approval,
5. read-only run,
6. redacted receipt,
7. active preset.

No bridge may bypass tests, lint, receipts, or operator approval.
