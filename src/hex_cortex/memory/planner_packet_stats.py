"""Compact statistics from planner packets."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

PLANNER_STATS_FILENAME = "planner-packet-stats.jsonl"
PACKET_FILENAME = "planner-decision-packet.jsonl"


def build_planner_packet_stats(profile: Path) -> dict[str, object]:
    packets = _load_jsonl(profile / PACKET_FILENAME)
    record = _record(profile, packets)
    stats_path = profile / PLANNER_STATS_FILENAME
    records = _load_jsonl(stats_path)
    records.append(record)
    _save_jsonl(stats_path, records)
    return {
        "stats_type": "planner_packet_stats",
        "profile_path": str(profile),
        "stats_path": str(stats_path),
        "stats_count": len(records),
        "stats_record": record,
    }


def summarize_planner_packet_stats(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else {}
    return {
        "inspect_type": "planner_packet_stats",
        "path": str(path),
        "exists": path.exists(),
        "total_stats_count": len(records),
        "latest_dominant_status": latest.get("dominant_status"),
        "latest_recommended_action": latest.get("recommended_action"),
        "latest_packet_score": latest.get("packet_score"),
        "latest_missing_skills": latest.get("missing_skills", []),
    }


def _record(profile: Path, packets: list[dict[str, object]]) -> dict[str, object]:
    if not packets:
        return {
            "profile_path": str(profile),
            "source_packet_count": 0,
            "dominant_status": "missing",
            "dominant_next_action": "build_planner_decision_packet",
            "missing_skills": [],
            "packet_score": 0.0,
            "recommended_action": "build_planner_decision_packet",
        }
    statuses = Counter(str(packet.get("planner_status")) for packet in packets)
    next_actions = Counter(str(packet.get("next_action")) for packet in packets)
    fallback_packets = [
        packet for packet in packets if packet.get("registry_status") == "fallback"
    ]
    missing_skills = sorted(
        {str(packet.get("selected_skill")) for packet in fallback_packets}
    )
    packet_score = 0.0 if missing_skills else 1.0
    return {
        "profile_path": str(profile),
        "source_packet_count": len(packets),
        "dominant_status": statuses.most_common(1)[0][0],
        "dominant_next_action": next_actions.most_common(1)[0][0],
        "missing_skills": missing_skills,
        "packet_score": packet_score,
        "recommended_action": _recommended_action(missing_skills, statuses),
    }


def _recommended_action(missing_skills: list[str], statuses: Counter[str]) -> str:
    if missing_skills:
        return "register_or_activate_missing_skills"
    if statuses.get("ready", 0):
        return "review_ready_planner_path"
    if statuses.get("blocked", 0):
        return "inspect_blocked_planner_packets"
    return "continue_planner_observation"


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _save_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(f"{json.dumps(record, sort_keys=True)}\n")
