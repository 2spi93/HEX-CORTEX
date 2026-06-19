# Parallel Runtime, Research, and Federation v1

This package closes the three integration blocks that follow the HEX-CORTEX gateway and wiring audit.

## Invariants

- Windows prefers Ollama.
- Linux server prefers llama-server.
- Remote model endpoints are rejected by the local runtime selector.
- Network and model calls are opt-in.
- Hermes and HEX-CORTEX never merge memories.
- GTIXT remains read-only and keeps its own predictor, ledger, scores, and product truth.
- Secrets are represented by `secret_ref`; raw secret values are never written to JSONL receipts.
- Social write actions require explicit operator approval.
- Federation tasks use signed envelopes, bounded context references, and append-only receipts.

## Block A: runtime_model_orchestration_v1

Implemented in `cortex_runtime_model_orchestration.py`.

Capabilities:

- platform-aware descriptors;
- Ollama `/api/tags` and `/api/ps` probes;
- llama-server OpenAI-compatible `/v1/models` probe;
- model inventory normalization;
- loaded VRAM observation for Ollama;
- bounded benchmark receipts for latency and generated-token throughput;
- automatic fallback to the next healthy runtime;
- prompt and raw response non-persistence;
- runtime facts consumable by the wiring audit.

Commands:

```powershell
hexcortex runtime-auto --system Windows
hexcortex runtime-auto --system Windows --network
hexcortex runtime-auto --system Windows --network --benchmark --ollama-model qwen3:8b
```

```bash
hexcortex runtime-auto --system Linux --network
hexcortex runtime-auto --system Linux --network --benchmark --llama-model qwen3-8b.gguf
```

`wiring-auto` now merges the filesystem runtime probe into the wiring audit:

```bash
hexcortex wiring-auto --project-root .
```

This removes the old false diagnostic where `wiring` received an empty runtime-facts object even though `probe` had already detected MCP and project integrations.

## Block B: research_social_credentials_v1

Implemented in `cortex_research_social_credentials.py` and `deploy/research/`.

Capabilities:

- SearXNG and Crawl4AI local deployment profile;
- quality, freshness, and domain-diversity ranking;
- bounded citation packs with observed-content hashes;
- query and raw-page non-persistence;
- secret reference validation for environment, keyring, vault, Docker secret, and systemd credential stores;
- Telegram, LinkedIn, Instagram, and Reddit connection receipts;
- read-only first policy;
- explicit approval gate for write mode.

Start the local research services:

```bash
cd deploy/research
printf 'SEARXNG_SECRET=%s\n' "$(python -c 'import secrets; print(secrets.token_hex(32))')" > .env
docker compose up -d
```

Inspect the plan:

```bash
hexcortex research-plan
```

Prepare a provider receipt without reading the secret:

```bash
hexcortex provider-connection telegram keyring://hex-cortex/telegram/main
```

Write mode stays blocked unless `--operator-approved` is present.

## Block C: server_federation_audit_v1

Implemented in:

- `cortex_server_federation_audit.py`;
- `cortex_federation_queue.py`;
- `cortex_server_api.py`;
- `deploy/server/`.

Capabilities:

- localhost internal API;
- Caddy HTTPS reverse-proxy configuration;
- host-network Linux container profile keeping the API on `127.0.0.1`;
- optional Cloudflare Tunnel or Tailscale exposure at the host layer;
- Telegram webhook secret validation;
- HMAC-SHA256 signed task envelopes;
- append-only server-to-worker queue;
- worker claim and completion receipts;
- remote receipts with no raw payload or memory persistence;
- Hermes autodiscovery order: MCP, OpenAI-compatible `/v1/models`, declared Hermes API, bounded CLI stdio;
- GTIXT read-only capability audit.

Hermes exchange contract:

```text
signed task envelope
capability request
bounded context reference
result
receipt
```

Forbidden:

```text
memory merge
raw memory transfer
unbounded context transfer
implicit shell execution
```

GTIXT allowed capabilities:

```text
gtixt.health
gtixt.runtime_summary
gtixt.current_blockers
gtixt.latest_artifacts
gtixt.evidence_coverage
gtixt.open_tasks
gtixt.capability_map
```

Start the internal API on the Linux server:

```bash
cd deploy/server
export HEX_CORTEX_FEDERATION_SIGNING_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
docker compose up -d --build
```

Install Caddy on the host, set `HEX_CORTEX_DOMAIN`, then load `deploy/server/Caddyfile`. The API remains bound to localhost. A Cloudflare Tunnel or Tailscale service may target the Caddy HTTPS endpoint without exposing the Python service directly.

Inspect the federation contract:

```bash
hexcortex hermes-plan
hexcortex federation-audit --facts-json '{"internal_api_available":true,"https_reverse_proxy_available":true,"private_or_tunneled_transport_available":true,"server_worker_queue_available":true,"signed_task_envelopes_available":true,"remote_receipts_available":true,"hermes_autodiscovery_available":true,"gtixt_read_only_audit_available":true}'
```

## Validation

```bash
python -m pip install -e '.[dev]'
python -m pytest
ruff check .
```

The integration tests cover runtime preference and fallback, inventories, benchmark privacy, research ranking, citation packs, secret references, social approval gates, signed-envelope tamper detection, queue lifecycle, federation audit, remote receipts, and the new CLI commands.

## Next wave

After this package is validated and merged:

1. `media_runtime_v1`
2. `latent_world_model_lab_v1`
3. `world_model_training_evaluation_v1`

The next wave must consume the existing `CortexAdapter`, `runtime_facts`, `secret_ref`, gateway receipt, and surface audit contracts rather than create parallel state systems.
