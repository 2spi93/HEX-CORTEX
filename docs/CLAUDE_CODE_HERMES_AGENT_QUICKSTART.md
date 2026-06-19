# Claude Code and Hermes Agent quickstart

## Windows — Claude Code

From an elevated or normal PowerShell in the HEX-CORTEX checkout:

```powershell
powershell -ExecutionPolicy Bypass `
  -File scripts\install_claude_code_windows.ps1 `
  -Method native `
  -Channel stable
```

If the installer reports success but `claude` is not found, close every PowerShell window, open a new one, return to the repository, and run:

```powershell
claude --version
claude doctor
claude
```

The project-scoped `.mcp.json` starts HEX-CORTEX through stdio. In Claude Code, run `/mcp`, approve the project server named `hex-cortex`, and inspect the exposed tools. The MCP surface stays read-only for diagnostics and planning. Patch application and worktree execution remain explicit operator-approved CLI operations.

## Windows — validate the agent runtime branch

```powershell
git fetch origin
git switch -C screen-lab-policy-v2 origin/screen-lab-policy-v2
python -m pip install -e ".[dev,vision]"
python -m pytest
ruff check .

hexcortex-agent model-catalog
hexcortex-agent route-task routine_patch `
  --context-sensitivity private `
  --complexity medium

hexcortex-agent correction-plan `
  policy_gate_failed `
  "Action-discriminative training improves held-out top-1 accuracy." `
  "main@957d0eb" `
  "screen_lab_policy_v2_gate"

hexcortex-agent screen-v2-plan
```

## Generate the screen-lab-policy-v2 corpus

This creates 24 training episodes, 8 validation episodes, and 8 test episodes, with 8 transitions per episode and a balanced four-action distribution.

```powershell
$WorkspaceV2 = ".hex-cortex\environments\screen_lab_policy_v2"

hexcortex-agent screen-v2-bootstrap `
  --workspace-root "$WorkspaceV2" `
  --seed 42 `
  --replace-existing-source `
  --operator-approved `
  --model-ref facebook/dinov2-base `
  --pooling cls `
  --device cpu
```

Create the action-discriminative training plan:

```powershell
$ManifestV2 = Join-Path $WorkspaceV2 "manifest.json"
$PlanV2 = Join-Path $WorkspaceV2 "training-plan-v2.json"
$CandidateV2 = Join-Path $WorkspaceV2 "candidate-v2"

hexcortex-agent screen-v2-train-plan `
  "$ManifestV2" `
  --output "$PlanV2" `
  --hidden-dim 128 `
  --epochs 100 `
  --batch-size 16 `
  --ranking-margin 0.0001 `
  --ranking-weight 1.0 `
  --minimum-top1-accuracy 1.0 `
  --device cpu `
  --max-seconds 1800
```

Train the candidate:

```powershell
hexcortex-agent screen-v2-train `
  "$ManifestV2" `
  "$PlanV2" `
  --environment-root "$WorkspaceV2" `
  --output-dir "$CandidateV2" `
  --model-ref facebook/dinov2-base `
  --pooling cls `
  --device cpu `
  --operator-approved
```

Do not promote the candidate unless its manifest reports both `promotion_allowed=true` and `policy_gate_passed=true`. A failed top-1 held-out gate is a valid result and must remain blocked.

## Linux server — Hermes Agent

From the server checkout:

```bash
cd /opt/HEX-CORTEX
bash scripts/install_hermes_agent_server.sh /opt/HEX-CORTEX
hermes setup
```

Merge the example `deploy/server/hermes-hex-cortex-mcp.yaml.example` into `~/.hermes/config.yaml`, correcting the checkout path when necessary. Then run:

```bash
hermes doctor
hermes chat
```

The adapter contract keeps Hermes memory and HEX-CORTEX memory separate. Hermes receives signed task envelopes and bounded context references; HEX-CORTEX accepts only results and receipts that preserve `memory_policy=separate_no_merge`.

## Local open-weight plus remote API model

The model catalog is provider-neutral. The local rail expects an OpenAI-compatible service on localhost, normally `llama-server` on Linux. The remote rail is disabled until its provider is available and the operator explicitly permits sending the bounded context.

```powershell
hexcortex-agent model-catalog `
  --local-endpoint http://127.0.0.1:8080 `
  --local-model Qwen3-Coder-30B-A3B-Instruct `
  --remote-provider openai `
  --remote-model gpt-5.5 `
  --remote-api-key-ref env:OPENAI_API_KEY
```

The catalog command does not call either model. It produces a secret-free routing receipt.

### Execute a local coding task

Prepare UTF-8 files for the instruction, task, and bounded repository context:

```powershell
$TaskDir = ".hex-cortex\coding-tasks\task-001"
New-Item -ItemType Directory -Force -Path $TaskDir | Out-Null

Set-Content -Encoding utf8 `
  (Join-Path $TaskDir "instruction.txt") `
  "Act as a careful coding agent. Return a reviewable plan or unified diff only."

Set-Content -Encoding utf8 `
  (Join-Path $TaskDir "prompt.txt") `
  "Repair the failing parser test without modifying the evaluator."

Set-Content -Encoding utf8 `
  (Join-Path $TaskDir "context.txt") `
  "Insert only the bounded source and failure context approved for this task."
```

Call the local OpenAI-compatible endpoint:

```powershell
hexcortex-code execute `
  local_open_weight `
  (Join-Path $TaskDir "prompt.txt") `
  --instruction-file (Join-Path $TaskDir "instruction.txt") `
  --context-file (Join-Path $TaskDir "context.txt") `
  --model Qwen3-Coder-30B-A3B-Instruct `
  --local-endpoint http://127.0.0.1:8080 `
  --context-sensitivity private `
  --operator-approved
```

The returned text is volatile and is not appended automatically to a receipt store.

### Execute an explicitly approved remote review

Configure the API key in the current shell without writing it into the repository:

```powershell
$env:OPENAI_API_KEY = "<set-outside-the-repository>"

hexcortex-code execute `
  remote_api `
  (Join-Path $TaskDir "prompt.txt") `
  --instruction-file (Join-Path $TaskDir "instruction.txt") `
  --context-file (Join-Path $TaskDir "context.txt") `
  --model gpt-5.5 `
  --remote-api-key-ref env:OPENAI_API_KEY `
  --context-sensitivity private `
  --operator-approved
```

Secret-classified context is rejected for remote execution even when an API key exists.

## Reviewable worktree and self-correction flow

Create a worktree plan:

```powershell
$WorktreePlan = ".hex-cortex\coding-tasks\task-001\worktree-plan.json"
$WorktreeRoot = Join-Path (Split-Path $PWD -Parent) "HEX-CORTEX-worktrees"

hexcortex-code worktree-plan `
  "$PWD" `
  "$WorktreeRoot" `
  candidate-001 `
  main `
  --check pytest `
  --check ruff `
  --output "$WorktreePlan"
```

Create it only after review:

```powershell
hexcortex-code worktree-create `
  "$WorktreePlan" `
  --operator-approved
```

A proposed patch must be stored as a file and its SHA-256 reviewed before application:

```powershell
$PatchPath = ".hex-cortex\coding-tasks\task-001\candidate.patch"
$PatchHash = (Get-FileHash "$PatchPath" -Algorithm SHA256).Hash.ToLowerInvariant()
$CandidateWorktree = Join-Path $WorktreeRoot "candidate-001"

hexcortex-code patch-apply `
  "$CandidateWorktree" `
  "$PatchPath" `
  "$PatchHash" `
  --operator-approved

hexcortex-code worktree-check `
  "$CandidateWorktree" `
  --check pytest `
  --check ruff `
  --operator-approved
```

No command performs an automatic merge.

## Persistent research hypothesis ledger

```powershell
$Hypotheses = ".hex-cortex\research\hypotheses.jsonl"

hexcortex-code hypothesis-add `
  "$Hypotheses" `
  "Spatial pooling improves held-out action ranking." `
  "main@957d0eb" `
  "screen_lab_policy_v2_gate" `
  --created-by hex-cortex

hexcortex-code hypothesis-frontier "$Hypotheses"
```

Outcomes become merge-eligible only when marked validated, with a positive metric delta and a passing held-out gate; an operator merge is still required.

## Safety invariants

- no unrestricted shell through MCP;
- no automatic merge;
- no evaluator mutation;
- no threshold reduction to make a candidate pass;
- no raw secret or full agent-memory persistence;
- every patch is hash-checked and applied in an isolated worktree;
- only allowlisted checks can execute;
- held-out evaluation and operator approval remain mandatory.
