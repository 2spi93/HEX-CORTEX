from hex_cortex.memory.cortex_ci_artifact_export import CORTEX_CI_ARTIFACT_EXPORT_FILENAME
from hex_cortex.memory.cortex_ci_artifact_export import CortexCiArtifactExportRecord


def test_ci_artifact_export_imports() -> None:
    assert CORTEX_CI_ARTIFACT_EXPORT_FILENAME == "cortex-ci-artifact-export.json"
    assert CortexCiArtifactExportRecord.__name__ == "CortexCiArtifactExportRecord"
