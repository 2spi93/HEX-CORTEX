# HEX-CORTEX V29 — Source-evidence coding and prospective world drift guard

## Why this integration exists

Operator Windows V28: **1947 tests passed**, Ruff clean. Real local
Qwen2.5-coder:7b produced a valid JSON plan with 3 proposed changes, but
each proposed change had \`file: null\` even though the candidate file was
correct. \`plan_grounding_ratio: 1.0\` only reflected a different grounded
field; it was **not** grounded evidence for the changes. Specifically:
- proposed new non-finite input handling for \`_finite_vector\` even
  though its AST already included \`isfinite\` + \`ValueError\`;
- proposed adding a docstring to \`run_universal_world_advisory\` even
  though its AST already contains a docstring;
- suggested unspecified tests, without reading test files or verifying
  actual coverage.

The world stress simulator found a bias correction that helped in stable
synthetic dynamics, but its normalized mean error rose from 0 to
0.359765625 when the hidden bias vanished and from 0.359765625 to
1.4390625 when the hidden bias reversed. No real sensor was used.

## V29 changes

1. **Independent coding evidence gate** built on the existing code review:
   compare every proposed change's path to the one approved file; check
   whether the proposal explicitly refers to a function in its AST;
   flag possible duplication of existing finite-value guards and
   existing docstrings, using only static evidence. The gate reports
   **grounded_proposal_count** and each proposal's \`file_grounded\`,
   \`potentially_redundant_with_ast\`, \`behavior_proven: false\`,
   \`test_coverage_audited: false\`. The legacy
   \`plan_grounding_ratio\` remains an output for compatibility; it is
   NOT a substitute for the new per-proposal checks.
2. **World prospective lagged-feedback gate:** compare baseline and
   corrected errors from a short history of at least three previously
   completed operator-supplied transitions, then choose the prediction
   for the **NEXT virtual step**. If recent corrected predictions
   performed worse, explicitly fall back to the uncorrected simulator.
   Never use the next step's future observed state to make the decision.
   Refuse missing, malformed and duplicated history. This is a
   deterministic **rolling-error heuristic**, **not** the ADWIN or
   Page-Hinkley statistical drift detector.
3. Wire the optional next-step gate into the already existing V28
   stress CLI, preserving the original baseline/shift benchmark and
   requiring a second explicit \`--approve-next-prediction\` flag.
4. No actual code edits, command execution, source publication,
   learning on real sensors, active model update or physical device
   action.

## External reference checks

- Official Ollama local structured-output documentation confirms JSON
  schema support and recommends validating the parsed results:
  https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx
- River's original Page-Hinkley/ADWIN modules are examples of formal
  *online concept drift* algorithms and explain why drift must be
  monitored over time:
  https://github.com/online-ml/river/blob/main/river/drift/page_hinkley.py
  https://github.com/online-ml/river/blob/main/river/drift/adwin.py
  **Neither library nor algorithm was implemented in V29.**
- OWASP's secure AI coding guidance says repository sources and
  generated outputs can contain malicious instructions and recommends
  strict action boundaries:
  https://cheatsheetseries.owasp.org/cheatsheets/Secure_Coding_with_AI_Cheat_Sheet.html
- NIST's testing/evaluation guidance supports treating measurement,
  validation and monitoring as distinct lifecycle activities:
  https://airc.nist.gov/

## Windows PowerShell operator commands (single physical line each)

Synchronize, test and lint:

~~~powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
~~~

Re-run one CPU-only Qwen Coder 7B AST-based read-only review and check
\`review_evidence\`, not just \`plan_grounding_ratio\`:

~~~powershell
python -m hex_cortex.memory.cortex_code_review_cli_v26 --project-root . --file src/hex_cortex/memory/cortex_universal_world_loop_v26.py --model qwen2.5-coder:7b --approve-read --approve-model --max-tokens 1536
~~~

Perform the synthetic world stress and separate next-step guard test
with **NO real LLM calls, hardware, GPU, saving or internet**:

~~~powershell
python -m hex_cortex.memory.cortex_world_shift_stress_cli_v28 --approve-stress --approve-next-prediction
~~~

Expected in this deterministic toy suite: stable dynamics allow a
corrected next virtual prediction, while vanished/reversed biases
fall back to the baseline. A detector that reacts after observations
CANNOT prevent harm on the *first unobserved changed step*. No robust
real-time control claim should be made.

## Priority beyond V29

Use genuine independently sourced, time-stamped datasets with
calibration and uncertainty; assess latency-to-detect, false alarms,
grouped train/test splits and change-points. For code review, inspect
relevant unit tests with their own explicit approval and verify suggested
fixes by sandboxed tests before any human-approved patch. No unbounded
autonomous file edits or device controls should be enabled.
