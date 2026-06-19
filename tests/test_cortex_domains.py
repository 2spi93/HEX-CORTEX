from hex_cortex.memory.cortex_domains import get_cortex_domain_candidate
from hex_cortex.memory.cortex_domains import list_cortex_domain_candidates


def test_domain_candidates_include_requested_expertise() -> None:
    rows = list_cortex_domain_candidates()
    ids = {row["domain_id"] for row in rows}

    assert "enterprise_management" in ids
    assert "security_and_cyber" in ids
    assert "software_development_all_types" in ids
    assert "engineering_profile" in ids
    assert "philosophy" in ids
    assert "media_generation" in ids
    assert "spatial_3d_reasoning" in ids
    assert "multimodal_world_model" in ids


def test_get_domain_candidate() -> None:
    payload = get_cortex_domain_candidate("security_and_cyber")

    assert payload["state"] == "candidate"
    assert payload["label"] == "Securite et cyber"


def test_engineering_profile_candidate() -> None:
    payload = get_cortex_domain_candidate("engineering_profile")

    assert payload["state"] == "candidate"
    assert "verification" in payload["scope"]


def test_unknown_domain_candidate_blocks() -> None:
    payload = get_cortex_domain_candidate("unknown")

    assert payload["state"] == "blocked"
    assert payload["blocker"] == "unknown_domain_candidate"
