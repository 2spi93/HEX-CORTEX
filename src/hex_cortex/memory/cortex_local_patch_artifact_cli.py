from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from hex_cortex.memory.cortex_local_patch_artifact import CORTEX_LOCAL_PATCH_ARTIFACT_FILENAME, build_cortex_local_patch_artifact, summarize_cortex_local_patch_artifacts
def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('profile',type=Path); p.add_argument('--summary',action='store_true'); p.add_argument('--pretty',action='store_true'); a=p.parse_args(argv)
    payload=summarize_cortex_local_patch_artifacts(a.profile/CORTEX_LOCAL_PATCH_ARTIFACT_FILENAME) if a.summary else build_cortex_local_patch_artifact(a.profile)
    json.dump(payload,sys.stdout,indent=2 if a.pretty else None,sort_keys=True); print(); return 0
if __name__=='__main__': raise SystemExit(main())
