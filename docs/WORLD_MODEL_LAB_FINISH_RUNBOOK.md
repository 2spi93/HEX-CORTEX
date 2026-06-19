# World Model Lab Finish Runbook

Run the complete guarded local lab cycle with one PowerShell command:

```powershell
powershell -ExecutionPolicy Bypass `
  -File scripts\run_world_model_lab_finish.ps1 `
  -ProjectRoot . `
  -ComfyRoot "C:\Users\2spi\Documents\comfy\ComfyUI" `
  -ImageName "HEX-CORTEX_00001_.png" `
  -SampleCount 36 `
  -Epochs 100 `
  -OperatorApproved
```

The runner performs:

```text
architecture audit
→ controlled transition bootstrap
→ dataset manifest
→ bounded training plan
→ compact predictor training
→ held-out promotion gate
→ active predictor registration when allowed
→ active prediction smoke test
→ final completion audit
```

A return code of `3` means the candidate trained successfully but did not beat the held-out identity baseline. In that case the candidate remains inactive and its metrics are retained under `.hex-cortex\world-model\candidate`.

The controlled transform domain is a laboratory proof only. It must not be represented as a general physical world model. Real environment capability requires genuine sequential observations and meaningful actions in a separately versioned dataset domain.
