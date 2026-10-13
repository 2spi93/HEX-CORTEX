"""Deterministic V29 evidence checks on suggestions, not LLM self-confidence.

A path/JSON check cannot establish that a requested change is needed.
Check the approved file's AST for exact named anchors and existing basic
guards/docstrings; never claim the implementation or test coverage is proven.
"""
from __future__ import annotations

import re


def check_code_review_evidence(
    plan: dict[str, object] | None,
    *,
    selected_file: str,
    structure: dict[str, object],
    source_disclosed: bool,
) -> dict[str, object]:
    if not isinstance(plan, dict):
        return {
            "status": "not_assessable", "proposal_count": 0,
            "grounded_proposal_count": 0, "has_actionable_evidence": False,
            "source_disclosed": source_disclosed, "warnings": [],
        }
    raw = plan.get("proposed_changes")
    proposed = raw if isinstance(raw, list) else []
    functions = {
        row["name"]: row for row in structure.get("functions", [])
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    evidence: list[dict[str, object]] = []
    for index, row in enumerate(proposed[:20]):
        if not isinstance(row, dict):
            continue
        path = row.get("file")
        text = str(row.get("objective", "")) + " " + str(row.get("change", ""))
        named = sorted(
            name for name in functions
            if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text)
        )
        redundant: list[str] = []
        text_lower = text.casefold()
        for name in named:
            function = functions[name]
            calls = function.get("calls", [])
            if (
                any(term in text_lower for term in (
                    "non-finite", "nonfinite", "not finite",
                    "non finite", "isfinite",
                ))
                and "isfinite" in calls and "ValueError" in calls
            ):
                redundant.append(f"{name}:finite_guard_already_present_in_ast")
            if (
                "docstring" in text_lower
                and function.get("has_docstring") is True
            ):
                redundant.append(f"{name}:docstring_already_present_in_ast")
        anchored = path == selected_file and bool(named)
        evidence.append({
            "index": index,
            "file_grounded": path == selected_file,
            "named_functions_in_approved_ast": named,
            "potentially_redundant_with_ast": redundant,
            "structurally_anchored": anchored,
            "candidate_for_human_review": (
                anchored and not redundant and source_disclosed
            ),
            "behavior_proven": False,
            "test_coverage_audited": False,
        })
    human_review_candidates = sum(bool(row["candidate_for_human_review"]) for row in evidence)
    anchored_count = sum(bool(row["structurally_anchored"]) for row in evidence)
    flags: list[str] = []
    if proposed and not anchored_count:
        flags.append("no_proposed_change_references_both_allowed_file_and_known_function")
    if any(row["potentially_redundant_with_ast"] for row in evidence):
        flags.append("some_proposals_may_duplicate_existing_guards_or_docstrings")
    if not source_disclosed:
        flags.append("source_body_not_disclosed_to_model")
    if proposed:
        flags.append("test_coverage_not_verified_from_repository")
    return {
        "status": "source_proposal_needs_review" if human_review_candidates
        else "insufficient_verified_review_evidence",
        "proposal_count": len(evidence),
        "grounded_proposal_count": anchored_count,
        "human_review_candidate_count": human_review_candidates,
        "has_actionable_evidence": False,
        "source_disclosed": source_disclosed,
        "warnings": flags,
        "proposals": evidence,
        "independently_verified_code_fix": False,
    }
