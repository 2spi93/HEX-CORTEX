from hex_cortex.memory.cortex_ci_evidence_export_plan import CORTEX_CI_EVIDENCE_EXPORT_PLAN_FILENAME


def test_ci_evidence_export_plan_imports() -> None:
    assert CORTEX_CI_EVIDENCE_EXPORT_PLAN_FILENAME == "cortex-ci-evidence-export-plan.jsonl"
