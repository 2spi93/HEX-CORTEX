# HEX-CORTEX V35 — Object-centric world model: reuse, don't reinvent

**Decision (13 October 2026):** preserve the existing HEX-CORTEX
CognitiveClock/LocalHarness/Spine, permission controls, replay receipts,
cached CPU DINOv2 768D encoder and the existing compact
action-conditioned residual-MLP checkpoint. Build a vendor-neutral
object-centric perception and world-action **interface around them**.
Do not train a new foundation model or replace DINOv2 weights.

## Verified baseline (operator evidence)

- Windows V34: 2007 pytest PASS, Ruff PASS.
- Actual DINOv2 weights \`facebook/dinov2-base\` are installed in
  Hugging Face local cache and load on CPU with 768D features.
- Actual compact world model 768D visual + 4D *image transformation*
  action → 768D predicted next visual latent can run on CPU.
- Original 108 image-transform transitions constitute ONE connected
  visual-image group spanning train/validation/test. No scientifically
  independent model improvement proved.
- Actual novel heldout photo/action/next-photo experiment remains not
  executed because no truly independently sourced image pair with
  verified action values is provided.

## Major external capabilities (verified official sources)

| Backend | What it actually produces | What it does NOT prove | Deployment now |
| --- | --- | --- | --- |
| **Microsoft Florence-2-base** | 0.23B multimodal caption, object boxes, OCR, region captions | exact alpha masks; faithful 3D; physical prediction | Test *as a separate opt-in CPU recognizer*, inspect remote-code requirements/license |
| **MobileSAM / TinySAM** | Lightweight prompted CPU masks, with MobileSAM CPU demonstrations and Apache-2.0 sources | detection of every object *without* prompts, true 3D, hidden background | **First CPU segmentation benchmark** before heavyweight SAM 3.1 |
| **Meta SAM 3.1** | Language/image-prompted object masks & multi-object video tracking | hidden pixels, physically accurate depth | Use licensed external/GPU service adapter later; don't install huge CUDA stack on broken RX 6700 XT |
| **Qwen/Qwen-Image-Layered** | Generatively decomposes 2D RGB into multiple independent **RGBA layers**, supports editing/moving and PSD export | exact ground truth of hidden regions; sensor measurements | Use as separately approved capable GPU/cloud provider; official quick start uses **CUDA and bfloat16** |
| **Meta SAM 3D Objects** | Plausible textured 3D object/scene reconstruction from image | physical dimensions from a monocular photo without calibration | Offline/specialist optional 3D stage |
| **ByteDance Depth Anything 3 Small/Base** | Estimated spatial depth/geometry | guaranteed metric depth | Optional geometry stage only after objective calibration tests |
| **Meta V-JEPA 2.1 / V-JEPA 2-AC** | Temporal dense video features / action-conditioned latent predictor | same DINOv2 embedding space or drop-in model | **Separate** video world backend after clean temporal dataset |
| **OpenAI GPT-Image-2.5 Flare/Sunburst** | High-fidelity generative editing, mask edit, transparency where supported | standalone transparent multi-layer object source truth | Optional permissioned, budgeted cloud editor, not local core |
| **NVIDIA Cosmos Predict2.5** | Generative physical-world video conditioned on image/video/text | low-VRAM CPU viability or measured ground-truth dynamics | Research comparator only, not workstation deployment |

Official sources:
- https://huggingface.co/microsoft/Florence-2-base
- https://ai.meta.com/blog/segment-anything-model-3/
- https://github.com/ChaoningZhang/MobileSAM
- https://github.com/xinghaochen/TinySAM
- https://github.com/QwenLM/Qwen-Image-Layered
- https://ai.meta.com/blog/sam-3d
- https://github.com/ByteDance-Seed/Depth-Anything-3
- https://github.com/facebookresearch/vjepa2
- https://openai.com/index/introducing-chatgpt-images-2-5/
- https://docs.nvidia.com/cosmos/latest/introduction.html

Model versions and licences must be verified at actual adoption.
OpenAI generative APIs are neither local model weights nor transparent
source; do not equate masking/editing with native multilayer decomposition.

## Architecture — ONE real scene memory, adapters are interchangeable

\`\`\`text
operator-approved photo/video/audio/sensor
   │
   ├─ DINOv2 CPU visual encoder [ALREADY ACTIVE; keep frozen]
   ├─ Florence-2 optional detector/captioner (future)
   ├─ SAM3.1/efficient mask segmenter external provider (future)
   ├─ Qwen-Image-Layered RGBA generator external provider (future)
   └─ Depth Anything3 / SAM3D geometry estimates (later)
   │
   ▼
Object-centric state: {scene_id, capture provenance, object_id,
      source frames, bounding box, visible mask, RGBA layer, label,
      confidence, tracking correspondence, geometry with uncertainty,
      action/timestamp, evidence hashes, occlusion/unknown flags}
   │
   ├─ V35 exact pixel compositor for GIVEN approved masks [IMPLEMENTED]
   ├─ object-centric spatial/temporal relationships (NEXT)
   ├─ existing Spine/Replay/Memory provenance gates
   ├─ existing DINOv2-MLP world model for compatible 4D
   │    brightness/contrast/translate_x/translate_y inputs only
   └─ later independently evaluated JEPA action-conditioned world backend
   │
   ▼
Predict next object/scene -> compare with observed scene
    -> per-object errors, grounded counterfactual tests,
       uncertainty, heldout environment checks
   │
   ▼
MANUAL-only promotion; hardware gateway stays SIMULATION ONLY
\`\`\`

**Novelty** is the *auditable connection* between exact objects and
actions, persistent identities, counterfactual world prediction and
independent physical observations — not claiming to invent a better
segmenter, generator, VLM or autonomous robot from scratch.

## What V35 ACTUALLY IMPLEMENTS

\`cortex_object_layers_v35.py\` and
\`cortex_object_layers_cli_v35.py\`:

- CPU-only extraction of visible original-photo pixels into RGBA
  layers from **externally supplied masks**. Those masks could later
  be sourced from SAM or an explicitly selected manual tool.
- Disjoint mask ownership; first mask wins where object masks overlap
  (ambiguity count reported), preventing duplicate pixel claims.
- Create an alpha-masked visible-only background plus object layers,
  recompose the original opaque input, **verify byte-for-byte exact
  RGBA pixel equality** with PIL.
- Output pixel counts, image/layer hashes and quality evidence without
  persisting data or invoking any model by default.
- Only explicit \`--approve-read --approve-write --export-dir\` writes
  real PNG objects/background/recomposition to a **new** in-project
  directory. No overwrites.
- Strictly bounded relative image/mask paths, unique IDs and same
  dimensions. All source images/metadata remain unmodified.
- **DOES NOT** autonomously identify objects, generate masks, infer
  hidden geometry, inpaint occluded backgrounds, reconstruct 3D, infer
  real actions or load any SAM/Qwen weights. Pillow is needed for
  real pixel operations; CI environments without it may skip these
  optional tests. Do not describe this as a full SAM integration.

### Windows one physical PowerShell command per line

Pull and test:

~~~powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
~~~

Safe preflight, reads nothing (example placeholder paths):

~~~powershell
python -m hex_cortex.memory.cortex_object_layers_cli_v35 --image images/novel_scene.png --mask cup=masks/cup.png --dry-run
~~~

Real read-only compositing, only if approved files and masks actually
exist under the repository (NO writes, no model calls):

~~~powershell
python -m hex_cortex.memory.cortex_object_layers_cli_v35 --project-root . --image images/novel_scene.png --mask cup=masks/cup.png --approve-read
~~~

Save transparent RGBA layers, only after explicit operator permission
and choosing a brand-new output directory:

~~~powershell
python -m hex_cortex.memory.cortex_object_layers_cli_v35 --project-root . --image images/novel_scene.png --mask cup=masks/cup.png --export-dir outputs/scene-run-001 --approve-read --approve-write
~~~

**All image paths are examples**; missing files will be rejected. A
mask must already exist and align with the original photo. A PNG mask
uses grayscale pixels with >=128 considered visible/foreground.
The source must be opaque; unknown pixels behind removed foreground
remain transparent, NOT magically generated.

## Fast milestones, prioritized by actual capability

### Phase A — local CPU first
1. Operator-supplied new image: V35 pixel-accurate object/mask/scene
   contract + independent data hash receipts. **Done in V35 code.**
2. Real Florence-2-base (or equivalent CPU VLM) in a separately managed
   optional environment, **without** uncontrolled remote-code execution:
   detect objects, emit bounding boxes/captions with confidence.
3. **Prioritize MobileSAM then TinySAM on CPU**, after isolated
   installation and small benchmark with operator-selected weights.
   MobileSAM has an official CPU demo; TinySAM has smaller compressed
   versions. Compare segmentation mask IoU vs manual masks, startup,
   wall clock time and RAM. These are NOT yet installed/inferred by V35.
   Do NOT silently substitute a slow/broken SAM3.1 CUDA stack for the
   user's faulty RX 6700 XT. Feed the produced masks to V35.
4. V33 independent novel pair with known action and cached DINOv2;
   compare active predictor vs identity baseline and per-object
   predictions over several independently sourced scenes.

### Phase B — specialist model providers
5. Selective SAM 3.1 and Qwen-Image-Layered inference on a GPU/cloud
   backend after operator approves licence, data transfer, costs
   and hardware. Treat generated hidden pixels as hypotheses.
6. Optional Depth Anything 3 / SAM3D 3D geometry, with uncertainty and
   calibration tests.
7. New, separately benchmarked JEPA video/action model backend,
   with ENCODER-IDENTITY separation from DINOv2, test episode
   grouping and counterfactual action consistency. Never overwrite
   the working 768D active compact checkpoint.

### Phase C — objective measures before model activation
- Masks: IoU against human masks, false positives, per-object boundary F1.
- Extracted visible layers: exact RGB/RGBA recompose, overlap
  ambiguity, background alpha correctness, CPU latency and RAM.
- Tracking: object ID continuity after occlusion and shot change.
- Generated hidden surfaces: photometric consistency on withheld
  camera views, calibrated uncertainty, disclosure as synthetic.
- Spatial reasoning: object relations and depth relative error,
  occlusion consistency against annotated truth.
- World dynamics: identity baseline, compatible model MSE and per
  object/scene generalization on completely independent source scenes,
  action-conditioned rollout, calibration and domain-shift fallback.
- Formal governance: read/persist/share/move control, project scope,
  receipts, no automatic hardware actuation.

## Two hard limitations not to disguise

1. **A mask is not a complete layer generative model.** Masked cutouts
   preserve only visible object pixels. If a foreground object is moved,
   the previously hidden background is unknown. Qwen-Image-Layered
   and high-quality inpainting may synthesize it, but it is a *guess*,
   not a new physical observation.
2. **Object-centric editing is not physical causality.** The current
   predictor learned 4D image-transform controls, not robot motor
   torques, forces, velocities or reliable human tool affordances.
   New robot dynamics need their own encoder/action/trajectory
   contracts and independent evaluation.
