from __future__ import annotations

_LINKS = [
    {
        "link_id": "formal_math_link",
        "state": "candidate",
        "scope": "formal reasoning, math workflow, proof-oriented review",
        "default_mode": "manual_until_receipts",
    },
    {
        "link_id": "repo_coding_link_a",
        "state": "candidate",
        "scope": "repository coding, tests, lint, branch-first implementation",
        "default_mode": "assisted_until_trusted_plan",
    },
    {
        "link_id": "repo_coding_link_b",
        "state": "candidate",
        "scope": "repository review, refactor, coding workflow, validation",
        "default_mode": "assisted_until_trusted_plan",
    },
    {
        "link_id": "tool_protocol_link",
        "state": "candidate",
        "scope": "schema-first external tools and resources",
        "default_mode": "manual_until_tool_policy",
    },
]


def list_cortex_links() -> list[dict[str, object]]:
    return [dict(item) for item in _LINKS]


def get_cortex_link(link_id: str) -> dict[str, object]:
    for item in _LINKS:
        if item["link_id"] == link_id:
            return dict(item)
    return {
        "link_id": link_id,
        "state": "blocked",
        "blocker": "unknown_link_candidate",
    }
