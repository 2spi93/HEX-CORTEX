from datetime import UTC, datetime

from hex_cortex.memory.cortex_research_social_credentials import build_citation_pack
from hex_cortex.memory.cortex_research_social_credentials import build_provider_connection_receipt
from hex_cortex.memory.cortex_research_social_credentials import build_research_social_plan
from hex_cortex.memory.cortex_research_social_credentials import rank_research_results
from hex_cortex.memory.cortex_research_social_credentials import validate_secret_ref


def test_research_plan_is_local_private_and_citation_first() -> None:
    plan = build_research_social_plan()

    assert plan["search_stack"]["search_engine"] == "searxng"
    assert plan["search_stack"]["crawler"] == "crawl4ai"
    assert plan["search_stack"]["network_local_only_by_default"] is True
    assert plan["ranking"]["citation_required"] is True
    assert plan["credential_policy"]["raw_secret_persistence_allowed"] is False


def test_secret_ref_accepts_keyring_and_rejects_raw_value() -> None:
    valid = validate_secret_ref("keyring://hex-cortex/telegram/main")
    invalid = validate_secret_ref("plain-secret-value")

    assert valid["secret_ref_valid"] is True
    assert valid["secret_value_read"] is False
    assert invalid["secret_ref_valid"] is False


def test_provider_write_requires_operator_approval() -> None:
    blocked = build_provider_connection_receipt(
        provider="telegram",
        secret_ref="keyring://hex-cortex/telegram/main",
        requested_mode="write",
    )
    allowed = build_provider_connection_receipt(
        provider="telegram",
        secret_ref="keyring://hex-cortex/telegram/main",
        requested_mode="write",
        operator_approved=True,
    )

    assert blocked["connection_allowed"] is False
    assert "write_requires_operator_approval" in blocked["blockers"]
    assert allowed["connection_allowed"] is True
    assert allowed["secret_value_persisted"] is False
    assert "messages.send" in allowed["scopes"]


def test_ranking_prefers_fresh_official_source() -> None:
    now = datetime(2026, 6, 19, tzinfo=UTC)
    rows = [
        {
            "title": "Community note",
            "url": "https://community.example/post",
            "snippet": "secondary",
            "source_type": "community",
            "updated_at": "2025-01-01T00:00:00+00:00",
        },
        {
            "title": "Official documentation",
            "url": "https://docs.example/reference",
            "snippet": "primary",
            "source_type": "official",
            "updated_at": "2026-06-18T00:00:00+00:00",
        },
    ]

    ranked = rank_research_results(rows, now=now)

    assert ranked[0]["title"] == "Official documentation"
    assert ranked[0]["ranking_score"] > ranked[1]["ranking_score"]


def test_citation_pack_hashes_observed_content_and_limits_context() -> None:
    pack = build_citation_pack(
        query="local runtime",
        rows=[
            {
                "title": "Official docs",
                "url": "https://docs.example/runtime",
                "snippet": "x" * 1200,
                "source_type": "official",
                "updated_at": "2026-06-18T00:00:00+00:00",
            }
        ],
    )

    assert pack["pack_allowed"] is True
    assert pack["query_persisted"] is False
    assert pack["raw_page_content_persisted"] is False
    assert len(pack["citations"][0]["snippet"]) == 800
    assert len(pack["citations"][0]["observed_content_hash"]) == 64
