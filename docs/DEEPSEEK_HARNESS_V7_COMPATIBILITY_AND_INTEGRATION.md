# HEX-CORTEX + Official DeepSeek Harness (dsh) — V7 compatibility gateway

## Why reuse instead of rebuilding

The official MIT-licensed DeepSeek Harness is a separate Cordis-based plugin agent runtime (`deepseek-ai/deepseek-harness`). It already supplies an agent loop, code editing, shell, tools, session replay, plugins, model backends, optional MCP and a Web UI. HEX-CORTEX owns its canonical evidence, memory, clock, cells, visual perception and performance evaluation. Reuse established capabilities through **one adapter**; do not transplant two competing long-term memories, agent routers or permission stores.

Official resources reviewed: https://github.com/deepseek-ai/deepseek-harness ; https://github.com/deepseek-ai/deepseek-harness/tree/master/python/sdk ; https://github.com/deepseek-ai/deepseek-harness/blob/master/SAFETY.md ; https://github.com/ollama/ollama/blob/main/docs/integrations/deepseek-harness.mdx

**Upstream warning:** DSH is fast-changing developer-preview agent software, has not undergone a full security audit, and can run code, commands and plugins. Workspace-only configuration, prompts and sandbox flags are not independent OS-level confinement. Use a disposable Windows/Linux VM with separate credentials, no mounted real HEX repo and no accessible trading systems, phone, drones, camera or local secrets before running any agent.

## V7 implemented (be precise)

- The read-only compatibility module `cortex_deepseek_harness_bridge_v7.py` provides a mapping of candidate DSH capabilities against existing HEX subsystems and does not import, install, launch or call DSH.
- Detects only installed `deepseek-harness-sdk` distribution metadata via standard `importlib.metadata`; an installed SDK does not prove a working runtime, a configured model, or permission to execute tools.
- Creates a SHA256 digest of strictly server-derived HEX facts. Does not copy scene photos, code, chat conversations, credentials or external plugin data to DSH.
- Command Center V7 adds GET `/api/integrations/deepseek-harness` and a DeepSeek Harness read-only preflight screen, inheriting Host/Origin restrictions, CPU chat and V6 MobileSAM under opt-in.
- V7 does NOT merge the two runtimes, offer cross-agent execution or add an MCP gateway. The bridge is intentionally an audited compatibility and provenance layer before actual SDK-agent invocation.

## Controlled integration roadmap

1. Pin official DSH version and review `SAFETY.md`, Python SDK wheel, third-party notices and installed Cordis plugins; review dependency hashes and licenses.
2. In a **throwaway VM**, with NO mount of the main repo or secret files, provision independent `$DSH_HOME` and a copied small fixture repo; use a matching Python SDK version/runtime wheel. A matching runtime wheel exists for Windows x64 (see official docs).
3. Run one bounded agent task with the shipped SDK profile in the VM only. Verify no capabilities beyond the declared profile and explicit approval policy, and inspect created file/process/network effects. Do not assume `sdk-minimal` is safe just because of its name: it can include shell/file tools.
4. Build a fixed-schema adapter using the official Python `DeepSeekHarness` JSON-RPC API, but launch it only by the VM-side executor. Export a sanitized outcome/event manifest back to HEX, not executable instructions. Independent operator review required before any promotion to CanonicalSpine.
5. Wire through HEX policy: human-per-task approval, plugin allowlist, capped calls, output size and time budgets, resource receipts, kill switch, recoverable errors; no direct MCP tools to the chat by default.
6. Move features in parallel: coding sandbox, research with citations, skills and subagents, then project memory retrieval. Reuse DSH session/event tools rather than rewriting. Keep source identity and attribution across agents.
7. Scientific benchmark: same task suite Qwen/Ollama alone, DSH alone, HEX alone, HEX+DSH; measure task completion, verified errors, wall time, CPU/RAM, tool side effects, safety/permission violations and token/cost. Reject coupling if reliability or quality degrades.
8. Only after evidence: voice offline (Whisper/Piper), vision temporal tracking and World Model remain HEX-native; robot/drone/phone control needs authentic pairing, read-only telemetry first and hardware failsafe.

## Operator PowerShell — from existing HEX-CORTEX V6

Stop V6 Ctrl+C before switching. One command per line:

    git fetch origin
    git switch -c feature/command-center-v7-deepseek-harness-bridge --track origin/feature/command-center-v7-deepseek-harness-bridge
    $VP = "$env:LOCALAPPDATA\HEX-CORTEX\vision-v36\Scripts\python.exe"
    & $VP -m pytest -q tests/test_cortex_command_center_v6.py tests/test_cortex_command_center_v7.py
    & $VP -m ruff check .
    & $VP -m hex_cortex.memory.cortex_command_center_v7 --project-root . --port 8777 --enable-cpu-chat --enable-cpu-vision --dry-run
    & $VP -m hex_cortex.memory.cortex_command_center_v7 --project-root . --port 8777 --enable-cpu-chat --enable-cpu-vision

Visit http://127.0.0.1:8777/ then Ctrl+F5; click the DeepSeek Harness sidebar and inspect candidate vs connected. Route `http://127.0.0.1:8777/api/integrations/deepseek-harness` is metadata-only.

## Separate, isolated experimentation — not inside HEX-CORTEX repo

Ollama's official integration currently documents `ollama launch dsh --model qwen3.8` or `ollama launch dsh --config` and notes cloud-backed Web search may be enabled. Do NOT assume every locally installed Qwen model supports all agent tool protocols. In an isolated VM, choose the exact model/backend and review network access **before** enabling tools. Alternative: `npx @deepseek-ai/dsh web` launches an independent local Web UI, typically 127.0.0.1:3080; it is NOT automatically connected to HEX on port 8777. Never run `npx` in the real repository with broad workspace access just to test the integration.

## Release criteria

Keep PR draft until Windows/Ubuntu regression suites pass, all new buttons are functional, original V6 MobileSAM works and the external runtime pilot is isolated. The word 'connected' must not appear for capabilities that are merely discoverable or proposed. A real SDK demo inside a VM plus passing security gates is the first future milestone for claiming operational integration.
