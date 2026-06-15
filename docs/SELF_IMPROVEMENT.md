# HEX-EVOLVER Self-Improvement Architecture v0.1

HEX-CORTEX must improve itself, but never in an uncontrolled way.

Self-improvement is an organ, not a side effect.

## Core law

```text
Observe.
Compress.
Hypothesize.
Test.
Select.
Promote.
Replay.
Rollback if needed.
```

## What self-improvement means

HEX-CORTEX does not modify model weights in v0.1.

It improves through:

- compressed memory
- tacit rules
- skill records
- cell health scores
- routing feedback
- replay outcomes
- promotion gates
- regression checks

Fine-tuning and distillation come later, after enough high-quality traces exist.

## Self-improvement loop

```text
CanonicalSpine events
→ MemoryCompressionSpine
→ ErrorPatternDetector
→ ImprovementHypothesis
→ Sandbox/Evaluation
→ PromotionDecision
→ SkillLibrary / CellHealth update
→ Replay
```

## Biological inspirations

### Evolution

```text
variation → selection → retention
```

HEX-CORTEX translation:

```text
improvement hypothesis → evaluation metrics → promotion gate
```

### Immune system

```text
detect abnormal behavior → quarantine → retest
```

HEX-CORTEX translation:

```text
cell failures → trust score down → double-check or quarantine
```

### Sleep replay

```text
recent episodes → consolidation → pruning
```

HEX-CORTEX translation:

```text
batch replay → memory compression → index update → weak rule pruning
```

### Myelination

```text
frequently successful path → faster pathway
```

HEX-CORTEX translation:

```text
successful workflow → SkillRecord → reflex/working path
```

### Synaptic pruning

```text
unused or noisy connection → weaken/remove
```

HEX-CORTEX translation:

```text
low-value rule/memory/cell → lower priority or archive
```

## Safety boundaries

Self-improvement is allowed only through controlled artifacts.

Rules:

1. No direct mutation of `main` by an autonomous loop.
2. Every hypothesis needs source lineage.
3. Every promotion needs evaluation evidence.
4. Every promoted change needs a rollback plan.
5. Failed evaluations must create memory, not be hidden.
6. A cell can be degraded or quarantined.
7. No unbounded recursive self-improvement.
8. No shell execution in v0.1 self-improvement.
9. No model weight modification in v0.1.
10. No promotion without regression checks.

## v0.1 scope

Implement only typed records and deterministic selection logic:

- ImprovementHypothesis
- EvaluationMetric
- EvaluationResult
- PromotionDecision
- SkillRecord
- CellHealth
- EvolutionSelector

No autonomous code generation yet.

## Promotion gates

An improvement can be promoted only if:

```text
score >= threshold
tests_passed = true
regressions = []
rollback_plan is present
risk_level is acceptable
```

## Future phases

### v0.2

- persistent SkillLibrary
- replay scheduler
- cell trust update engine

### v0.3

- sandboxed patch proposals
- branch-based evaluations
- CI-backed promotion gate

### v0.4

- distillation dataset exporter
- small RouterCell training dataset
- small CriticCell training dataset

### v0.5

- optional supervised fine-tuning or preference tuning on validated traces
