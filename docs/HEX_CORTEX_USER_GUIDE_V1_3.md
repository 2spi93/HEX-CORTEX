# HEX-CORTEX v1.3 User Guide

## Status

- Release report: `RELEASE_HEX_CORTEX_V1_3_INTERACTIVE_COCKPIT.md`
- Release tag: `hex-cortex-v1.3-interactive-cockpit`
- Test summary: `480 passed`
- Evidence export workflow: `.github\workflows\hex-cortex-ci-evidence.yml`
- Evidence name: `hex-cortex-v1-3-evidence`
- Docs hash: `778cde8d1bcceee8c492b2993ca355800df959a4695bace77095ef32e72cc956`

## Run the interactive cockpit

1. Run the tests:

```powershell
python -m pytest
```

2. Rebuild the cockpit data API when evidence changes:

```powershell
python -m hex_cortex.memory.cortex_cockpit_data_api_cli .hex-cortex --pretty
```

3. Rebuild or reopen the interactive cockpit:

```powershell
python -m hex_cortex.memory.cortex_interactive_cockpit_shell_cli .hex-cortex --pretty
start .\artifacts\hex-cortex-interactive-cockpit\index.html
```

## Interpret the cockpit

- `Best routed skill` is the skill currently selected as strongest for the latest architecture loop.
- `Feedback score` aggregates routing quality, skill-use success, guidance quality, outcome usefulness, and closeout stability.
- `Active skills` is the count of skills currently available to the controlled skill loop.
- `Evidence drilldown` contains the full embedded evidence payload used by the cockpit.

## Refresh controls

- Use `Refresh cockpit` after regenerating local evidence.
- Use auto-refresh only for short local review sessions.
- The cockpit is static/local-first, so refresh reloads the page rather than starting a server.

## CI evidence export

The CI evidence workflow exports these paths:

- `RELEASE_HEX_CORTEX_V1_3_INTERACTIVE_COCKPIT.md`
- `artifacts/hex-cortex-ci/**`
- `artifacts/hex-cortex-ui-cockpit/**`
- `artifacts/hex-cortex-interactive-cockpit/**`

The exported evidence is intended for release review and audit, not for runtime state mutation.

## Product hardening notes

Generated runtime folders such as `.hex-cortex/` and `artifacts/` should remain local or CI-exported unless a release explicitly decides to track them.

## Next action

`plan_operator_ui_wording_polish`
