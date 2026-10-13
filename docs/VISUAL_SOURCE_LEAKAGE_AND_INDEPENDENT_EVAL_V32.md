# V32 — Visual source groups, leakage diagnostics and independent evaluation plan

## Actual operator findings; no claim of generalization

Operator Windows V31:

- 1,984 tests passed; Ruff all checks passed.
- The **existing** compact residual-MLP active checkpoint performs one real
  CPU forward pass on zero vectors: 768 latent coordinates, 4 action
  coordinates, hidden size 128, 2 ms elapsed for local load + forward.
- Both trained/active weights hashes and the active artifact chain are
  verified: \`artifact_chain_ok=true\`.
- Exactly ONE **image hash shared between dataset partitions** was detected:
  \`exact_cross_split_image_overlap_count=1\`.
- Dataset: **108** controlled visual-transform records, **76 train / 16
  validation / 16 test**. This is NOT separately collected real-world
  robotic or action-conditioned video data.
- The model is **executable**, but the legacy split is contaminated and
  independent scientific generalization is NOT supported.

Do NOT retrain or overwrite this baseline simply to make the red
\`integrity_blocked\` flag turn green. That flag records evidence
contamination; discarding records or moving them among split labels
would not make the **already-trained active checkpoint** unseen.

## New V32: exact-image connected-component graph

Existing V31 looked for individual image hashes crossing splits. V32
groups ALL transitions sharing either their \`current_image_hash\` or
\`next_image_hash\`, transitively. A shared intermediary frame links
an entire chain of transitions into a single visual-source component.

The audit reports:
- graph component count, largest component size and its share of all
  108 records;
- count of cross-split components and affected transition records;
- individual overlapping image references hashed AGAIN for privacy,
  their split labels, and **1-based line numbers** inside
  \`.hex-cortex/world-model/transitions.jsonl\`;
- component summaries and capped line lists (never raw paths, original
  image bytes, or latent vectors);
- a conservative indication whether at least three distinct graph
  groups exist, which only means an entirely NEW grouped train/val/test
  experiment may be structurally possible.

**Does NOT** reshuffle current data, rewrite a training manifest, rename
images, move a checkpoint or alter its promotion flags. It makes no
future-world prediction, GPU call, network request or disk write.

An \`exact_cross_split_image_count=1\` could still connect MANY rows by
transitive shared images. Only the actual V32 graph output can tell us
how many. Even a graph with no exact overlaps cannot attest
independence of visually near-identical frames, environmental scenes,
robot episodes, camera positions or media-source licensing.

## External research basis

scikit-learn: \`GroupKFold\` and \`GroupShuffleSplit\` use non-overlapping
group IDs across each split:
- https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html
- https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html

scikit-learn warns that preprocessing and feature selection must not fit
on the test partition:
- https://scikit-learn.org/stable/common_pitfalls.html#data-leakage

These references inform the grouping principle only. V32 implements
its own deterministic **read-only connectivity audit**, NOT scikit-learn
splitters.

## Windows PowerShell — one physical line per command

Pull + test + lint:

~~~powershell
git pull --ff-only origin eval/v21-claude-amplification-prep; if($LASTEXITCODE -ne 0){throw 'Git pull failed'}; python -m pytest -q; if($LASTEXITCODE -ne 0){throw 'Pytest failed'}; ruff check .; if($LASTEXITCODE -ne 0){throw 'Ruff failed'}
~~~

Preflight: read nothing:

~~~powershell
python -m hex_cortex.memory.cortex_visual_leakage_cli_v32 --project-root . --dry-run
~~~

Actual consented read-only graph of existing 108 records:

~~~powershell
python -m hex_cortex.memory.cortex_visual_leakage_cli_v32 --project-root . --approve-read
~~~

An output status of \`visual_leakage_detected\` is a SUCCESSFUL DIAGNOSIS
and uses exit code 0; it is not an integrity certification.

## Next real-world evaluation

1. Keep existing candidate, registry and dataset unchanged as the
   **controlled experiment baseline**.
2. Identify shared source frame(s), trajectories and their component
   lineage from V32 graph.
3. Choose completely new, independently captured and licensed images,
   video segments and corresponding action timestamps. This needs
   operator selection and a domain with a meaningful action contract;
   the old "brightness, contrast, translate_x, translate_y" actions
   represent **visual transformations**, not necessarily robot motion.
4. Reserve independent **source scenes/episodes/environments** for
   test BEFORE preprocessing or training; record reliable episode,
   environment, device and timestamp identifiers.
5. Freeze the same DINOv2 encoder and 768-dimensional latent scheme;
   never mix V-JEPA 2.1 representations into this checkpoint's DINOv2
   feature space.
6. Use V30's grouped external-latent import for newly converted data;
   compare the ACTUAL stored CPU model vs identity baseline and inspect
   errors PER environment, not only global MSE. All data-provenance
   claims remain unverified until externally attested.
7. Use a separate, newly trained model candidate only if the desired
   task requires it; do not silently retrain the active model.

A successful local CPU checkpoint smoke is orthogonal to scientific
accuracy. No autonomous actuation is enabled.
