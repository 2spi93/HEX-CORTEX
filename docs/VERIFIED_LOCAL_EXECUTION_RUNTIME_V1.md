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
7. optionally builds a bounded AST repository context and requests a structured
   JSON code plan;
8. applies deterministic arithmetic verification when the plan requires it;
9. returns `completed`, `needs_more_samples`, `needs_escalation`,
   `needs_human_review`, `refused`, `failed`, or `blocked`;
10. unloads the Ollama model after the final sample by sending `keep_alive=0`;
11. persists hashes and decisions only, never prompts, responses, raw consensus,
    repository context, secrets, patches, or shell output.

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

### Plain-text compatibility mode

```powershell
hexcortex-loop execute-local `
  .hex-cortex\cognitive\next-plan.json `
  --gpu-snapshot .hex-cortex\gpu-snapshot.json `
  --instruction-file .hex-cortex\tasks\instruction.txt `
  --prompt-file .hex-cortex\tasks\task.txt `
  --model qwen2.5-coder:7b `
  --receipt .hex-cortex\receipts\verified-local-execution.jsonl `
  --operator-approved `
  --confirm EXECUTE_VERIFIED_LOCAL_LOOP
```

A manually prepared context file may be supplied with `--context-file`.

### Grounded structured code-plan mode

Use this mode for repository analysis and code planning:

```powershell
hexcortex-loop execute-local `
  .hex-cortex\cognitive\next-plan.json `
  --gpu-snapshot .hex-cortex\gpu-snapshot.json `
  --instruction-file .hex-cortex\tasks\instruction.txt `
  --prompt-file .hex-cortex\tasks\task.txt `
  --repo-root . `
  --auto-repo-context `
  --structured-code-plan `
  --repo-context-max-modules 10 `
  --repo-context-max-chars 12000 `
  --model qwen2.5-coder:7b `
  --max-output-tokens 900 `
  --timeout-seconds 300 `
  --sample-temperature 0.2 `
  --receipt .hex-cortex\receipts\verified-local-structured.jsonl `
  --operator-approved `
  --confirm EXECUTE_VERIFIED_LOCAL_LOOP
```

This mode:

- ranks real Python modules from task terms, imports, definitions and references;
- supplies only module paths, imports, public symbol names and line numbers;
- never pastes source bodies;
- sends an Ollama JSON schema through the `format` field;
- validates every proposed file against the selected repository paths;
- removes invented paths before consensus;
- compares focus areas, validated files and proposed change targets rather than
  byte-identical prose;
- returns the weighted medoid plan for human review.

`--structured-code-plan` requires `--auto-repo-context` and `--repo-root`.

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

In structured mode, `consensus_status: consensus` means that at least two samples
agree on the normalized decision structure. It does not remove the human-review
requirement when no independent critic exists.

## Receipt boundary

The JSONL receipt may include:

- source plan hash;
- selected brain identifier;
- model identifier hash;
- sample hashes and counts;
- individual call receipt hashes;
- fresh GPU admission decision;
- bounded repository-context hash, character count and module count;
- structured schema hash;
- grounding ratio and invalid-path count;
- consensus event hash and confidence;
- verification action and reason;
- deterministic verifier result;
- next action.

It must not include prompt text, response text, consensus text, repository-context
text, secrets, source code, patches, or chain-of-thought.
