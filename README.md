# HEX-CORTEX

**Cellular World Model Intelligence**

HEX-CORTEX is an experimental AI architecture designed around small specialized cells, sparse activation, a global cognitive workspace, local-first memory retrieval, memory compression, procedural skill memory, replay consolidation, sleep replay batches, a canonical append-only spine, controlled self-improvement, a bounded cognitive clock, a health-aware cell registry, and a JEPA-inspired world-model layer.

The goal is not to build one oversized model. The goal is to build a modular cognitive system where intelligence emerges from health-aware routing, bounded execution, memory compression, replay consolidation, skill reuse, prediction, criticism, lineage, controlled self-improvement, and controlled action.

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
             + canonical lineage
             + replay consolidation
             + sleep replay batches
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
12. **Self-improvement is gated**: hypotheses must be evaluated, scored, and rollback-safe before promotion.
13. **Criticism is native**: every high-impact answer must pass through a critic or immune gate.

## Cognitive loop

```text
input
→ cognitive clock start
→ canonical spine event
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
→ sleep replay batch
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
```

## Canonical spine law

```text
Append events.
Never rewrite cognition.
Verify hash chain.
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
Search skills by trigger tags.
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

## Repository status

This repository starts with the foundation only:

- architecture notes
- environment strategy
- memory architecture
- self-improvement architecture
- Pydantic contracts
- health-aware thalamic router
- bounded cognitive clock
- health-aware cell registry
- procedural skill library
- replay engine
- sleep replay batch engine
- minimal global workspace
- local knowledge index
- retrieval router
- deterministic memory compression spine
- append-only canonical spine
- deterministic evolution selector
- unit tests

No heavy model inference, GPU serving, vector database, autonomous code modification, arbitrary skill execution, or training code is included in the initial version.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -e '.[dev]'
pytest
ruff check .
```

## Project layout

```text
src/hex_cortex/
  core/
    schemas.py
    router.py
    workspace.py
    cognitive_clock.py
    cell_registry.py
  memory/
    schemas.py
    local_index.py
    retrieval_router.py
    compression.py
  spine/
    schemas.py
    canonical_spine.py
  evolver/
    schemas.py
    selector.py
    skill_library.py
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
  test_router.py
  test_retrieval_router.py
  test_memory_compression.py
  test_canonical_spine.py
  test_evolver.py
  test_cognitive_clock.py
  test_cell_registry.py
  test_skill_library.py
  test_replay_engine.py
  test_sleep_replay.py
```

## Current target

Build **HEX-CORTEX v0.1**: a local-first cognitive kernel that can retrieve compact memory, run bounded cognitive ticks, route tasks into health-aware deterministic cells, reuse validated procedural skills, replay canonical events into compressed memory, batch consolidate replay reports, maintain a compact workspace, record append-only cognitive lineage, evaluate improvement hypotheses, score confidence, and expose its internal decisions for replay.
