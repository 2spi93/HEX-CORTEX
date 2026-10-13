# HEX-CORTEX V34 — DINOv2 local cache vs active checkpoint

## Evidence from the operator's Windows computer

- V33 validation after the CPU descriptor test correction:
  **6 targeted tests passed**, **2000 total tests passed**, Ruff clean.
- V31 independently verified the active compact residual MLP's file
  SHA256 chain and a true CPU forward: latent dimension 768, action
  dimension 4, hidden 128. The old dataset has 108 controlled visual
  transformation transitions, all one linked source group; no
  generalization is established.
- V33 is ready for new operator-selected image pairs with known visual
  actions, but no actual new pair has yet been supplied or scored.

## Why cached encoder verification matters

V33 requires EXACT DINOv2 descriptor equality to the frozen descriptor
used during prior training. The existing training CLI defaults to
\`--device cpu\`, \`--pooling cls\` and
\`--model-ref facebook/dinov2-base\`. V33 uses these same defaults.
Because descriptor hashes include requested device, a historical
custom training run with \`--device auto\` would legitimately differ,
even when runtime auto selected CPU. **Never bypass a hash mismatch
or rewrite the registry** just to make a cache load pass.

The local V26 optional dependency probe found \`torch=true\`,
\`transformers=true\`, \`PIL=true\`; this means installed packages,
NOT cached pretrained DINOv2 weights. V34 distinguishes these facts.

## V34 behavior

1. \`--approve-read\`: verify V31 active model artifact chain,
   read active encoder descriptor hash and compact hidden config, and
   compare a reconstructed strictly CPU encoder descriptor. Does not
   load Hugging Face weights or make network calls.
2. \`--approve-cache\` additionally asks Hugging Face's
   \`try_to_load_from_cache\` for LOCAL config, image processor and
   unsharded/sharded weight filename HINTS. Cache presence checks
   do not certify complete shards, weight validity or actual loading.
3. \`--approve-load\` separately permits real
   \`AutoImageProcessor.from_pretrained\` and
   \`AutoModel.from_pretrained\` with
   \`local_files_only=True, trust_remote_code=False\`. Model parameters
   are checked to remain on CPU. The hidden dimension must match the
   existing compact model's input size (768 on user's actual system).
   No image decoding, no inference or model training.
4. No background processes, web requests, implicit downloads,
   external APIs, GPU calls, file updates, promotion or device actuation.
   A missing cache is not a software defect: the next step is an
   independently approved way of obtaining model weights.
5. CI uses synthetic fixture models/cache stubs. **CI success does not
   prove the user's real DINOv2 weights are present**.

## Windows PowerShell — one physical line per command

Update, run tests, lint:

~~~powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
~~~

Descriptor only, no Hugging Face cache check:

~~~powershell
python -m hex_cortex.memory.cortex_dinov2_active_preflight_cli_v34 --project-root . --approve-read
~~~

Strictly local cache check (no model load):

~~~powershell
python -m hex_cortex.memory.cortex_dinov2_active_preflight_cli_v34 --project-root . --approve-read --approve-cache
~~~

Optional, potentially more costly LOAD of already locally cached
DINOv2 weights, only after both previous steps and explicit
\`--approve-load\`. CPU only; no image pass or network:

~~~powershell
python -m hex_cortex.memory.cortex_dinov2_active_preflight_cli_v34 --project-root . --approve-read --approve-cache --approve-load
~~~

The default recommended first step is **descriptor+cache**, not model
load. Do not enable new GPU benchmarks until the RX 6700 XT hardware
power/cabling issue is resolved independently.

## Next scientific objective

Prepare 2 source-separated, previously unseen, legally usable images
before/after a **known** visual action corresponding to the active
model's four actions. The V33 command then compares the model's
actual predicted next DINOv2 embedding against the identity baseline,
without modifying the active checkpoint. Evaluate multiple genuinely
independent episodes/scenes before asserting cognitive improvement.
Do NOT use the 108 existing transitions as independent held-out data
by retroactively changing their splits.
