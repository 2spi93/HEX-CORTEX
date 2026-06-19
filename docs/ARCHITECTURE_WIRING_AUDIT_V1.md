# HEX-CORTEX Architecture Wiring Audit V1

Audit scope: architecture built from the beginning of the local model, agent, multimodal, world-model, action, routing, receipt, and integration work.

## Readiness vocabulary

- **Contract ready**: interfaces, guards, receipts, tests, and registry wiring exist.
- **Usable**: an operator can invoke the feature through the Python API or CLI.
- **Native ready**: the intended host transport or concrete runtime adapter is configured.
- **Operational**: the external runtime is available and the complete path has been exercised.

## Current matrix

| Area | Contract | Usable | Native/runtime status |
|---|---|---|---|
| Agent instructions and repository doctrine | Ready | Ready | `AGENTS.md` and `CLAUDE.md` present |
| Expert-domain candidates and progression doctrine | Ready | Ready | Evidence-based promotion still required |
| Local model contract and advisory receipts | Ready | Ready | Real runtime must be running |
| Ollama localhost adapter | Ready | Ready | Endpoint must be configured and running |
| OpenAI-compatible local adapter | Ready | Ready | llama.cpp-compatible endpoint must be running |
| Web research with mandatory citations | Ready | Injectable | Concrete search engine handler not configured globally |
| Multimodal sensor/provider contracts | Ready | Ready | Physical providers still environment-specific |
| Text, image, video, audio, and 3D encoder receipts | Ready | Ready | Actual encoder models remain external adapters |
| Image, video, and 3D generation receipts | Ready | Ready | Actual generation engines remain external adapters |
| Social channel and account receipts | Ready | Ready | Live API handlers and credentials remain unconfigured |
| State, transition, surprise, temporal memory | Ready | Ready | Deterministic V1, not a trained latent model |
| Goal, cost, action proposal, selection, and routing | Ready | Ready | Complete through the adapter-receipt boundary |
| Adapter execution gateway | Ready | Ready | Concrete adapter handlers are runtime-specific |
| Claude Code integration | Ready | Ready | Project MCP config included; project approval required |
| Codex integration | Ready | Ready | Project MCP config included; trusted project required |
| MCP stdio diagnostics | Ready | Ready | Read-only by design in V1 |
| Kali Linux | Ready | CLI usable | Kali-specific profile and tool adapters remain optional |
| Generic server/container | Ready | CLI usable | Long-running service packaging not implemented |
| Hardware/edge | Ready | Factory usable | Concrete device handler not configured |
| GTIXT or another project | Ready | Factory usable | Concrete project handler not configured |
| Hermes Agent | Candidate | Not native | Dedicated adapter still required |
| Stability and repair suggestions | Ready | Ready | Automated model retraining is not implemented |
| Learned multimodal world model | Architecture prepared | Not trained | Training/evaluation pipeline remains future work |

## Static wiring result

The unified bundle contains the complete deterministic chain:

`local target -> advisory shape -> runner receipt -> providers -> observation -> state -> transition -> surprise -> temporal sequence -> goal/cost -> action proposal -> action selection -> route -> adapter receipt -> execution gateway`

Registry combination fails closed on duplicate unit names. Route auditing fails if any route points to a missing receipt unit.

## Native developer-tool integration

The repository contains:

- `.mcp.json` for Claude Code project scope,
- `.codex/config.toml` for Codex project scope,
- `hexcortex` CLI entry point,
- `hexcortex-mcp` stdio server entry point,
- a read-only MCP tool catalog for units, wiring, surfaces, manifests, runtime facts, and read-plan diagnostics.

The MCP server does not expose the execution gateway in V1.

## Portable host adapters

Factories now exist for:

- project handlers such as GTIXT,
- network services,
- hardware devices,
- cited web research,
- Ollama localhost,
- local OpenAI-compatible servers.

Factories register capabilities only. The embedding environment supplies the handler and the gateway applies permissions, policy, lane matching, secret redaction, idempotency, and result receipts.

## Remaining runtime blocks

1. Configure and run the selected local model endpoint.
2. Inject a concrete cited search engine handler.
3. Implement a GTIXT-specific project handler and allowed operation schema.
4. Package a long-running service transport if remote/server-native access is required.
5. Configure concrete media, sensor, social, and hardware handlers.
6. Add a Hermes-specific adapter if Hermes is selected.
7. Build the learned multimodal world-model training and evaluation pipeline.
8. Expose controlled execution tools over MCP only after read-only MCP validation and host approval UX are proven.

## Verification commands

```text
python -m pytest
ruff check .
python -m hex_cortex.memory.cortex_cli units
python -m hex_cortex.memory.cortex_cli wiring
python -m hex_cortex.memory.cortex_cli probe
python -m hex_cortex.memory.cortex_cli surface-auto claude_code
python -m hex_cortex.memory.cortex_cli surface-auto codex_cli
```

After editable installation, the equivalent commands are:

```text
hexcortex units
hexcortex wiring
hexcortex probe
hexcortex surface-auto claude_code
hexcortex-mcp
```
