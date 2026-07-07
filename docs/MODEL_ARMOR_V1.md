# Model Armor v1

HEX-CORTEX is model-interchangeable. Model armor is the cognitive exoskeleton
that makes any base model — especially a small local one — behave like a
disciplined senior engineer. The power comes from structure around the model,
never from weakening the model's own guardrails.

## Principle

Discipline scales inversely with capability:

| Scale  | Params (guide) | Discipline | Max files/step | Max diff lines/step |
|--------|----------------|------------|----------------|---------------------|
| tiny   | < 2B           | maximal    | 1              | 40                  |
| small  | 2–8B           | strict     | 2              | 80                  |
| medium | 8–35B          | standard   | 4              | 200                 |
| large  | > 35B          | light      | 8              | 400                 |

What never scales down, at any size:

- deterministic verification (pytest + lint) before any success claim,
- the full loop `understand → plan → act → verify → reflect`,
- post-error reflection against the genome error ontology,
- skill proposals as candidates only (human promotion gate),
- branch-first mutation, no secret access, base-model guardrails untouched.

## Coding protocols

Eight protocols distilled from proven agentic engineering practice, encoded in
`cortex_model_armor.CODING_PROTOCOLS`:

1. **Baseline before change** — run tests/lint first; the baseline is the only
   honest reference point.
2. **Read before edit** — never edit unread code; match surrounding
   conventions.
3. **Plan before code** — restate the task, list files and reasons, smallest
   complete plan.
4. **Smallest-cause fix** — reproduce, read the real error, fix the cause not
   the symptom, rerun targeted then full tests.
5. **Empirical verification** — never claim unexecuted behavior; probe unknown
   library behavior with tiny scripts; report failures verbatim.
6. **Atomic commits** — one concern per commit, tree green at every commit,
   branch-first.
7. **Post-error reflection** — classify failures against the error ontology,
   extract one reusable lesson, propose (never install) skills.
8. **Adversarial self-review** — after producing a change, try to refute it;
   keep only claims that survive.

## Surfaces

- Python: `hex_cortex.memory.cortex_model_armor.build_model_armor_plan(...)`,
  `list_coding_protocols()`, `propose_protocol_skill_candidates()`.
- MCP: tool `hex_cortex_model_armor` with actions `plan`, `protocols`,
  `skill_candidates`. Read-only; runs nothing; no model call.

## Integration path for a runtime

1. Detect or declare the base model profile (scale, context window,
   tool-call/JSON support).
2. Call `build_model_armor_plan` and assemble the prompt scaffold sections in
   order; a tight context (< 16k tokens) adds mandatory compression and
   retrieval-first context policy.
3. Enforce the step budget mechanically (reject oversized diffs).
4. Feed `compute_strategy` (reused from the adaptive compute policy) to the
   GPU governor / router.
5. On failed verification twice, or risk ≥ high, escalate to a larger model or
   the operator per `escalation_contract`.

## Non-goals

The armor does not remove refusals, does not bypass safety rails, does not
grant autonomy beyond the safe autonomy ladder, and does not execute anything
itself. It is a plan generator: cold, pure, deterministic.
