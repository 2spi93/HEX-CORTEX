from __future__ import annotations

import json
from pathlib import Path

WORLD_MODEL_REVIEW_FILENAME = "cortex-world-model-review.jsonl"


def append_world_model_review(profile: Path, record: dict[str, object]) -> Path:
    path = profile / WORLD_MODEL_REVIEW_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return path
