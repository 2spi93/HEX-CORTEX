# HEX-CORTEX — Cloud-first, local-ready (2026-10-10)

## Decision approved by the project owner

The owner's workstation cannot reliably run local LLMs. Do **not** block
HEX-CORTEX development, CI, feature completion or release gates on Ollama,
local LLM benchmarks, GPU/VRAM availability or model quality scores.

The project remains **local execution, no personal server**:

- HEX-CORTEX's control plane and files run on the Windows workstation.
- OpenAI and Anthropic are optional hosted *reasoning providers* through
  direct HTTPS APIs. This is not a HEX-CORTEX VPS deployment.
- The model selector is manual, one explicit provider/model per call; never
  present synthetic or unverified benchmark scores as evidence of best choice.
- Keep Ollama code for later, but it is **optional and not an acceptance gate**.
- Maintain strictly offline pytest, Ruff, mocked provider contracts and
  CanonicalSpine receipt verification in Windows and Linux CI.
- Never modify GTIXT/TXT repositories or share memories across projects.
- No automatic file writes, shell tools, provider fallback, network retries,
  benchmark scoring or background execution from cloud model outputs.

## First commands — no model, key or benchmark

PowerShell (Windows):

    git switch main
    git pull --ff-only origin main
    python -m pip install -e ".[dev]"
    python -m pytest
    ruff check .
    hexcortex-readiness --pretty

The readiness command checks explicit permissions, CanonicalSpine integrity,
a simulated Brain through CognitiveClock, and adapter contracts.
It uses the OS temporary directory only, **does not call Ollama, Claude
or OpenAI**, and never changes the checkout. `production_ready=false`
is intentional: this is architecture wiring evidence, not product
certification.

Preview planned cloud call without inference:

    hexcortex-harness --provider openai --model gpt-6.1-sol --dry-run
    hexcortex-harness --provider anthropic --model claude-sonnet-5 --dry-run

The model IDs are provider API examples, subject to account entitlements.
The official Anthropic model list identifies `claude-sonnet-5`, not the
requested name `Claude Sonnet 5.5` as a verified API identifier.
Always verify available model names in your provider account before actual use.

## Optional live calls — paid external APIs

OpenAI:

    hexcortex-harness --provider openai --model gpt-6.1-sol --approve-model --approve-cloud-send --instruction "Explain the HEX-CORTEX CognitiveClock design"

Anthropic:

    hexcortex-harness --provider anthropic --model claude-sonnet-5 --approve-model --approve-cloud-send --instruction "Explain the HEX-CORTEX CognitiveClock design"

For a live call you need an **API key** from the selected provider, supplied
to the running process through `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.
The adapters do not create an API account or grant model entitlements.
A ChatGPT/Claude subscription does not automatically supply API credits or
credentials. Cloud prompts leave the PC and provider costs may apply.

On Windows, enter secrets securely in the current PowerShell session rather
than embedding them in a script, commit or chat. Example for PowerShell 7+:

    $env:OPENAI_API_KEY = Read-Host "OpenAI API key" -MaskInput

PowerShell 5.1 operators should use a secret manager or another approved
environment-injection method; don't paste a literal key into a shell command
stored in history. Do not put keys into `.env` committed to Git.

A local API key is never written to receipts. However the instruction text
**is transmitted** to the provider after two explicit flags and, unless the
caller suppresses or handles it, the human-facing CLI prints the answer.
Do not send secrets, private source or GTIXT data in task instructions.

For calls in the HEX-CORTEX CLI, only fixed official API HTTPS URLs are
allowed. OpenAI uses Responses API with `store:false`. Anthropic uses
Messages API. Provider API data-handling rules remain independently
applicable; `store:false` does not create an unconditional privacy promise.

## Explicit release gates without local models

1. Architecture: CLI, Harness, CognitiveClock, CanonicalSpine,
   permission boundaries and provider adapters have deterministic tests.
2. Security: cloud send double-approval, bounded response/input/token/time,
   no secrets in receipts, no remote provider reached in CI.
3. Quality: Windows + Linux CI all green, including mock cloud providers,
   unauthorized tool denial, replay/tamper checks. No model benchmark gate.
4. Integration: manual live API smoke **only if the operator chooses** to
   connect a paid provider; unavailable keys do not block code completion.
5. Product: review remaining open issues #10-12, implement and validate
   real workload flows incrementally without implying synthetic tests
   certify production autonomy.
6. Acceptance: do not label an endpoint operational until actually tested
   against its real dependency, and do not label HEX-CORTEX fully complete
   while critical acceptance issues remain unresolved.

## Deferred rather than removed

- Local Ollama, GPU profiling, model comparative benchmarks.
- Automatic model selection using quality scores.
- Real-world multi-repository autonomous patch/test/merge flow.
- Fully interoperable MCP/A2A reference-client conformance.

Existing code remains intact; it is not required to pass the model-free
development gates.

## Provider references

- OpenAI Responses: https://platform.openai.com/docs/api-reference/responses
- Anthropic Messages: https://platform.claude.com/docs/en/api/messages/create
- Anthropic model availability: https://docs.anthropic.com/en/docs/about-claude/model-deprecations
