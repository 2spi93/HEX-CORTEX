"""Read-only overlap graph on existing V1 observed visual transitions.

Every transition contributes both its *current* and *next* image hashes.
Transitions sharing either image become one connected component. This
detects exact-image leakage missed by per-row or random sample splits.

Only indexes / SHA256-of-hashes are exposed, never image paths/raw media.
No split reassignment: the active checkpoint has ALREADY seen its data,
so retrospectively changing labels CANNOT produce independent evidence.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence

_SPLITS = ("train", "validation", "test")


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def inspect_visual_overlap_graph(
    records: Sequence[dict[str, object]], *,
    approved: bool = False,
) -> dict[str, object]:
    if not approved:
        return {
            "status": "blocked",
            "reason": "visual_overlap_graph_approval_required",
            "records_inspected": 0,
            "files_written": False,
        }
    if not isinstance(records, (list, tuple)) or not 1 <= len(records) <= 5000:
        raise ValueError("visual_graph_record_count_invalid")
    parent = list(range(len(records)))
    size = [1] * len(records)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        aa, bb = find(a), find(b)
        if aa != bb:
            if size[aa] < size[bb]:
                aa, bb = bb, aa
            parent[bb] = aa
            size[aa] += size[bb]

    first: dict[str, int] = {}
    image_lines: dict[str, set[int]] = defaultdict(set)
    sample_ids: set[str] = set()
    for i, row in enumerate(records):
        if not isinstance(row, dict) or row.get("split") not in _SPLITS:
            raise ValueError("visual_graph_invalid_split")
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in sample_ids:
            raise ValueError("visual_graph_invalid_or_duplicate_sample_id")
        sample_ids.add(sample_id)
        current, nxt = row.get("current_image_hash"), row.get("next_image_hash")
        for image_hash in (current, nxt):
            if (
                not isinstance(image_hash, str) or len(image_hash) != 64
                or any(char not in "0123456789abcdef" for char in image_hash)
            ):
                raise ValueError("visual_graph_invalid_sha256_image_hash")
            if image_hash in first:
                union(i, first[image_hash])
            else:
                first[image_hash] = i
            image_lines[image_hash].add(i + 1)
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        groups[find(index)].append(index)
    sizes = sorted((len(members) for members in groups.values()), reverse=True)
    crossed = []
    impacted: set[int] = set()
    for members in groups.values():
        splits = sorted({records[i]["split"] for i in members})
        if len(splits) > 1:
            impacted.update(i + 1 for i in members)
            crossed.append({
                "component_id": _hash(sorted(
                    h for h, image_members in image_lines.items()
                    if any(i + 1 in image_members for i in members)
                ))[:20],
                "size": len(members),
                "splits": splits,
                "line_numbers": [i + 1 for i in members[:24]],
                "line_numbers_truncated": len(members) > 24,
            })
    overlaps = []
    for image_hash, lines in image_lines.items():
        splits = sorted({records[i - 1]["split"] for i in lines})
        if len(splits) > 1:
            overlaps.append({
                "image_reference_id": _hash(image_hash)[:20],
                "splits": splits,
                "line_numbers": sorted(lines)[:24],
                "line_numbers_truncated": len(lines) > 24,
            })
    overlaps.sort(key=lambda item: item["image_reference_id"])
    crossed.sort(key=lambda item: (-item["size"], item["component_id"]))
    all_partitions_present = all(any(
        row["split"] == split for row in records
    ) for split in _SPLITS)
    structural_group_split_possible = (
        len(groups) >= 3 and all_partitions_present
    )
    return {
        "status": "visual_leakage_detected" if crossed else "no_exact_image_overlap_detected",
        "records_inspected": len(records),
        "record_split_counts": {
            split: sum(row["split"] == split for row in records)
            for split in _SPLITS
        },
        "unique_image_hash_count": len(image_lines),
        "image_connected_component_count": len(groups),
        "largest_component_size": sizes[0],
        "largest_component_share": round(sizes[0] / len(records), 6),
        "component_sizes_descending": sizes[:16],
        "component_sizes_truncated": len(sizes) > 16,
        "components_spanning_splits": len(crossed),
        "records_in_cross_split_components": len(impacted),
        "exact_cross_split_image_count": len(overlaps),
        "overlap_images": overlaps[:16],
        "overlap_images_truncated": len(overlaps) > 16,
        "cross_split_components": crossed[:16],
        "cross_split_components_truncated": len(crossed) > 16,
        "existing_split_is_image_disjoint": len(crossed) == 0,
        "new_source_grouped_split_structurally_possible": structural_group_split_possible,
        "new_source_grouped_split_not_independently_attested": True,
        "existing_checkpoint_test_data_already_exposed": True,
        "retroactive_resplit_valid_for_current_checkpoint": False,
        "requires_new_independent_holdout": True,
        "original_episode_or_environment_provenance_attested": False,
        "data_modified": False,
        "model_retrained": False,
        "active_model_modified": False,
        "model_called": False,
        "files_written": False,
    }
