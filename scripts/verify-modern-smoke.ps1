param(
    [switch]$Sync,
    [switch]$RecreateVenv,
    [switch]$RequireREvidence
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $repoRoot ".venv"
$rDefaultPackageCacheRoot = Join-Path (Join-Path $repoRoot "artifacts") "r-default-library-cache"

function Write-Step {
    param([string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}

Push-Location $repoRoot
try {
    if ($RecreateVenv -and (Test-Path $venvRoot)) {
        Write-Step "Removing existing uv environment at .venv"
        Remove-Item -LiteralPath $venvRoot -Recurse -Force
        $Sync = $true
    }

    if ($Sync) {
        Write-Step "Syncing locked modern environment with uv"
        uv sync --locked
        if ($LASTEXITCODE -ne 0) { throw "uv failed to sync the locked modern environment." }
    }
    else {
        Write-Step "Skipping dependency sync for warm local smoke verification"
    }

    Write-Step "Collecting modern pytest nodes"
    uv run pytest tests\modern --collect-only -q
    if ($LASTEXITCODE -ne 0) { throw "Modern pytest collection failed." }

    Write-Step "Validating manifest sanity"
    uv run python scripts\validate_golden_baseline_manifests.py
    if ($LASTEXITCODE -ne 0) { throw "Golden baseline manifest validation failed." }

    Write-Step "Running smoke pytest nodes"
    uv run pytest `
        tests\modern\golden\test_modern_golden_compare.py::test_golden_summary_parser_reads_current_openmetar_summary_display `
        tests\modern\fast\test_project_pickle_loader.py::test_loader_opens_representative_qt4_project_without_pyqt4_module
    if ($LASTEXITCODE -ne 0) { throw "Smoke pytest nodes failed." }

    Write-Step "Checking Default R Evidence prerequisites"
    $rEvidenceArgs = @("run", "python", "scripts\verify_openmetar_r_default.py")
    if ($RequireREvidence) {
        $rEvidenceArgs += @("--require-r", "--require-installed-packages", "--install-missing", "--r-library-cache-root", $rDefaultPackageCacheRoot)
    }
    uv @rEvidenceArgs
    if ($LASTEXITCODE -ne 0) { throw "Default R Evidence prerequisites failed." }

    Write-Step "Smoke Verification Lane complete"
}
finally {
    Pop-Location
}
