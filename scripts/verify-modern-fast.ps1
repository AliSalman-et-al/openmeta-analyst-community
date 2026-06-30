param(
    [switch]$Sync,
    [switch]$RecreateVenv,
    [switch]$RequireREvidence,
    [switch]$StrictTaxonomy,
    [string]$FastWorkers = "4"
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
        Write-Step "Skipping dependency sync for warm local verification"
    }

    Write-Step "Validating Comprehensive Golden Baseline manifests"
    uv run python scripts\validate_golden_baseline_manifests.py
    if ($LASTEXITCODE -ne 0) { throw "Golden baseline manifest validation failed." }

    Write-Step "Checking modern test taxonomy"
    $taxonomyArgs = @("run", "python", "scripts\validate_test_taxonomy.py")
    if ($StrictTaxonomy) {
        $taxonomyArgs += "--strict"
    }
    uv @taxonomyArgs
    if ($LASTEXITCODE -ne 0) { throw "Modern test taxonomy validation failed." }

    Write-Step "Running parallel fast verification pytest lanes"
    $fastPytestArgs = @("run", "pytest", "tests\modern\fast", "tests\modern\golden", "tests\modern\packaging_contract")
    if ($FastWorkers -and $FastWorkers -notin @("0", "1")) {
        $fastPytestArgs += @("--dist", "loadfile", "-n", $FastWorkers)
    }
    uv @fastPytestArgs
    if ($LASTEXITCODE -ne 0) { throw "Fast verification pytest lanes failed." }

    Write-Step "Verifying Default R Evidence"
    $rEvidenceArgs = @("run", "python", "scripts\verify_openmetar_r_default.py")
    if ($RequireREvidence) {
        $rEvidenceArgs += @("--require-r", "--require-installed-packages", "--install-missing", "--r-library-cache-root", $rDefaultPackageCacheRoot)
    }
    uv @rEvidenceArgs
    if ($LASTEXITCODE -ne 0) { throw "Default R Evidence failed." }

    Write-Step "Fast Verification Lane complete"
}
finally {
    Pop-Location
}
