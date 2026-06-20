# HEX-CORTEX Cognitive Genome, Adaptive Distillation and CR-JEPA V0

## Status

Cold architecture and executable contracts are implemented. No LLM base weights are modified by this block. CR-JEPA V0 is a research descriptor and dataset contract only; training is disabled until the evidence gate is satisfied.

## Purpose

HEX-CORTEX treats the language model as an interchangeable cognitive engine and the surrounding architecture as a persistent cognitive exoskeleton. The exoskeleton must preserve verified skills, detect model-specific failure modes, select epistemic profiles and tools, regulate cost and uncertainty, and permit only reversible, evidence-backed mutations.

The architecture is designed around five separations:

1. Base-model parameters are not the identity of HEX-CORTEX.
2. Immutable genome rules are separate from mutable evidence ledgers.
3. Raw reasoning is separate from auditable residual metadata.
4. Skill memory is separate from adapter weights.
5. Proposal, evaluation and promotion are separate authorities.

## Canonical tree

```text
HEX-CORTEX COGNITIVE GENOME V1
|
|-- Error Ontology
|-- Profile Council
|-- Verifier Hierarchy
|-- Cognitive Residual Ledger
|-- Residual Topology Consolidation
|-- Competency Baselines
|-- Skill Graph
|-- Causal Intervention Ledger
|-- Cognitive Homeostasis Controller
|-- Mutation Sandbox
|-- Anti-Forgetting Gate
|-- Adapter Registry
`-- CR-JEPA V0 Dataset Contract
```

## Immutable genome

The repository-controlled genome is stored at:

```text
config/cognitive_genome_v1.json
```

It establishes the following invariants:

- the base model is interchangeable;
- the base model is immutable by default;
- autonomous full-weight mutation is disabled;
- raw chain-of-thought persistence is forbidden;
- evaluator mutation and threshold reduction are forbidden;
- held-out evaluation and reversibility are mandatory;
- promotion requires operator approval;
- automatic merge is forbidden.

The genome is validated by:

```bash
hexcortex-genome audit
```

and is a required stage of the canonical wiring audit.

## Error ontology

The initial ontology contains:

```text
knowledge_gap
logic_error
planning_error
context_loss
tool_misuse
hallucination
ambiguity_failure
capability_limit
uncertainty_failure
causal_misattribution
```

The ontology is deliberately compact. A new class should be added only after recurrent residual evidence demonstrates that existing classes cannot separate a materially different correction policy.

## Cognitive residual ledger

The principal learning unit is not question -> answer. It is:

```text
observed state
-> selected model, profiles and tools
-> predicted outcome
-> observed outcome
-> cognitive residual
-> failure class
-> verified correction
-> causal intervention
```

The append-only default ledger is:

```text
.hex-cortex/cognitive/residual-ledger.jsonl
```

A residual record stores hashes and references, not raw state, raw output or hidden reasoning. The cross-context residual signature intentionally excludes the exact context identity, so the topology can discover the same failure pattern across different contexts and models.

Example:

```bash
hexcortex-genome residual \
  --model-id local-model-instance \
  --model-family gemma \
  --domain hex-cortex \
  --context-signature repo-change-context \
  --state-ref state-embedding-ref \
  --predicted-ref predicted-outcome-ref \
  --observed-ref observed-outcome-ref \
  --failure-class planning_error \
  --residual-magnitude 0.42 \
  --profiles scientist,engineer,adversary \
  --tools pytest,ruff \
  --correction-ref verified-fix-ref \
  --correction-verified
```

## Residual Topology Consolidation

A correction is not immediately converted into a permanent skill. The default consolidation gate requires:

- at least 3 recurrent observations;
- at least 2 distinct contexts;
- at least 2 distinct models;
- every correction verified;
- at least one verified causal intervention.

Projection:

```bash
hexcortex-genome topology
```

Only a ready cluster can produce a skill candidate. Skill promotion remains disabled at candidate creation time.

## Profile Council

Profiles are epistemic functions rather than personalities:

| Profile | Function |
|---|---|
| explorer | generate novel hypotheses |
| researcher | retrieve independent evidence |
| scientist | make claims falsifiable |
| engineer | turn claims into bounded experiments |
| statistician | quantify uncertainty and evidence strength |
| adversary | search for counterexamples and shortcut solutions |
| causalist | design interventions and counterfactual tests |
| archivist | compare against prior failures and skills |
| constitutional_judge | enforce mutation and promotion invariants |

The council does not use naive majority voting. It requires evidence-weighted adjudication and independent views.

```bash
hexcortex-genome council \
  --failure-class causal_misattribution \
  --novelty 0.8 \
  --uncertainty 0.9 \
  --mutation-requested
```

## Verifier hierarchy

Evidence is ordered by epistemic strength:

1. deterministic truth: tests, compilers, solvers, signatures;
2. observed reality: runtime outcomes, instruments, human feedback;
3. causal and physical constraints;
4. independent sources;
5. diverse model critics;
6. human judgment for ambiguity and high-impact promotion.

An LLM critique alone cannot certify a durable skill mutation.

## Cognitive homeostasis

The homeostasis controller regulates the system before mutation. It can:

- retrieve skill memory;
- run deterministic verification;
- allocate additional test-time compute;
- consult a remote teacher after local verification fails;
- propose skill consolidation after recurrent evidence;
- consider an isolated adapter only under low regression risk;
- refuse an unverified high-uncertainty action.

It never selects direct weight mutation.

```bash
hexcortex-genome homeostasis \
  --uncertainty 0.9 \
  --recurrence-count 4 \
  --local-verification-failed \
  --cost-pressure 0.2 \
  --regression-risk 0.1
```

## Competency baselines

Before any trainable mutation, the current model or model-plus-adapter phenotype receives a competency baseline. Critical competencies have zero tolerated regression by default. Noncritical competencies tolerate at most a 0.02 drop.

```bash
hexcortex-memory baseline \
  --model-id local-model-instance \
  --suite-ref cognitive-regression-suite-v1 \
  --metrics-json '{"architecture_contracts":1.0,"coding":0.82}' \
  --critical architecture_contracts
```

Model and suite identifiers are hashed before persistence.

## Causal intervention ledger

A correlation between a tool and a better result is insufficient. The causal ledger stores controlled intervention evidence:

```bash
hexcortex-memory intervention \
  --residual-signature <sha256> \
  --intervention-id enable-deterministic-verifier \
  --control-ref control-run-ref \
  --treatment-ref treatment-run-ref \
  --verifier-ref evaluator-ref \
  --outcome-delta 0.25 \
  --verified
```

Control, treatment and verifier references are hashed before persistence.

## Skill graph

Durable skills are model-independent graph nodes with explicit dependencies and verification provenance. Missing dependencies and graph cycles invalidate the projection.

```bash
hexcortex-memory skill-add \
  --skill-id architecture-contract-audit-v1 \
  --domain hex-cortex \
  --source-residual-signature <sha256> \
  --verification-ref heldout-evaluation-ref \
  --status candidate

hexcortex-memory skill-graph
```

The graph is stored in:

```text
.hex-cortex/cognitive/skill-graph.jsonl
```

## Mutation ladder

Mutations are attempted in increasing order of risk:

```text
external memory
-> skill procedure
-> router update
-> isolated adapter candidate
-> full-weight update
```

Full-weight update is disabled in Genome V1. An isolated adapter plan requires a frozen base model, worktree isolation, held-out evaluation and a revocation reference.

```bash
hexcortex-genome mutation-plan \
  --skill-candidate-hash <sha256> \
  --mutation-level isolated_adapter_candidate \
  --baseline-ref baseline-ref \
  --evaluator-ref evaluator-ref \
  --revocation-ref adapter-revocation-ref
```

## Anti-forgetting gate

A candidate is promotable only when all conditions hold:

- target skill improves;
- held-out gate passes;
- mutation is reversible;
- evaluator is unchanged;
- thresholds are unchanged;
- no critical competency regresses;
- no noncritical competency drops by more than 0.02.

Rejected mutations remain evidence and are never silently discarded.

## Adapter registry

The base model remains immutable. Adapter events are append-only and follow this lifecycle:

```text
candidate -> evaluated -> promoted -> revoked
          `-> rejected
```

Direct candidate-to-promoted transitions are forbidden. Promotion and revocation require operator approval.

```bash
hexcortex-memory adapter-register \
  --adapter-id architecture-audit-v1 \
  --base-model-id local-model-instance \
  --skill-id architecture-contract-audit-v1 \
  --plan-hash <sha256> \
  --checkpoint-hash <sha256> \
  --reversible
```

## CR-JEPA V0

CR-JEPA means Cognitive Residual Joint-Embedding Predictive Architecture. It is an original HEX-CORTEX research hypothesis, not a claim of solved intelligence.

The proposed objective is to predict, in latent space, the residual between an expected outcome and the observed outcome, conditioned on:

- state representation;
- model identity;
- selected profiles;
- selected tools;
- proposed action;
- predicted outcome.

Targets include:

- observed outcome representation;
- cognitive residual representation;
- failure class;
- best verified corrective intervention.

V0 does not train. It only measures dataset readiness:

```bash
hexcortex-genome cr-jepa-manifest
```

The initial research gate requires at least:

- 1,000 verified residuals;
- 200 causal residuals;
- 6 distinct failure classes;
- a held-out split designed before training.

These numbers are starting governance thresholds, not scientific constants. They may be revised only through a separate evidence-backed proposal; they must never be lowered to make a candidate pass.

## Research grounding

This architecture is informed by, but not equivalent to, the following work:

- Yann LeCun, A Path Towards Autonomous Machine Intelligence, 2022: world models, actor, cost, memory and hierarchical planning.
- Assran et al., Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture, arXiv:2301.08243: prediction in representation space.
- V-JEPA 2, 2025: video-based world modeling and action-conditioned physical prediction.
- Nam et al., Causal-JEPA, arXiv:2602.11389: object-level latent interventions and counterfactual-like reasoning.
- Kamoi et al., When Can LLMs Actually Correct Their Own Mistakes?, arXiv:2406.01297: reliable external feedback is central to successful correction.
- Continual-learning adapter research including C-LoRA, PEARL, JumpLoRA and program-memory approaches: parameter isolation and routed adapters can reduce interference, but catastrophic forgetting is not solved generally.

## Explicit non-claims

This block does not claim that:

- cognitive residuals constitute consciousness;
- JEPA alone solves reasoning;
- a small model becomes globally equivalent to a frontier model;
- mathematical constants such as the golden ratio are universal intelligence laws;
- self-generated feedback is a sufficient verifier;
- CR-JEPA has demonstrated empirical superiority.

Every such proposition remains a falsifiable hypothesis requiring controlled experiments.

## Immediate operating sequence

```text
1. audit the genome
2. record verified residuals
3. project recurring topology
4. run causal interventions
5. build skill candidates
6. establish competency baselines
7. prefer memory, procedure and routing mutations
8. train isolated adapters only after evidence accumulation
9. apply anti-forgetting and held-out gates
10. promote or revoke with operator approval
```
