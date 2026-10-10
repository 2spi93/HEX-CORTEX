# HEX-CORTEX Project Alignment

## Mission

HEX-CORTEX is a generalist coding and learning cortex.

Its primary job is not trading, execution, dashboards, or a single domain workflow. Its primary job is to help build, inspect, test, repair, learn, compress, and reuse knowledge across software projects.

## Non-goals

HEX-CORTEX must not become a trading bot by default.
HEX-CORTEX must not treat execution as its center.
HEX-CORTEX must not self-modify without tests, lineage, and rollback.
HEX-CORTEX must not grow by adding unverified agents or vague memory.

## Core loop

```text
retrieve little
reason bounded
record everything
compress experience
extract reusable rules
promote only with evidence
reuse validated skills
```

## Priority order

1. Coding reliability
2. Learning from errors and successes
3. Memory compression and retrieval precision
4. Verified reusable skills
5. Controlled self-improvement
6. Generalist project support
7. Domain-specific execution only behind explicit gates

## Architectural laws

### No cognition without lineage

Every important perception, route, decision, action, result, correction, and learning event must have source lineage.

### Memory is not storage

Memory must be selectable, compressed, scoped, visible, and reusable. Raw logs are not intelligence.

### Skills are earned

A skill is not a prompt. A skill candidate must come from accepted learning events, tested workflows, corrections, benchmarks, or external lessons with evidence.

### Execution is optional and gated

Execution is not the identity of HEX-CORTEX. Any destructive or irreversible execution requires a dedicated authorization gate.

### Local-only architecture (decision 2026-10-10)

No HEX-CORTEX server. Hosted reasoning APIs require explicit consent. No local LLM, GPU, or benchmark gate.

## Current strategic spine

```text
CortexLearningEvent
→ CortexSkillCandidate
→ SkillLibrary
→ Replay / Evaluation
→ PromotionGate
→ DistillationDataset later
```

## Current engineering focus

Prior skill candidate and genome contracts already exist. Connect existing modules with independent evidence, recovery and gateway protection. See [original architecture audit](ORIGINAL_VISION_GAP_AUDIT_2026_10.md).
