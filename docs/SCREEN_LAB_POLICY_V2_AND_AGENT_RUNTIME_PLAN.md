# SCREEN-LAB-POLICY-V2 AND AGENT RUNTIME PLAN

Status: cold design and implementation plan

## Decision

The `screen_lab_v1` transition predictor is not eligible to advise the planner. The strict policy gate measured 0/4 top-1 and 0/4 top-2 action accuracy. The v1 model and receipts remain valid evidence for transition-learning experiments, but `planner_advice_allowed` stays false and execution remains forbidden.

## Workstream A — screen-lab-policy-v2

1. Remove split-visible rendering differences. Train, validation, and test frames must share the same visual palette; split identity exists only in metadata.
2. Generate a balanced corpus with all four actions represented across varied positions and goals. Initial gate target: at least 32 test transitions, with episode-level split isolation.
3. Keep the frozen visual encoder, but add a spatial representation option based on patch-token pooling or a deterministic spatial projection. Do not silently replace the encoder contract.
4. Add an action-discriminative objective in addition to transition MSE. The observed action must rank closer to the observed next latent than all counterfactual actions by a positive margin.
5. Preserve held-out admission. Training and model selection use train/development evidence; the test policy gate is not an exploration oracle.
6. Require policy gates before planner advice: top-1 accuracy, top-2 accuracy, mean reciprocal rank, positive-improvement rate, correct-action margin, calibration, and multi-step rollout success.
7. Keep `execution_allowed=false` for v2. A green policy gate permits a domain-specific planner packet only, not autonomous dispatch.

## Workstream B — Claude Code surface

The repository already contains a project-scoped `.mcp.json` launching `hex_cortex.memory.cortex_stdio`. The current RPC surface is read-only diagnostics. Add a second, explicitly reviewable coding surface rather than mutating the diagnostic tools:

- repository snapshot and bounded file reads;
- plan generation;
- patch proposal as a unified diff;
- isolated worktree application;
- test/lint execution under allowlisted commands;
- evidence receipt and candidate score;
- operator-approved merge only.

No raw secret, unrestricted shell, or automatic merge capability is exposed through MCP.

## Workstream C — Hermes Agent surface

Keep Hermes memory and HEX-CORTEX memory separate. Exchange only signed task envelopes, bounded context references, results, and receipts. Implement transports in this order:

1. MCP;
2. OpenAI-compatible endpoint discovery;
3. declared Hermes API;
4. bounded CLI stdio.

Hermes may execute a task in an isolated worktree, but it cannot import its full memory into HEX-CORTEX or overwrite canonical evidence.

## Workstream D — dual-model coding rail

Use a provider-neutral model contract and route every request through one of two model classes:

- `local_open_weight`: OpenAI-compatible local/server endpoint, intended for privacy, routine coding, indexing, and first-pass patches;
- `remote_api`: authenticated API model, intended for difficult planning, critique, and final review.

Required controls:

- capability declaration and model fingerprint;
- per-task cost, latency, context, and privacy policy;
- fallback without silent provider substitution;
- model-call receipts with prompt/context hashes, never raw secrets;
- A/B evaluation on the same immutable task set;
- no model may self-promote based on its own score.

## Workstream E — learning from other LLMs

HEX-CORTEX may learn from other models only through governed artifacts:

- proposals;
- critiques;
- patches;
- test results;
- preference pairs;
- distilled skills;
- accepted/rejected outcome receipts.

This is not automatic weight training. Initial learning means retrieval, skill induction, routing calibration, and evaluator improvement. Any fine-tuning or distillation is a separate offline pipeline with licensed data, train/dev/test separation, provenance, rollback, and explicit promotion.

## Workstream F — self-correction

Build an evidence-driven repair loop:

1. formulate one falsifiable hypothesis;
2. create an isolated worktree;
3. generate a bounded patch;
4. run deterministic tests, lint, type checks, and task-specific evaluators;
5. classify the failure;
6. allow a limited repair budget without changing the hypothesis;
7. compare against baseline and sibling candidates;
8. distill the result into a compact insight;
9. admit only through a held-out merge gate;
10. retain failed attempts as evidence, not as active code.

The corrector must never edit the evaluator, lower thresholds, or rewrite history to make a candidate pass.

## Arbor parity target

HEX-CORTEX is not yet equivalent to Arbor. It already has contracts, receipts, gates, model routing, isolated evidence, and fail-closed execution. Missing for Arbor-level autonomous research:

- persistent hypothesis tree;
- long-lived coordinator over a research frontier;
- short-lived executors in isolated worktrees;
- parent/child insight propagation;
- branch selection and pruning;
- immutable development versus held-out evaluators;
- autonomous multi-candidate comparison under a budget;
- verified merge gate across long-running experiments.

Implement these as `cortex_hypothesis_tree_v1`, `cortex_research_coordinator_v1`, `cortex_executor_worktree_v1`, and `cortex_heldout_admission_v1`. Do not merge them with the world-model state or Hermes memory.

## Ordered delivery

1. `screen-lab-policy-v2-data`
2. `screen-lab-policy-v2-ranking-loss`
3. `screen-lab-policy-v2-heldout-eval`
4. `coding-model-router-v2`
5. `claude-code-reviewable-tools-v1`
6. `hermes-executor-adapter-v1`
7. `self-correction-hypothesis-loop-v1`
8. `arbor-like-hypothesis-tree-v1`

Each stage must keep tests green and produce a receipt before the next stage begins.
