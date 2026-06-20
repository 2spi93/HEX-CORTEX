from hex_cortex.memory.cortex_cognitive_residuals import build_residual_signature


def test_residual_signature_excludes_context_and_model_identity() -> None:
    signature = build_residual_signature(
        failure_class="logic_error",
        domain="hex-cortex",
        best_corrective_intervention="run_tests",
    )
    repeated = build_residual_signature(
        failure_class="logic_error",
        domain="hex-cortex",
        best_corrective_intervention="run_tests",
    )

    assert signature == repeated
    assert len(signature) == 64
