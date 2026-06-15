# HEX-CORTEX

**Cellular World Model Intelligence**

HEX-CORTEX is an experimental AI architecture designed around small specialized cells, sparse activation, a global cognitive workspace, and a JEPA-inspired world-model layer.

The goal is not to build one oversized model. The goal is to build a modular cognitive system where intelligence emerges from routing, memory, prediction, criticism, replay, and controlled action.

## Core thesis

```text
intelligence = specialized cells
             + fast routing
             + sparse activation
             + global workspace
             + predictive world model
             + critic / immune system
             + memory replay
```

## Architecture principles

1. **Local-first**: prototype locally before deploying anything to a shared server.
2. **Small cells, strong contracts**: every cell has explicit input/output schemas.
3. **Sparse activation**: never activate the whole cortex when a small circuit is enough.
4. **Fast / working / deep thinking**: cognitive depth depends on uncertainty, novelty, risk, and cost.
5. **No cognition without lineage**: every decision should be traceable to task, cells, workspace state, and confidence.
6. **Memory is compressed experience**: raw logs are not intelligence; replayable compressed patterns are.
7. **Criticism is native**: every high-impact answer must pass through a critic or immune gate.

## Cognitive loop

```text
input
→ perception
→ thalamic routing
→ sparse cell activation
→ global workspace
→ world model prediction
→ critic / immune check
→ action
→ memory / replay
```

## Repository status

This repository starts with the foundation only:

- architecture notes
- environment strategy
- Pydantic contracts
- minimal thalamic router
- minimal global workspace
- unit tests

No heavy model inference, GPU serving, or training code is included in the initial version.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -e '.[dev]'
pytest
```

## Project layout

```text
src/hex_cortex/
  core/
    schemas.py
    router.py
    workspace.py

docs/
  ARCHITECTURE.md
  ENVIRONMENT_STRATEGY.md

tests/
  test_router.py
```

## Current target

Build **HEX-CORTEX v0.1**: a local-first cognitive kernel that can route tasks into small deterministic cells, maintain a compact workspace, score confidence, and expose its internal decisions for replay.
