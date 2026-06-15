# HEX-CORTEX Architecture v0.1

HEX-CORTEX is a cellular cognitive architecture. It is not designed as a single monolithic LLM. It is designed as a system of specialized cells connected through a fast router, a compact global workspace, and a replayable memory spine.

## Core components

### 1. Thalamic Router

The router decides how deeply the system should think and which cells should be activated.

Inputs:

- task type
- domain hints
- novelty
- risk
- uncertainty
- latency budget
- available cells
- historical trust scores

Outputs:

- cognitive mode: `reflex`, `working`, or `deep`
- selected cells
- max ticks
- confidence threshold

### 2. Cognitive Clock

The cognitive clock prevents uncontrolled agent loops.

Default ticks:

```text
0 intake
1 perception
2 abstraction
3 prediction
4 criticism
5 action
6 memory_update
```

Each task gets a bounded budget: maximum ticks, maximum cells, maximum latency, and minimum confidence.

### 3. Global Workspace

The workspace is the active cognitive state. It is intentionally compact.

It stores:

- active goal
- selected cells
- hypotheses
- contradictions
- predictions
- confidence
- next action

It must not become a raw transcript dump.

### 4. Sparse Cell Network

Cells are small specialized modules. A cell can be deterministic code, a small model, a tool wrapper, or a hybrid.

Examples:

- IntentCell
- LogicCell
- MathCell
- CodeCell
- MemoryCell
- CriticCell
- WorldModelCell
- PlannerCell
- EvidenceCell
- ActionCell

Rule:

```text
Many cells may exist. Only a few should activate per task.
```

### 5. World Model Organ

The world model predicts consequences in latent or structured state space.

Initial scope:

```text
state_t + candidate_action → predicted_state_t+1
```

The first version predicts cognitive and system consequences, not full physical reality.

### 6. Critic / Immune System

The critic and immune system detect:

- contradiction
- missing evidence
- overconfidence
- repeated cell failure
- unsafe action
- corrupted memory
- infinite reasoning loops

A cell can be trusted, double-checked, degraded, or quarantined.

### 7. Canonical Spine

Every meaningful cognitive event should be append-only and replayable.

Events include:

- task received
- routing decision
- cell result
- workspace update
- prediction
- critic report
- action decision
- memory write

This prevents false diagnostics and makes cognition auditable.

## Thinking modes

### Reflex mode

Fast, low-cost processing.

Target use cases:

- classification
- direct memory hit
- simple formatting
- low-risk routing

### Working mode

Short technical reasoning.

Target use cases:

- code review
- architecture comparison
- explanation
- local planning

### Deep mode

Expensive reasoning and simulation.

Target use cases:

- high-risk decisions
- novel design
- scientific reasoning
- multi-step architecture
- conflicting evidence

## Design rule

```text
Think fast by activating little.
Think well by criticizing strongly.
Think far by predicting latent consequences.
Learn by replaying compressed errors.
```
