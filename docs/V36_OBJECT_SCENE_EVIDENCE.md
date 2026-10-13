# V36-B — Object scene evidence (metadata only)

This is an additive, read-only, CPU-free metadata contract built on V35. No image, model or checkpoint is loaded, no raw pixels stored, and no file writes occur. It does **not** claim robust object tracking or physical understanding.

- `build_object_scene_evidence`: named visible-object identity, bounding box, mask content hash, label source/confidence, scene/source-group/split and source event lineage; every generated hypothesis is explicitly distinguished from observation.
- `relations_2d_bbox_only`: visible image-plane ordering and bounding-box overlap, **not** depth, ownership, occlusion geometry or object dynamics.
- `audit_scene_split_independence`: exact image-hash and operator-declared source-group contamination checks. "No exact conflict detected" is **not** evidence of true independence or novelty; near duplicates and provenance remain unverified.
- Existing V31–V35 active world-model checkpoint and its 108 connected transitions remain unchanged.

Windows PowerShell — **one command per line**:

~~~powershell
git fetch origin
git switch -c feature/v36-object-scene-evidence --track origin/feature/v36-object-scene-evidence
python -m pytest -q tests/test_cortex_object_scene_v36.py
ruff check .
~~~

This branch is intentionally based on PR #39's V35 head and should be reviewed into that evaluation branch **only after** CI, not merged directly to main. The next integration should connect operator-approved V35 mask hashes and existing CanonicalSpine event IDs to this contract; it must not invent lineage, identity tracking or object labels.
