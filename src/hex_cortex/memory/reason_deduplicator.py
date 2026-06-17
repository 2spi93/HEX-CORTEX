"""Utilities for stable reason de-duplication."""

from __future__ import annotations


def deduplicate_reasons(reasons: list[str]) -> list[str]:
    """Return reasons with stable ordering and duplicate values removed."""

    seen: set[str] = set()
    unique: list[str] = []
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        unique.append(reason)
    return unique


def reason_dedup_report(reasons: list[str]) -> dict[str, object]:
    """Build a small report for a reason list."""

    unique = deduplicate_reasons(reasons)
    return {
        "input_count": len(reasons),
        "output_count": len(unique),
        "removed_count": len(reasons) - len(unique),
        "reasons": unique,
    }
