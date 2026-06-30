param(
    [switch]$RecreateVenv
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $repoRoot ".venv"

function Write-Step {
    param([string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}

Push-Location $repoRoot
try {
    if ($RecreateVenv -and (Test-Path $venvRoot)) {
        Write-Step "Removing existing uv environment at .venv"
        Remove-Item -LiteralPath $venvRoot -Recurse -Force
    }

    Write-Step "Syncing locked modern environment with uv"
    uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw "uv failed to sync the locked modern environment." }

    Write-Step "Validating Comprehensive Golden Baseline manifests"
    uv run python scripts\validate_golden_baseline_manifests.py
    if ($LASTEXITCODE -ne 0) { throw "Golden baseline manifest validation failed." }

    Write-Step "Checking modern test taxonomy"
    uv run python scripts\validate_test_taxonomy.py
    if ($LASTEXITCODE -ne 0) { throw "Modern test taxonomy validation failed." }

    Write-Step "Running fast pytest lanes"
    uv run pytest tests\modern -m "fast or golden or packaging_contract"
    if ($LASTEXITCODE -ne 0) { throw "Fast pytest lanes failed." }

    Write-Step "Verifying Default R Evidence"
    uv run python scripts\verify_openmetar_r_default.py
    if ($LASTEXITCODE -ne 0) { throw "Default R Evidence failed." }

    Write-Step "Fast Verification Lane complete"
}
finally {
    Pop-Location
}
