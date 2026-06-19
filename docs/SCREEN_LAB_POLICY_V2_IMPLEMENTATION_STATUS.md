# SCREEN-LAB-POLICY-V2 implementation status

Branch: `screen-lab-policy-v2`

## Implemented

- balanced 320-transition deterministic corpus with no split-visible palette;
- action-discriminative transition training objective;
- strict held-out policy metrics required before promotion;
- dual local/open-weight and remote/API coding model routing contract;
- project MCP exposure for model catalog, routing, and bounded self-correction planning;
- Claude Code Windows installation helper;
- Hermes Agent Linux installation helper and minimal MCP configuration;
- signed-envelope Hermes executor adapter with separate memories;
- isolated worktree, patch-hash, and allowlisted-check executor;
- bounded self-correction candidate gates;
- append-only research hypothesis ledger and frontier projection;
- operational quickstart and tests for the new contracts.

## Runtime validation still required

- run the complete repository test and Ruff gates on Windows;
- generate and encode the v2 corpus using the cached DINOv2 model;
- train the first action-discriminative candidate;
- verify held-out top-1, margins, and promotion gate;
- install Claude Code from the official installer and approve the project MCP server;
- install/configure Hermes on the Linux server;
- connect a real local OpenAI-compatible coding model and an explicitly authorized remote API provider.

No v2 model, Hermes task, remote API call, worktree mutation, or merge has been performed by this branch implementation alone.
