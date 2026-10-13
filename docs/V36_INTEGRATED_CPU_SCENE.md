# HEX-CORTEX V36-C — CPU masks to object-scene evidence

**Scope:** Integrated evaluation branch from V35 + V36-A + V36-B. No model weights, GPU, retraining, cloud calls, automatic model activation, file mutation or hardware actuation. The read-only scene bridge receives an already-produced V36-A segmentation JSON receipt and creates a V36-B object scene with evidence references. Identity is **local to one scene**; tracking the same object across photos is not yet implemented.

## Distinguish the three data layers

1. **Observed**: the original photo's input SHA-256, declared scene/source group, original box prompt and bounded verified scene dimensions.
2. **Inferred**: MobileSAM's visible mask predicted from an operator box; confidence/IoU may be absent. A good IoU requires separately collected human ground truth. Names assigned by the operator are **assertions**, not automatically verified image recognition.
3. **Generated**: synthetic hypotheses are represented separately by the V36-B `generated` contract. The scene bridge does not claim hidden pixels, depth or physical dynamics. It records the mask semantics separately even when the immutable source-image metadata is labelled `observed_metadata`.

The `segmentation_receipt_sha256` hashes the receipt JSON as received; it is **not** a digital signature nor proof of authentic MobileSAM execution. `source_event_ids` are operator-provided; this bridge does **not** verify their existence in the CanonicalSpine. That verification should be the next integration.

### Reuse and operational constraints

- `V35`: exact RGBA recomposition using approved externally produced PNG masks.
- `V36-A`: opt-in real CPU MobileSAM; no download or write unless approved, 2D human box prompts, optional IoU against manually provided reference mask.
- `V36-B`: object metadata, source/image hashes, 2D bbox relation and exact split contamination checks.
- `V36-C`: joins one V36-A receipt with V36-B metadata without a second memory store; no model calls and no implicit persistence.

### PowerShell commands — **one physical line per command**

From the project root:

~~~powershell
git fetch origin
git switch -c feature/v36-integrated-perception-scene --track origin/feature/v36-integrated-perception-scene
python -m pytest -q tests/test_cortex_object_layers_v35.py tests/test_cortex_cpu_segmentation_v36.py tests/test_cortex_object_scene_v36.py tests/test_cortex_segmentation_scene_bridge_v36.py tests/test_cortex_segmentation_scene_bridge_cli_v36.py
ruff check .
~~~

Dry-run: does not read the JSON input file.

~~~powershell
python -m hex_cortex.memory.cortex_segmentation_scene_bridge_cli_v36 --receipt receipts/v36-segmentation-001.json --scene-id scene001 --source-group episode001 --split test --label cup=cup --source-event-id evt001 --dry-run
~~~

For a **genuine** operator-approved receipt already saved under the project (replace labels/event identifiers, only if actually known), read-only:

~~~powershell
python -m hex_cortex.memory.cortex_segmentation_scene_bridge_cli_v36 --receipt receipts/v36-segmentation-001.json --scene-id scene001 --source-group episode001 --split test --label cup=cup --source-event-id evt001 --approve-read
~~~

This command does **not** produce the segmentation receipt itself. First obtain a real image and trusted MobileSAM weights; use the V36-A documentation and command with the model explicitly approved. To save the output JSON in PowerShell, use an operator-selected new path and verify the command succeeded before relying on the file. Never substitute a generated synthetic example for a real model benchmark.

### Quality gate

Run Windows/Ubuntu CI including the **Pillow-required** V36 suite. The ordinary root CI, without Pillow, legitimately skips image fixtures, so its raw pass count must never be confused with a true model quality benchmark. Continue PRs in draft; human review before merge.

Next: true CPU MobileSAM run with a novel photograph, independent manual mask IoU, tracked provider fingerprint, and verified lineage to existing CanonicalSpine. Only then integrate optional Florence-2 semantic boxes in a separately reviewed dependency environment. Preserve the existing DINOv2 768D descriptor and active world checkpoint.
