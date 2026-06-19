from __future__ import annotations


def analyze_cortex_project_fit(
    *,
    project_id: str,
    existing_capabilities: list[str],
    proposed_capabilities: list[str],
) -> dict[str, object]:
    existing = set(existing_capabilities)
    proposed = set(proposed_capabilities)
    overlap = sorted(existing.intersection(proposed))
    additions = sorted(proposed.difference(existing))
    mode = "federated_read_only" if overlap else "bounded_extension"
    return {
        "analysis_type": "cortex_project_fit",
        "project_id": project_id,
        "integration_mode": mode,
        "overlapping_capabilities": overlap,
        "extension_capabilities": additions,
        "shared_memory": False,
        "shared_history": False,
        "project_remains_source_of_truth": True,
        "next_action": (
            "build_read_only_capability_adapter"
            if overlap
            else "build_extension_adapter"
        ),
    }
