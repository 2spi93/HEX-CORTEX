from __future__ import annotations

_DOMAIN_CANDIDATES = [
    {
        "domain_id": "enterprise_management",
        "label": "Gestion d'entreprise",
        "state": "candidate",
        "scope": "strategy, finance, operations, leadership, organization",
    },
    {
        "domain_id": "security_and_cyber",
        "label": "Securite et cyber",
        "state": "candidate",
        "scope": "defensive security, audit, hardening, risk, incident review",
    },
    {
        "domain_id": "software_development_all_types",
        "label": "Tout type de developpement logiciel",
        "state": "candidate",
        "scope": "frontend, backend, data, ai, devops, tests, architecture",
    },
    {
        "domain_id": "screen_vision",
        "label": "Vision ecran",
        "state": "candidate",
        "scope": "screen reading, UI understanding, visual debugging",
    },
    {
        "domain_id": "camera_vision",
        "label": "Vision camera",
        "state": "candidate",
        "scope": "camera frames, scene understanding, operator-approved capture",
    },
    {
        "domain_id": "voice_io",
        "label": "Voix",
        "state": "candidate",
        "scope": "speech input, speech output, transcript receipts",
    },
    {
        "domain_id": "multimodal_world_model",
        "label": "World model multimodal",
        "state": "candidate",
        "scope": "latent state, memory, prediction, planning, surprise detection",
    },
]


def list_cortex_domain_candidates() -> list[dict[str, object]]:
    return [dict(item) for item in _DOMAIN_CANDIDATES]


def get_cortex_domain_candidate(domain_id: str) -> dict[str, object]:
    for item in _DOMAIN_CANDIDATES:
        if item["domain_id"] == domain_id:
            return dict(item)
    return {
        "domain_id": domain_id,
        "state": "blocked",
        "blocker": "unknown_domain_candidate",
    }
