param(
    [string]$ProjectRoot = ".",
    [string]$Endpoint = "http://127.0.0.1:8188",
    [string]$RegistryRoot = ".hex-cortex/comfyui-workflows",
    [switch]$ImportWorkflow
)

$ErrorActionPreference = "Stop"

Push-Location $ProjectRoot
try {
    Write-Host "[1/3] Probing ComfyUI at $Endpoint"
    hexcortex-operational comfyui-probe --endpoint $Endpoint
    if ($LASTEXITCODE -ne 0) {
        throw "ComfyUI probe failed. Start or repair the local service first."
    }

    Write-Host "[2/3] Validating reviewed API workflow template"
    hexcortex-operational workflow-validate `
        "workflows/comfyui/txt2img_basic_api_v1.workflow.json" `
        --allow-placeholders
    if ($LASTEXITCODE -ne 0) {
        throw "Workflow validation failed."
    }

    if ($ImportWorkflow) {
        Write-Host "[3/3] Importing homologated workflow bundle"
        hexcortex-operational workflow-import `
            "workflows/comfyui/txt2img_basic_api_v1.workflow.json" `
            "workflows/comfyui/txt2img_basic_api_v1.profile.json" `
            --registry-root $RegistryRoot `
            --operator-approved
        if ($LASTEXITCODE -ne 0) {
            throw "Workflow import failed."
        }
    }
    else {
        Write-Host "[3/3] Import skipped. Re-run with -ImportWorkflow after review."
    }

    Write-Host "ComfyUI operational preflight completed."
}
finally {
    Pop-Location
}
