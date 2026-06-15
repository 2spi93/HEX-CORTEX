# HEX-CORTEX

**Cellular World Model Intelligence**

HEX-CORTEX is an experimental AI architecture designed around small specialized cells, sparse activation, a global cognitive workspace, local-first memory retrieval, memory compression, a canonical append-only spine, controlled self-improvement, and a JEPA-inspired world-model layer.

The goal is not to build one oversized model. The goal is to build a modular cognitive system where intelligence emerges from routing, memory compression, prediction, criticism, replay, lineage, controlled self-improvement, and controlled action.

## Core thesis

```text
intelligence = specialized cells
             + fast routing
             + sparse activation
             + global workspace
             + index-first memory
             + canonical lineage
             + controlled self-improvement
             + predictive world model
             + critic / immune system
             + memory replay
```

## Architecture principles

1. **Local-first**: prototype locally before deploying anything to a shared server.
2. **Small cells, strong contracts**: every cell has explicit input/output schemas.
3. **Sparse activation**: never activate the whole cortex when a small circuit is enough.
4. **Fast / working / deep thinking**: cognitive depth depends on uncertainty, novelty, risk, and cost.
5. **Index-first memory**: never inject long context before searching a compact index.
6. **No cognition without lineage**: every decision should be traceable to task, cells, workspace state, and confidence.
7. **Memory is compressed experience**: raw logs are not intelligence; replayable compressed patterns are.
8. **Self-improvement is gated**: hypotheses must be evaluated, scored, and rollback-safe before promotion.
9. **Criticism is native**: every high-impact answer must pass through a critic or immune gate.

## Cognitive loop

```text
input
→ canonical spine event
→ local knowledge index
→ retrieval router
→ bounded context packet
→ thalamic routing
→ sparse cell activation
→ global workspace
→ world model prediction
→ critic / immune check
→ action
→ memory compression
→ self-improvement candidate
→ replay
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

## Repository status

This repository starts with the foundation only:

- architecture notes
- environment strategy
- memory architecture
- self-improvement architecture
- Pydantic contracts
- minimal thalamic router
- minimal global workspace
- local knowledge index
- retrieval router
- deterministic memory compression spine
- append-only canonical spine
- deterministic evolution selector
- unit tests

No heavy model inference, GPU serving, vector database, autonomous code modification, or training code is included in the initial version.

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
```

## Current target

Build **HEX-CORTEX v0.1**: a local-first cognitive kernel that can retrieve compact memory, route tasks into small deterministic cells, compress experience into replayable rules, maintain a compact workspace, record append-only cognitive lineage, evaluate improvement hypotheses, score confidence, and expose its internal decisions for replay.
