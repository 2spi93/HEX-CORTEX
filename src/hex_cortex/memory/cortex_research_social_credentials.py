from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import urlparse

_SECRET_SCHEMES = {"env", "keyring", "vault", "docker-secret", "systemd-credential"}
_PROVIDER_CATALOG = {
    "telegram": {
        "auth_mode": "bot_token",
        "default_mode": "read",
        "read_scopes": ["updates.read"],
        "write_scopes": ["messages.send"],
        "callback_mode": "webhook_or_long_polling",
    },
    "linkedin": {
        "auth_mode": "oauth2_authorization_code",
        "default_mode": "read",
        "read_scopes": ["profile.read"],
        "write_scopes": ["content.write"],
        "callback_mode": "https_callback",
    },
    "instagram": {
        "auth_mode": "oauth2",
        "default_mode": "read",
        "read_scopes": ["profile.read", "media.read"],
        "write_scopes": ["content.publish"],
        "callback_mode": "https_callback",
    },
    "reddit": {
        "auth_mode": "oauth2",
        "default_mode": "read",
        "read_scopes": ["identity", "read"],
        "write_scopes": ["submit", "privatemessages"],
        "callback_mode": "https_callback",
    },
}
_SOURCE_QUALITY = {
    "official": 1.0,
    "primary": 0.92,
    "research": 0.88,
    "reputable_news": 0.78,
    "community": 0.58,
    "unknown": 0.45,
}


def build_research_social_plan() -> dict[str, object]:
    return {
        "plan_type": "research_social_credentials_v1",
        "search_stack": {
            "search_engine": "searxng",
            "search_endpoint": "http://127.0.0.1:8888/search",
            "search_output_format": "json",
            "crawler": "crawl4ai",
            "crawler_endpoint": "http://127.0.0.1:11235/crawl",
            "network_local_only_by_default": True,
        },
        "ranking": {
            "quality_weight": 0.5,
            "freshness_weight": 0.3,
            "diversity_weight": 0.2,
            "official_sources_preferred": True,
            "citation_required": True,
        },
        "credential_policy": {
            "allowed_secret_ref_schemes": sorted(_SECRET_SCHEMES),
            "raw_secret_persistence_allowed": False,
            "read_only_first": True,
            "write_requires_operator_approval": True,
            "rotation_health_checks_required": True,
        },
        "providers": list_social_providers(),
        "next_action": "start_research_services_and_connect_read_only_provider",
    }


def list_social_providers() -> list[dict[str, object]]:
    return [
        {"provider": name, **dict(config)}
        for name, config in sorted(_PROVIDER_CATALOG.items())
    ]


def validate_secret_ref(secret_ref: str) -> dict[str, object]:
    parsed = urlparse(secret_ref)
    valid = parsed.scheme in _SECRET_SCHEMES and bool(parsed.netloc or parsed.path)
    return {
        "secret_ref": secret_ref if valid else None,
        "secret_scheme": parsed.scheme or None,
        "secret_ref_valid": valid,
        "secret_value_read": False,
        "secret_value_persisted": False,
        "blockers": [] if valid else ["secret_ref_invalid"],
    }


def build_provider_connection_receipt(
    *,
    provider: str,
    secret_ref: str,
    requested_mode: str = "read",
    operator_approved: bool = False,
) -> dict[str, object]:
    config = _PROVIDER_CATALOG.get(provider)
    secret = validate_secret_ref(secret_ref)
    blockers = list(secret["blockers"])
    if config is None:
        blockers.append("provider_unknown")
    if requested_mode not in {"read", "write"}:
        blockers.append("requested_mode_invalid")
    if requested_mode == "write" and not operator_approved:
        blockers.append("write_requires_operator_approval")
    scopes: list[str] = []
    if config is not None and requested_mode in {"read", "write"}:
        scopes.extend(config["read_scopes"])
        if requested_mode == "write":
            scopes.extend(config["write_scopes"])
    allowed = not blockers
    stable = {
        "provider": provider,
        "secret_ref": secret.get("secret_ref"),
        "requested_mode": requested_mode,
        "operator_approved": operator_approved,
        "scopes": sorted(set(scopes)),
        "allowed": allowed,
        "blockers": blockers,
    }
    return {
        "receipt_type": "provider_connection_receipt",
        "provider": provider,
        "auth_mode": config.get("auth_mode") if config else None,
        "callback_mode": config.get("callback_mode") if config else None,
        "requested_mode": requested_mode,
        "operator_approved": operator_approved,
        "scopes": sorted(set(scopes)),
        "connection_allowed": allowed,
        "network_call_performed": False,
        "messages_read": False,
        "content_published": False,
        "secret_ref": secret.get("secret_ref"),
        "secret_value_read": False,
        "secret_value_persisted": False,
        "blockers": blockers,
        "receipt_hash": _stable_hash(stable),
        "next_action": "run_provider_health_check" if allowed else "repair_provider_connection",
    }


def rank_research_results(
    rows: list[dict[str, object]],
    *,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    reference = now or datetime.now(UTC)
    seen_domains: dict[str, int] = {}
    scored = []
    for position, row in enumerate(rows):
        url = str(row.get("url", ""))
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        domain = parsed.hostname.lower()
        source_type = str(row.get("source_type", "unknown"))
        quality = _SOURCE_QUALITY.get(source_type, _SOURCE_QUALITY["unknown"])
        freshness = _freshness_score(row.get("updated_at"), reference)
        duplicate_count = seen_domains.get(domain, 0)
        diversity = max(0.2, 1.0 - (duplicate_count * 0.25))
        seen_domains[domain] = duplicate_count + 1
        score = round((quality * 0.5) + (freshness * 0.3) + (diversity * 0.2), 4)
        scored.append(
            {
                **row,
                "domain": domain,
                "quality_score": quality,
                "freshness_score": freshness,
                "diversity_score": diversity,
                "ranking_score": score,
                "original_position": position,
            }
        )
    return sorted(
        scored,
        key=lambda item: (-float(item["ranking_score"]), int(item["original_position"])),
    )


def build_citation_pack(
    *,
    query: str,
    rows: list[dict[str, object]],
    max_items: int = 8,
) -> dict[str, object]:
    if max_items < 1 or max_items > 20:
        raise ValueError("max_items must be in [1, 20]")
    ranked = rank_research_results(rows)[:max_items]
    citations = []
    for row in ranked:
        snippet = str(row.get("snippet", ""))[:800]
        citations.append(
            {
                "title": str(row.get("title", ""))[:240],
                "url": row.get("url"),
                "domain": row.get("domain"),
                "source_type": row.get("source_type", "unknown"),
                "ranking_score": row.get("ranking_score"),
                "observed_content_hash": hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
                "snippet": snippet,
            }
        )
    return {
        "pack_type": "citation_pack",
        "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "query_persisted": False,
        "citation_count": len(citations),
        "citations": citations,
        "raw_page_content_persisted": False,
        "citation_required": True,
        "pack_allowed": bool(citations),
        "blockers": [] if citations else ["no_ranked_citations"],
        "pack_hash": _stable_hash({"query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest(), "citations": citations}),
    }


def _freshness_score(value: object, reference: datetime) -> float:
    if not isinstance(value, str) or not value.strip():
        return 0.4
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0.4
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    age_days = max((reference - observed.astimezone(UTC)).total_seconds() / 86400, 0)
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.82
    if age_days <= 90:
        return 0.62
    if age_days <= 365:
        return 0.42
    return 0.25


def _stable_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
