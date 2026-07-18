param(
    [string]$ArtifactName = "RCMetaStudio-windows-x64",
    [string]$ArchiveRootName,
    [string]$RIntegrationKit,
    [string]$ExpectedRIntegrationKitSha256,
    [switch]$RecreateVenv,
    [switch]$SkipClean,
    [switch]$SkipSmoke,
    [switch]$CaptureAdaptiveLayoutEvidence
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $repoRoot ".venv"
$pythonExe = Join-Path $venvRoot "Scripts\python.exe"

function Write-Step {
    param([string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message)
}

Push-Location $repoRoot
try {
    if (-not $RIntegrationKit -or -not $ExpectedRIntegrationKitSha256) {
        throw "Package assembly requires -RIntegrationKit and -ExpectedRIntegrationKitSha256 from the native producer."
    }
    if ($RecreateVenv -and (Test-Path $venvRoot)) {
        Write-Step "Removing existing uv environment at .venv"
        Remove-Item -LiteralPath $venvRoot -Recurse -Force
    }

    Write-Step "Authenticating the promoted kit before offline environment assembly"
    uv run --no-project --offline --python 3.11.9 python scripts/r_integration_kit.py verify-content --kit $RIntegrationKit --target windows-x64 --uv-lock uv.lock --expected-kit-sha256 $ExpectedRIntegrationKitSha256
    if ($LASTEXITCODE -ne 0) { throw "promoted R integration kit authentication failed." }

    Write-Step "Syncing locked verification environment from the authenticated kit cache"
    uv --cache-dir (Join-Path $RIntegrationKit "python\uv-cache") sync --locked --offline
    if ($LASTEXITCODE -ne 0) { throw "uv failed to sync the locked verification environment." }

    Write-Step "Building Windows package artifact with PyInstaller"
    $buildArgs = @{
        ArtifactName = $ArtifactName
        ArchiveRootName = $ArchiveRootName
        PythonExe = $pythonExe
        RIntegrationKit = $RIntegrationKit
        ExpectedRIntegrationKitSha256 = $ExpectedRIntegrationKitSha256
        SkipDependencyInstall = $true
    }
    if ($SkipClean) { $buildArgs.SkipClean = $true }
    if ($SkipSmoke) { $buildArgs.SkipSmoke = $true }
    if ($CaptureAdaptiveLayoutEvidence) { $buildArgs.CaptureAdaptiveLayoutEvidence = $true }
    & (Join-Path $repoRoot "scripts\build-windows-package.ps1") @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Windows package build failed." }

    Write-Step "Windows package complete: artifacts\$ArtifactName.zip"
}
finally {
    Pop-Location
}
