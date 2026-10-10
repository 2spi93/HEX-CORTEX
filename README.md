# HEX-CORTEX

> **Repository recovery notice (2026-10-09).** This README contains historical v0.1
> foundation descriptions. The current source and CLI entry points have evolved
> substantially beyond that baseline. Read
> [Recovery Audit](docs/RECOVERY_AUDIT_2026_10.md) and
> [Harness V2 Architecture](docs/HARNESS_V2_ARCHITECTURE.md) first.
>
> Recovery was merged to main; the next local-only Harness V2 implementation is
> documented in [Local Operator Manual](docs/LOCAL_HARNESS_V2_OPERATOR.md).
> No remote infrastructure is in scope, and a passing CI is not live-model certification.

## Cloud-first development policy (2026-10-10)

**A local LLM is no longer required to develop, test or validate the
architecture.** Keep the existing Ollama integrations for later, but do not
block development or CI on machine learning benchmarks or GPU/VRAM.
`hexcortex-readiness --pretty` validates model-free wiring; `hexcortex-harness`
can explicitly use hosted OpenAI/Anthropic APIs after separate model and
cloud-transmission approvals. No personal server is deployed.

See [Cloud-first / no-benchmark V5](docs/CLOUD_FIRST_NO_BENCHMARK_V5.md).
A green CI or offline readiness check does not certify real cloud API access
or end-to-end autonomous coding.

## Universal Cognitive Exoskeleton — project mission (V12)

HEX-CORTEX is **not a coding-only agent**. The owner's original North Star
is a model-independent cognitive exoskeleton (Tony Stark's armor metaphor)
for universal scientific knowledge, mathematics, physics, molecular chemistry,
biology, engineering and embodied interfaces to applications, devices,
robots and drones. Coding is the *first validated engineering test ground*.

The [universal mission and embodiment contract](docs/UNIVERSAL_CORTEX_NORTH_STAR_V12.md)
sets up fail-closed domain/target schemas and a science-evidence ledger
without pretending mathematical solvers, chemistry experts or drone pilots
have already been installed. **No direct physical actuation in this release**;
all physical control is deferred to real independently enforced safety gates.

## Current operational entry points

```text
hexcortex            inspect units, wiring and runtime probes
hexcortex-mcp        dual-era read-only MCP stdio (legacy + 2026-07-28)
hexcortex-doctor     audit local checkout; default expected branch main
hexcortex-benchmark  run bounded localhost Ollama smoke benchmarks
hexcortex-skills     export active SkillRecord JSONL to portable SKILL.md
hexcortex-harness    bounded local tool/brain execution with consent and receipts
hexcortex-readiness  offline architecture smoke; no LLM, cloud keys or benchmarks
hexcortex-benchmark-v2  machine-bound heldout Ollama fingerprints
hexcortex-repo-eval  local no-exec multi-file repair probe (experimental)
hexcortex-a2a-local   local A2A-compatible JSONL subset
hexcortex-code       gated coding and worktree actions
hexcortex-agent      model routing and bounded agent plans
```

`hexcortex-skills .hex-cortex/skills.jsonl exported-skills/` exports
instructions; it does not install, trust, activate or execute skills.
Use `hexcortex-doctor --expected-branch main` on main; override this when
validating an isolated feature branch.

**Repository coding evaluation:** the V3 offline evaluator analyzes four
synthetic Python repair snapshots (including two-file fixes) through an
allowlisted AST interpreter; generated source is never executed and no
checkout is altered. [Operator manual](docs/REPO_REPAIR_PROBE_V3.md).
Scores are research-only and are not trusted routing priors.

**Local Critic V4:** the repo evaluation CLI now fails fast on unknown Ollama
models, resolves real local model metadata by default, and distinguishes
failed model calls from rejected patches. An independent static critic can
optionally verify approved AST-safe candidates with tests in a tightly
restricted **local Docker Linux container** via `--approve-docker`. It is
disabled by default, mounts no checkout, and never grants modification rights.
See [Local Critic and Sandbox V4](docs/LOCAL_CRITIC_SANDBOX_V4.md).

**Readiness terminology:** code present, tested, configured, operational
and deployed are separate states. See the audit for detailed limitations.


**Cellular World Model Intelligence**

HEX-CORTEX is an experimental AI architecture designed around small specialized cells, sparse activation, a global cognitive workspace, local-first memory retrieval, memory compression, procedural skill memory, replay consolidation, sleep replay batches, conservative pruning, a persistent canonical spine, persistent local memory, memory index hydration, skill index hydration, controlled self-improvement, a bounded cognitive clock, a health-aware cell registry, a local cortex pipeline, and a JEPA-inspired world-model layer.

The goal is not to build one oversized model. The goal is to build a modular cognitive system where intelligence emerges from health-aware routing, bounded execution, memory compression, memory hydration, skill hydration, replay consolidation, skill reuse, conservative pruning, prediction, criticism, lineage, controlled self-improvement, and controlled action.

## Core thesis

```text
intelligence = specialized cells
             + health-aware cell registry
             + fast routing
             + bounded cognitive clock
             + sparse activation
             + global workspace
             + index-first memory
             + procedural skill memory
             + persistent canonical lineage
             + persistent local memory
             + memory index hydration
             + skill index hydration
             + replay consolidation
             + sleep replay batches
             + conservative pruning
             + controlled self-improvement
             + predictive world model
             + critic / immune system
             + memory replay
```

## Architecture principles

1. **Local-first**: prototype locally before deploying anything to a shared server.
2. **Small cells, strong contracts**: every cell has explicit input/output schemas.
3. **Health-aware cells**: cell trust, failures, double-check flags, and quarantine are first-class signals.
4. **Sparse activation**: never activate the whole cortex when a small circuit is enough.
5. **Fast / working / deep thinking**: cognitive depth depends on uncertainty, novelty, risk, and cost.
6. **Bounded ticks**: every reasoning loop has max ticks, max latency, and failure rules.
7. **Index-first memory**: never inject long context before searching a compact index.
8. **Procedural skill memory**: validated workflows become reusable skills.
9. **No cognition without lineage**: every decision should be traceable to task, cells, workspace state, and confidence.
10. **Memory is compressed experience**: raw logs are not intelligence; replayable compressed patterns are.
11. **Replay before trust**: canonical events are replayed into compact episode memory before reuse.
12. **Prune noise conservatively**: weak artifacts are degraded or archived by decision, not deleted from history.
13. **Self-improvement is gated**: hypotheses must be evaluated, scored, and rollback-safe before promotion.
14. **Criticism is native**: every high-impact answer must pass through a critic or immune gate.

## Cognitive loop

```text
input
→ local cortex pipeline
→ cognitive clock start
→ canonical spine event
→ persisted memory hydration
→ persisted skill hydration
→ local knowledge index
→ retrieval router
→ bounded context packet
→ skill library lookup
→ health-aware cell registry
→ thalamic routing
→ sparse cell activation
→ global workspace
→ world model prediction
→ critic / immune check
→ action
→ memory compression
→ replay consolidation
→ local memory persistence
→ sleep replay batch
→ pruning decision
→ self-improvement candidate
→ cognitive clock completion
```

## Memory / retrieval law

```text
Index first.
Lexical search first.
Semantic fallback only when needed.
Small context packet always.
Compress after use.
Persist compressed memories when requested.
Hydrate visible memories before retrieval.
```

## Canonical spine law

```text
Append events.
Never rewrite cognition.
Verify hash chain.
Persist as JSONL when requested.
Project state from events.
Replay before trusting memory.
```

## Self-improvement law

```text
Observe.
Compress.
Hypothesize.
Evaluate.
Reject or promote.
Never self-modify without rollback.
```

## Cognitive clock law

```text
Start tick.
Run bounded handler.
Capture success or failure.
Append lifecycle events.
Stop on required failure.
Never loop forever.
```

## Cell registry law

```text
Register cells explicitly.
Apply runtime health before routing.
Degrade trust after failures.
Quarantine unstable cells.
Never route through quarantined cells.
```

## Router law

```text
Build bounded budget from task pressure.
Ask the registry for available cells.
Score only health-adjusted cells.
Select sparse active cells.
Reject routing if no healthy cell exists.
```

## Skill library law

```text
Store validated workflows as skills.
Bootstrap skills through the CLI.
Search skills by trigger tags.
Hydrate active persisted skills before matching.
Activate only reusable skills.
Degrade weak skills after failures.
Archive skills that stop working.
Never execute arbitrary skill code in v0.1.
```

## Replay law

```text
Verify spine integrity first.
Replay canonical task events.
Extract episode summary.
Compress into reusable memory.
Refuse consolidation if lineage is broken.
```

## Sleep replay law

```text
Collect task ids.
Replay each task.
Count consolidated / empty / failed reports.
Expose consolidated memories.
Do not execute skills during batch replay.
```

## Pruning law

```text
Emit pruning decisions only.
Keep protected memories.
Degrade weak artifacts before archiving.
Quarantine unstable cells.
Never rewrite canonical history.
```

## Cortex pipeline law

```text
Receive task.
Retrieve bounded context.
Match procedural skills.
Route through healthy cells.
Run bounded clock ticks.
Replay into compressed memory.
Emit pruning decisions.
Keep every step traceable in the spine.
```

## Repository status

This repository starts with the foundation only:

- architecture notes
- environment strategy
- memory architecture
- self-improvement architecture
- Pydantic contracts
- local CLI entrypoint
- local inspect CLI
- local cortex pipeline
- health-aware thalamic router
- bounded cognitive clock
- health-aware cell registry
- procedural skill library
- persistent skill store
- skill bootstrap CLI
- replay engine
- sleep replay batch engine
- conservative pruning engine
- minimal global workspace
- local knowledge index
- memory index hydrator
- retrieval router
- deterministic memory compression spine
- persistent local memory store
- persistent append-only canonical spine
- deterministic evolution selector
- unit tests

No heavy model inference, GPU serving, vector database, autonomous code modification, arbitrary skill execution, destructive pruning, or training code is included in the initial version.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -e '.[dev]'
pytest
ruff check .
```

## Local CLI

Run one local pipeline pass and print stable JSON:

```bash
python -m hex_cortex.cli "Classify this local task" --domain intent --novelty 0.2 --risk 0.2 --uncertainty 0.2
```

Pretty-print JSON:

```bash
python -m hex_cortex.cli "Analyze this bounded task" --pretty
```

Bootstrap a reusable active skill:

```bash
python -m hex_cortex.cli --bootstrap-skill .hex-cortex/skills.jsonl --skill-name "memory workflow" --skill-trigger memory --skill-step hydrate --skill-step retrieve --pretty
```

Inspect local state without running a task:

```bash
python -m hex_cortex.cli --inspect-spine .hex-cortex/spine.jsonl --pretty
python -m hex_cortex.cli --inspect-memory .hex-cortex/memory.jsonl --pretty
python -m hex_cortex.cli --inspect-skills .hex-cortex/skills.jsonl --pretty
```

Persist canonical events between CLI runs:

```bash
python -m hex_cortex.cli "Persistent local task" --spine-jsonl .hex-cortex/spine.jsonl
```

Persist compressed memories between CLI runs:

```bash
python -m hex_cortex.cli "Memory task" --memory-jsonl .hex-cortex/memory.jsonl
```

Hydrate active persisted skills before matching:

```bash
python -m hex_cortex.cli "Use memory workflow" --domain memory --skills-jsonl .hex-cortex/skills.jsonl
```

Persist lineage and memories while hydrating skills:

```bash
python -m hex_cortex.cli "Durable task" --spine-jsonl .hex-cortex/spine.jsonl --memory-jsonl .hex-cortex/memory.jsonl --skills-jsonl .hex-cortex/skills.jsonl
```

When `--memory-jsonl` is provided, visible persisted memories are hydrated into the local index before retrieval. The output includes `hydrated_memory_count`.

When `--skills-jsonl` is provided, active persisted skills are hydrated into the skill library before matching. The output includes `hydrated_skill_count`.

The CLI does not call a remote model, start a server, or execute external actions.

## Project layout

```text
src/hex_cortex/
  __init__.py
  cli.py
  core/
    schemas.py
    router.py
    workspace.py
    cognitive_clock.py
    cell_registry.py
    cortex_pipeline.py
  memory/
    schemas.py
    index_hydrator.py
    jsonl_store.py
    local_index.py
    retrieval_router.py
    compression.py
  spine/
    schemas.py
    canonical_spine.py
    jsonl_store.py
  evolver/
    schemas.py
    selector.py
    skill_jsonl_store.py
    skill_library.py
    pruning.py
  replay/
    schemas.py
    replay_engine.py
    sleep_replay.py

docs/
  ARCHITECTURE.md
  ENVIRONMENT_STRATEGY.md
  MEMORY_ARCHITECTURE.md
  SELF_IMPROVEMENT.md

tests/
  test_cli.py
  test_router.py
  test_retrieval_router.py
  test_memory_compression.py
  test_memory_index_hydrator.py
  test_memory_jsonl_store.py
  test_canonical_spine.py
  test_spine_jsonl_store.py
  test_evolver.py
  test_cognitive_clock.py
  test_cell_registry.py
  test_skill_jsonl_store.py
  test_skill_library.py
  test_replay_engine.py
  test_sleep_replay.py
  test_pruning_engine.py
  test_cortex_pipeline.py
```

## Current target

Build **HEX-CORTEX v0.1**: a local-first cognitive kernel that can inspect local state, retrieve compact memory, hydrate persisted memories into a local index, hydrate active persisted skills into a procedural skill library, bootstrap new procedural skills locally, run bounded cognitive ticks, route tasks into health-aware deterministic cells, reuse validated procedural skills, replay canonical events into compressed memory, persist compressed memories, batch consolidate replay reports, emit conservative pruning decisions, maintain a compact workspace, record persistent append-only cognitive lineage, evaluate improvement hypotheses, score confidence, expose its internal decisions for replay, and run as a local CLI tool.
