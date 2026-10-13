"""Read-only health and skill maturity view over the EXISTING skill pipeline.

A declarative active index is not a signed attestation of real model gains.
No hidden installation, activation, shell or network operations.
"""
from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.cortex_active_skill_index import (
    CORTEX_ACTIVE_SKILL_INDEX_FILENAME, CortexActiveSkillIndexJsonlStore,
)
from hex_cortex.memory.cortex_manual_skill_activation import (
    CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME, CortexManualSkillActivationJsonlStore,
)
from hex_cortex.memory.cortex_procedural_skill_evidence_v25 import (
    EVIDENCE_FILENAME, assess_skill_evidence,
)
from hex_cortex.memory.cortex_skill_activation_apply import (
    CORTEX_SKILL_ACTIVATION_APPLY_FILENAME, CortexSkillActivationApplyJsonlStore,
)
from hex_cortex.memory.cortex_skill_activation_gate import (
    CORTEX_SKILL_ACTIVATION_GATE_FILENAME, CortexSkillActivationGateJsonlStore,
)
from hex_cortex.memory.cortex_skill_candidate import (
    CORTEX_SKILL_CANDIDATE_FILENAME, CortexSkillCandidateJsonlStore,
)
from hex_cortex.memory.cortex_skill_library import (
    CORTEX_SKILL_LIBRARY_FILENAME, CortexSkillLibraryJsonlStore,
)
from hex_cortex.memory.cortex_skill_usage_history import (
    CORTEX_SKILL_USAGE_HISTORY_FILENAME, CortexSkillUsageHistoryJsonlStore,
)


def audit_skill_profile(profile: Path) -> dict[str, object]:
    root = Path(profile).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("skill_profile_must_be_directory")
    files = (
        CORTEX_SKILL_CANDIDATE_FILENAME, CORTEX_SKILL_LIBRARY_FILENAME,
        CORTEX_SKILL_ACTIVATION_GATE_FILENAME,
        CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME,
        CORTEX_SKILL_ACTIVATION_APPLY_FILENAME,
        CORTEX_ACTIVE_SKILL_INDEX_FILENAME,
        CORTEX_SKILL_USAGE_HISTORY_FILENAME, EVIDENCE_FILENAME,
    )
    for filename in files:
        path = root / filename
        if path.is_symlink() or (path.exists() and (
            not path.is_file() or path.stat().st_size > 1_000_000
        )):
            raise ValueError("skill_profile_unsafe_record_file")

    candidates = CortexSkillCandidateJsonlStore(
        root / CORTEX_SKILL_CANDIDATE_FILENAME
    ).load()
    library = CortexSkillLibraryJsonlStore(
        root / CORTEX_SKILL_LIBRARY_FILENAME
    ).load()
    gates = CortexSkillActivationGateJsonlStore(
        root / CORTEX_SKILL_ACTIVATION_GATE_FILENAME
    ).load()
    manual = CortexManualSkillActivationJsonlStore(
        root / CORTEX_MANUAL_SKILL_ACTIVATION_FILENAME
    ).load()
    applies = CortexSkillActivationApplyJsonlStore(
        root / CORTEX_SKILL_ACTIVATION_APPLY_FILENAME
    ).load()
    indexes = CortexActiveSkillIndexJsonlStore(
        root / CORTEX_ACTIVE_SKILL_INDEX_FILENAME
    ).load()
    usage = CortexSkillUsageHistoryJsonlStore(
        root / CORTEX_SKILL_USAGE_HISTORY_FILENAME
    ).load()
    last_index = indexes[-1] if indexes else None
    procedural = [
        assess_skill_evidence(project_root=root, skill_id=skill_id)
        for skill_id in (
            "multiply_decomposition",
            "fraction_reduction",
            "addition_compensation",
        )
    ]
    return {
        "status": "read_only_skill_inventory",
        "profile_path": str(root),
        "candidate_records": len(candidates),
        "promotable_candidate_records": sum(
            bool(x.promote_to_library and x.candidate_allowed) for x in candidates
        ),
        "library_records": len(library),
        "library_registered": sum(bool(x.library_allowed) for x in library),
        "activation_gates": len(gates),
        "operator_activation_choices": len(manual),
        "explicit_activate_choices": sum(
            bool(x.operator_choice == "activate" and x.manual_allowed) for x in manual
        ),
        "applied_records": len(applies),
        "declared_activated_applications": sum(
            bool(x.apply_allowed and x.effective_active) for x in applies
        ),
        "active_index_records": len(indexes),
        "latest_declared_active_skills": list(
            last_index.active_skill_keys if last_index and last_index.index_allowed else []
        ),
        "usage_history_records": len(usage),
        "procedural_skill_trial_statuses": procedural,
        "actual_model_skill_gain_independently_attested": False,
        "active_index_external_signature_verified": False,
        "automatic_activation_performed": False,
        "model_called": False,
        "files_modified": False,
    }
