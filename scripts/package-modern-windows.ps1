param(
    [string]$ArtifactName = "OpenMetaAnalyst-modern-windows-x64",
    [string]$RPackageCacheRoot,
    [switch]$RecreateVenv,
    [switch]$SkipClean,
    [switch]$SkipSmoke,
    [switch]$SkipVerification
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $repoRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"
if (-not $RPackageCacheRoot) {
    $RPackageCacheRoot = Join-Path (Join-Path $repoRoot "artifacts") "r-library-cache"
}

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

    if (-not $SkipVerification) {
        Write-Step "Verifying Full R Stack Evidence"
        uv run python scripts\verify_openmetar_r_stack.py --r-library-cache-root $RPackageCacheRoot
        if ($LASTEXITCODE -ne 0) { throw "Full R Stack Evidence failed." }
    }

    Write-Step "Building modern Windows artifact with PyInstaller"
    $buildArgs = @{
        ArtifactName = $ArtifactName
        PythonExe = $pythonExe
        RPackageCacheRoot = $RPackageCacheRoot
        SkipDependencyInstall = $true
    }
    if ($SkipClean) { $buildArgs.SkipClean = $true }
    if ($SkipSmoke) { $buildArgs.SkipSmoke = $true }
    & (Join-Path $repoRoot "scripts\build-modern-windows-binary.ps1") @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Modern Windows binary build failed." }

    Write-Step "Modern Windows package complete: artifacts\$ArtifactName.zip"
}
finally {
    Pop-Location
}
