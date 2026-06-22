# Verified Local Execution Runtime V1

## Purpose

Execute the primary local-model sampling phase of a canonical
`cortex_cognitive_loop_plan_v1` without granting repository mutation, shell,
patch, test, merge, or automatic escalation authority.

The runtime is intentionally smaller than a coding agent. It does exactly this:

1. validates the immutable plan hash;
2. verifies that the supplied model matches the selected brain's stored model hash;
3. re-runs GPU admission from a fresh snapshot;
4. requires both `--operator-approved` and the exact phrase
   `EXECUTE_VERIFIED_LOCAL_LOOP`;
5. calls local Ollama through `POST /api/chat` for at most five primary samples;
6. aggregates the samples through weighted self-consistency;
7. applies deterministic arithmetic verification when the plan requires it;
8. returns `completed`, `needs_more_samples`, `needs_escalation`,
   `needs_human_review`, `refused`, `failed`, or `blocked`;
9. unloads the Ollama model after the final sample by sending `keep_alive=0`;
10. persists hashes and decisions only, never prompts, responses, raw consensus,
    secrets, patches, or shell output.

## Explicitly forbidden in V1

- automatic second-model calls;
- automatic resampling beyond the plan's initial primary sample budget;
- repository writes;
- patch generation or application;
- shell execution;
- running tests;
- automatic skill installation;
- automatic merge or promotion;
- remote model calls.

Each later stage is a separate operator-approved operation.

## Windows sequence

Update and reinstall the editable package:

```powershell
git pull --ff-only origin screen-lab-policy-v2
python -m pip install -e ".[dev]"
```

Create a fresh GPU snapshot using the existing GPU probe or guard. The snapshot
must represent the current state immediately before execution.

Create the instruction and task files. Keep repository context bounded and put it
in a separate context file only when needed.

Generate and persist the canonical plan:

```powershell
hexcortex-loop plan `
  --gpu-snapshot .hex-cortex\gpu-snapshot.json `
  --task-domain code_generation `
  --context-sensitivity private `
  --difficulty high `
  --risk medium `
  --cost-pressure 0.8 `
  --output .hex-cortex\cognitive\next-plan.json
```

Review `next-plan.json`. Execution is allowed only when `status` is `ready` and
the selected primary brain and resource decision are expected.

Execute the primary local phase:

```powershell
hexcortex-loop execute-local `
  .hex-cortex\cognitive\next-plan.json `
  --gpu-snapshot .hex-cortex\gpu-snapshot.json `
  --instruction-file .hex-cortex\tasks\instruction.txt `
  --prompt-file .hex-cortex\tasks\task.txt `
  --context-file .hex-cortex\tasks\context.txt `
  --model qwen2.5-coder:7b `
  --receipt .hex-cortex\receipts\verified-local-execution.jsonl `
  --operator-approved `
  --confirm EXECUTE_VERIFIED_LOCAL_LOOP
```

The context-file argument may be omitted when no bounded repository context is
needed.

## Expected result for the current Windows fleet

Both measured Windows brain records currently point to the same underlying
`qwen2.5-coder:7b` model. They are measurement aliases, not independent critics.
Therefore, a high-difficulty strategy that requires a second-model critique must
produce:

```text
verification_gap: true
require_human_validation: true
next_action: execute_primary_then_human_review
```

After the three primary samples, the V1 runtime must stop at
`needs_human_review`. It must not pretend that another brain identifier backed by
the same model is independent evidence.

## Receipt boundary

The JSONL receipt may include:

- source plan hash;
- selected brain identifier;
- model identifier hash;
- sample hashes and counts;
- individual call receipt hashes;
- fresh GPU admission decision;
- consensus event hash and confidence;
- verification action and reason;
- deterministic verifier result;
- next action.

It must not include prompt text, response text, consensus text, secrets, source
code, patches, or chain-of-thought.
