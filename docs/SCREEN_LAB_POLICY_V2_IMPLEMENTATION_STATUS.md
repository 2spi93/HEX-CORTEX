# SCREEN-LAB-POLICY-V2 implementation status

Branch: `screen-lab-policy-v2`
Pull request: `#8` (draft)

## Implemented

- balanced 320-transition deterministic corpus with no split-visible palette;
- action-discriminative transition training objective;
- strict held-out policy metrics required before promotion;
- dual local/open-weight and remote/API coding model routing contract;
- project MCP exposure for model catalog, routing, and bounded self-correction planning;
- canonical operational truth snapshot across code, runtimes, models, research, media, world model, security, and server evidence;
- operational MCP v1.1 used by Claude Code and Codex, with automatic localhost runtime facts when manual facts are omitted;
- `hexcortex-audit` CLI with optional live probes and receipt export;
- Claude Code Windows installation helper;
- Hermes Agent Linux installation helper and minimal MCP configuration;
- signed-envelope Hermes executor adapter with separate memories;
- isolated worktree, patch-hash, and allowlisted-check executor;
- bounded self-correction candidate gates;
- append-only research hypothesis ledger and frontier projection;
- SearXNG JSON format enabled and loopback limiter disabled for the private local stack;
- operational quickstart and tests for the new contracts.

## CI evidence

- standard CI: success on `8a27fc6`;
- HEX-CORTEX CI Evidence: success on `8a27fc6`;
- Ruff step: success;
- pytest step: success;
- PR remains draft pending local/runtime evidence.

## Runtime evidence already observed

- Claude Code installed, authenticated, and project MCP approved;
- Ollama and `qwen2.5-coder:7b` exercised through the local coding rail;
- DINOv2 frozen encoder exercised from the local cache;
- ComfyUI live probe reported healthy for `/system_stats`, `/queue`, and `/object_info` on `127.0.0.1:8188`.

These observations become canonical repository evidence only after running `hexcortex-audit --network --write-receipt ...` from the local checkout.

## Runtime validation still required before ready-for-review

- start the private SearXNG/Crawl4AI stack and retain one live citation audit receipt;
- train the first action-discriminative screen-lab-policy-v2 candidate;
- verify held-out top-1 accuracy, positive margins, and promotion gate, or retain a clean documented rejection;
- execute one complete isolated-worktree self-correction field cycle;
- execute one bounded remote API smoke test, or document its explicit deferral;
- certify n8n credential rotation and CI secret detection;
- inspect temporary branches and stash before cleanup;
- run the canonical operational audit after all local evidence exists.

No policy-v2 promotion, remote API call, self-correction merge, PR merge, or server deployment is performed merely by this implementation.
